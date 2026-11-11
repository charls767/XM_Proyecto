"""Emisión semanal del pronóstico con registro inmutable.

Uso:
    python src/semanal.py                  # actualiza datos, emite, registra y califica
    python src/semanal.py --sin-actualizar # usa la caché local (para pruebas)

Cada emisión agrega una fila a `registro/pronosticos.csv` y guarda en
`registro/snapshots/` los valores exactos de las variables y la última fecha
publicada de cada serie en ese momento. Una semana base ya registrada no se
vuelve a escribir: el registro es la evidencia prospectiva del modelo. Solo las
columnas de calificación (real, error, cubierto) se completan después, cuando el
precio de la semana objetivo ya se conoce.
"""

import hashlib
import json
import os
from pathlib import Path
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import alertas  # noqa: E402
import backtesting as bt  # noqa: E402
import calibration as cal  # noqa: E402
import config  # noqa: E402
import data_pipeline as dp  # noqa: E402
import feature_engineering as fe  # noqa: E402
import lear  # noqa: E402
import models  # noqa: E402
import monitoreo  # noqa: E402
import xm_client as xm  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
REGISTRO = RAIZ / "registro"
ARCHIVO = REGISTRO / "pronosticos.csv"
SERIES_MODELO = ["precio", "demanda", "aportes", "aportes_media", "volumen_pct", "volumen_kwh",
                 "capacidad", "oferta", "generacion", "combustible"]
COLUMNAS = ["fecha_emision", "semana_base", "semana_objetivo", "version_modelo", "estado", "motivos",
            "datos_precio_hasta", "precio_base", "pronostico", "cambio_pct", "cota90", "cota90_vol",
            "ingenuo", "alerta_precio_alto", "alerta_salto", "alerta_estres_hidrico",
            "real", "error", "cubierto", "fecha_calificacion",
            "candidato_version", "candidato_pronostico", "candidato_cota90", "candidato_error", "candidato_cubierto",
            "candidato_cmg_version", "candidato_cmg_pronostico", "candidato_cmg_cota90", "candidato_cmg_error",
            "candidato_cmg_cubierto", "huella"]
# Lo emitido no cambia nunca; la huella encadena estas columnas con la fila anterior.
COLUMNAS_SELLADAS = ["fecha_emision", "semana_base", "semana_objetivo", "version_modelo", "estado", "motivos",
                     "precio_base", "pronostico", "cota90", "cota90_vol", "candidato_version",
                     "candidato_pronostico", "candidato_cota90"]
# Columnas añadidas después: se sellan solo en las filas que las tienen, para que las huellas
# de las filas anteriores no cambien.
SELLADAS_DESDE_CMG = ["candidato_cmg_version", "candidato_cmg_pronostico", "candidato_cmg_cota90"]
CANDIDATOS = ("candidato", "candidato_cmg")


def actualizar_datos():
    """Refresca la caché (los meses recientes se vuelven a pedir) y devuelve la última fecha por serie."""
    return {n: xm.descargar(n).fecha.max() for n in SERIES_MODELO}


def ultimas_fechas():
    return {n: xm.ultima_fecha_en_cache(n) for n in SERIES_MODELO}


def historial_fuera_de_muestra(d):
    """Pronósticos walk-forward del modelo principal y del ingenuo, para calibrar la cota y monitorear."""
    r = bt.backtest(d, [models.Modelo("Ingenuo"), models.Modelo("Principal", config.VARIABLES, models.ridge)],
                    inicio=config.INICIO_BACKTEST, cada=4)
    w = bt.ancho(r)
    return pd.DataFrame({"real": w.real, "ingenuo": w.base, "prediccion": w.Principal})


def contribuciones(modelo, fila):
    """Descomposición exacta de Ridge: aporte de cada variable al cambio log frente a una semana promedio."""
    esc, reg = modelo[0], modelo[-1]
    z = (fila[config.VARIABLES].to_numpy(dtype=float) - esc.mean_) / esc.scale_
    aporte = reg.coef_ * z
    return float(reg.intercept_), pd.Series(aporte, index=config.VARIABLES)


def _cota(historial, semana, base, prediccion, escala=None):
    fila = pd.DataFrame({"real": [np.nan], "ingenuo": [base], "prediccion": [prediccion]}, index=[semana])
    h = pd.concat([historial[historial.index < semana], fila])
    return float(cal.conformal(h.real, h.prediccion, nivel=config.NIVEL_COTA,
                               ventana=config.VENTANA_CONFORMAL, escala=escala).iloc[-1])


def candidato(d, hist, semana, base, pronostico, recalcular=False):
    """Ensamble Ridge 14 + LEAR directo (E11), con su propia cota conformal.

    Se calcula en paralelo y no afecta al pronóstico oficial. El promedio es en escala
    de precio y sus errores pasados salen de un walk-forward con los mismos bloques.
    """
    diaria = dp.tabla_diaria(recalcular=recalcular)
    modelo = lear.LEAR("LEAR", diaria, 6, "directo")
    r = bt.backtest(d, [models.Modelo("Ingenuo"), modelo], inicio=config.INICIO_BACKTEST, cada=4,
                    requeridas=config.VARIABLES + ["y"])
    previo = bt.ancho(r).LEAR.reindex(hist.index)
    h = hist.assign(prediccion=(hist.prediccion + previo) / 2).dropna(subset=["prediccion"])
    pred = (pronostico + float(modelo.ajustar_predecir(None, pd.DataFrame(index=[semana]))[0])) / 2
    return {"version": config.VERSION_CANDIDATO, "pronostico": pred, "cota90": _cota(h, semana, base, pred)}


def tabla_cmg(d, cmg):
    """Tabla semanal con el costo marginal programado de los primeros días de la semana objetivo."""
    dc = d.join(dp.costo_marginal(cmg, dias=(config.DIAS_CMG_CANDIDATO,)))
    dc["cmg_brecha"] = np.log(dc.cmg_semana / dc.precio)
    return dc


def candidato_cmg(d, semana, base, actualizar=True):
    """Ridge 14 + costo marginal programado del lunes y el martes de la semana objetivo (E12).

    Se calcula en paralelo y no afecta al pronóstico oficial. Guarda los valores horarios del
    costo marginal tal como estaban publicados al emitir: así se puede verificar después que la
    historia de la API es la versión ex ante y no una revisada.
    """
    cmg = xm.descargar("costo_marginal") if actualizar else xm.leer_cache("costo_marginal")
    dc = tabla_cmg(d, cmg)
    variables = config.VARIABLES_CANDIDATO_CMG
    faltan = [v for v in variables if pd.isna(dc.at[semana, v])]
    if faltan:
        raise ValueError(f"costo marginal de la semana objetivo aún no publicado ({', '.join(faltan)})")
    r = bt.backtest(dc, [models.Modelo("Ingenuo"), models.Modelo("CMG", variables, models.ridge)],
                    inicio=config.INICIO_BACKTEST, cada=4, requeridas=variables + ["y"])
    w = bt.ancho(r)
    h = pd.DataFrame({"real": w.real, "ingenuo": w.base, "prediccion": w.CMG})
    completas = dc.dropna(subset=variables + ["y"])
    completas = completas[completas.index < semana]
    m = models.ridge().fit(completas[variables], completas.y)
    pred = base * float(np.exp(m.predict(dc.loc[[semana], variables])[0]))
    dias = pd.date_range(semana + pd.Timedelta(weeks=1), periods=config.DIAS_CMG_CANDIDATO)
    horario = cmg[cmg.fecha.isin(dias)].set_index("fecha")[xm.HORAS]
    return {"version": config.VERSION_CANDIDATO_CMG, "pronostico": pred, "cota90": _cota(h, semana, base, pred),
            "cmg_hasta": f"{cmg.fecha.max():%Y-%m-%d}",
            "cmg_publicado": {f"{f:%Y-%m-%d}": [float(x) for x in fila] for f, fila in horario.iterrows()},
            "variables": {v: float(dc.at[semana, v]) for v in variables[-2:]}}


def _huella_tabla(t):
    """SHA-256 del contenido de una tabla (índice y valores), independiente del archivo."""
    return hashlib.sha256(pd.util.hash_pandas_object(t, index=True).to_numpy().tobytes()).hexdigest()


def datos_reproduccion(modelo, completas, hist_cota, semana, pronostico, cota, cota_vol):
    """Lo necesario para reconstruir la emisión aunque XM revise los datos después.

    Con los coeficientes, el escalador y las variables del snapshot, el pronóstico se recalcula
    sin datos; las huellas dicen si la tabla de entrenamiento o los errores que calibran la cota
    siguen siendo los mismos.
    """
    import sklearn

    previos = hist_cota[hist_cota.index < semana].dropna(subset=["real", "prediccion"])
    out = {
        "n_entrenamiento": int(len(completas)),
        "entrenamiento_desde": f"{completas.index.min():%Y-%m-%d}" if len(completas) else None,
        "entrenamiento_hasta": f"{completas.index.max():%Y-%m-%d}" if len(completas) else None,
        "huella_entrenamiento": _huella_tabla(completas[config.VARIABLES + ["y"]]),
        "margen_log": float(np.log(cota / pronostico)),
        "margen_vol_log": float(np.log(cota_vol / pronostico)),
        "errores_cota": int(min(len(previos), config.VENTANA_CONFORMAL)),
        "huella_errores_cota": _huella_tabla(previos[["real", "prediccion"]].tail(config.VENTANA_CONFORMAL)),
        "versiones": {"numpy": np.__version__, "pandas": pd.__version__, "scikit-learn": sklearn.__version__},
    }
    if modelo is not None:
        esc, reg = modelo[0], modelo[-1]
        out["modelo"] = {"variables": list(config.VARIABLES), "intercepto": float(reg.intercept_),
                         "coeficientes": [float(c) for c in reg.coef_], "alpha": float(reg.alpha_),
                         "media": [float(m) for m in esc.mean_], "escala": [float(s) for s in esc.scale_]}
    return out


def reproducir(snapshot, precio_base):
    """Pronóstico y cotas a partir de un snapshot, sin datos ni reentrenar."""
    m = snapshot["reproduccion"]["modelo"]
    x = np.array([snapshot["variables"][v] for v in m["variables"]])
    z = (x - np.array(m["media"])) / np.array(m["escala"])
    pronostico = precio_base * float(np.exp(m["intercepto"] + z @ np.array(m["coeficientes"])))
    r = snapshot["reproduccion"]
    return pronostico, pronostico * np.exp(r["margen_log"]), pronostico * np.exp(r["margen_vol_log"])


def _alertas(d):
    umbrales = pd.read_csv(RAIZ / "results" / "alertas_resumen.csv").query("modelo == 'Logistica'")
    out = {}
    for e in alertas.EVENTOS:
        x = alertas.explicar(d, e.nombre)
        u = float(umbrales[umbrales.evento == e.nombre].umbral.iloc[0])
        out[e.nombre] = {"puntaje": x["prob_Logistica"], "umbral": u, "alerta": x["prob_Logistica"] >= u,
                         "semana_objetivo": x["semana_base"] + pd.Timedelta(weeks=e.horizonte),
                         "principales": {k: float(v) for k, v in x["top_Logistica"].items()}}
    return out


def emitir(fecha_emision=None, actualizar=True, guardar=True):
    """Pronóstico de la semana siguiente a la última semana completa publicada."""
    fecha_emision = pd.Timestamp(fecha_emision or pd.Timestamp.today()).normalize()
    if guardar and (malas := verificar_registro()):
        raise RuntimeError(f"El registro de pronósticos fue alterado en las semanas {malas}; revísalo antes de emitir.")
    fechas = actualizar_datos() if actualizar else ultimas_fechas()
    d = fe.preparar(dp.tabla_semanal(recalcular=actualizar, corregida=True))
    semana = d.index.max()
    fila = d.loc[semana]

    controles = monitoreo.calidad(d, semana, fecha_emision, datos_hasta=fechas)
    rango = monitoreo.fuera_de_rango(d, semana)
    hist = historial_fuera_de_muestra(d)
    hist["cota"] = cal.conformal(hist.real, hist.prediccion, nivel=config.NIVEL_COTA, ventana=config.VENTANA_CONFORMAL)
    desempeno = monitoreo.desempeno_reciente(hist)
    estado, motivos = monitoreo.estado(controles, rango, desempeno)

    base = float(fila.precio)
    completas = d.dropna(subset=config.VARIABLES + ["y"])
    completas = completas[completas.index < semana]
    modelo = None
    if estado == "respaldo":
        pronostico, intercepto, aportes = base, 0.0, pd.Series(dtype=float)
        hist_cota = hist.assign(prediccion=hist.ingenuo)
    else:
        modelo = models.ridge().fit(completas[config.VARIABLES], completas.y)
        pronostico = base * float(np.exp(modelo.predict(d.loc[[semana], config.VARIABLES])[0]))
        intercepto, aportes = contribuciones(modelo, fila)
        hist_cota = hist
    cota = _cota(hist_cota, semana, base, pronostico)
    cota_vol = _cota(hist_cota, semana, base, pronostico, escala=d.volatilidad_4s)
    reproduccion = datos_reproduccion(modelo, completas, hist_cota, semana, pronostico, cota, cota_vol)
    avisos = _alertas(d)

    # Un fallo del candidato nunca debe impedir la emisión oficial.
    cand = None
    if estado != "respaldo":
        try:
            cand = candidato(d, hist, semana, base, pronostico, recalcular=actualizar)
        except Exception as e:
            print(f"No se pudo calcular el candidato: {e}", flush=True)
    cand_cmg = None
    if estado != "respaldo":
        try:
            cand_cmg = candidato_cmg(d, semana, base, actualizar=actualizar)
        except Exception as e:
            print(f"No se pudo calcular el candidato con costo marginal: {e}", flush=True)

    resultado = {
        "fecha_emision": fecha_emision, "semana_base": semana, "semana_objetivo": semana + pd.Timedelta(weeks=1),
        "version_modelo": config.VERSION_MODELO, "estado": estado, "motivos": motivos,
        "datos_hasta": fechas, "precio_base": base, "pronostico": pronostico,
        "cambio_pct": (pronostico / base - 1) * 100, "cota90": cota, "cota90_vol": cota_vol, "ingenuo": base,
        "intercepto": intercepto, "aportes": aportes, "controles": controles, "fuera_de_rango": rango,
        "desempeno_reciente": desempeno, "alertas": avisos, "historial": hist,
        "variables": fila[config.VARIABLES].astype(float).to_dict(), "candidato": cand, "candidato_cmg": cand_cmg,
        "reproduccion": reproduccion,
    }
    if guardar:
        registrar(resultado)
        calificar(d)
    return resultado


def _leer_registro():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    # Las filas anteriores al candidato quedan sin esas columnas: no se llenan hacia atrás.
    reg = pd.read_csv(ARCHIVO, parse_dates=FECHAS).reindex(columns=COLUMNAS)
    # Una columna de texto o sí/no vacía se lee como float y luego no acepta sus valores.
    return reg.astype({c: object for c in ("motivos", "candidato_version", "huella", "cubierto", "candidato_cubierto",
                                           "candidato_cmg_version", "candidato_cmg_cubierto")})


FECHAS = ["fecha_emision", "semana_base", "semana_objetivo", "datos_precio_hasta", "fecha_calificacion"]


def _texto(v):
    if pd.isna(v):
        return ""
    if isinstance(v, pd.Timestamp):
        return f"{v:%Y-%m-%d}"
    return f"{v:.2f}" if isinstance(v, (float, np.floating)) else str(v)


def huella(fila, anterior=""):
    """SHA-256 de lo emitido, encadenado con la huella anterior: alterar una fila rompe la cadena."""
    columnas = COLUMNAS_SELLADAS + (SELLADAS_DESDE_CMG if _texto(fila.get("candidato_cmg_version")) else [])
    texto = anterior + "|" + "|".join(_texto(fila.get(c)) for c in columnas)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def verificar_registro():
    """Filas cuya huella no coincide (lista vacía si el registro está íntegro)."""
    reg, anterior, malas = _leer_registro(), "", []
    for _, fila in reg.iterrows():
        h = huella(fila, anterior)
        if fila.huella != h:
            malas.append(_texto(fila.semana_base))
        anterior = h
    return malas


def _escribir(reg):
    reg = reg.copy()
    for c in FECHAS:
        reg[c] = pd.to_datetime(reg[c]).dt.strftime("%Y-%m-%d")
    reg[COLUMNAS].to_csv(ARCHIVO, index=False)


def _json(v):
    """Tipos de numpy y pandas que json no serializa solo."""
    if isinstance(v, (np.integer, np.floating)):
        return None if isinstance(v, np.floating) and not np.isfinite(v) else v.item()
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return f"{v:%Y-%m-%d}"
    raise TypeError(f"No serializable: {type(v)}")


def registrar(r):
    """Agrega la emisión si su semana base no estaba registrada; nunca reescribe una existente."""
    REGISTRO.mkdir(exist_ok=True)
    reg = _leer_registro()
    if (reg.semana_base == r["semana_base"]).any():
        print(f"La semana base {r['semana_base']:%Y-%m-%d} ya está registrada; no se sobrescribe.")
        return False
    fila = {
        "fecha_emision": r["fecha_emision"], "semana_base": r["semana_base"], "semana_objetivo": r["semana_objetivo"],
        "version_modelo": r["version_modelo"], "estado": r["estado"], "motivos": " | ".join(r["motivos"]),
        "datos_precio_hasta": r["datos_hasta"]["precio"], "precio_base": round(r["precio_base"], 2),
        "pronostico": round(r["pronostico"], 2), "cambio_pct": round(r["cambio_pct"], 2),
        "cota90": round(r["cota90"], 2), "cota90_vol": round(r["cota90_vol"], 2), "ingenuo": round(r["ingenuo"], 2),
        **{f"alerta_{k}": round(v["puntaje"], 4) for k, v in r["alertas"].items()},
    }
    for prefijo in CANDIDATOS:
        if cand := r.get(prefijo):
            fila.update({f"{prefijo}_version": cand["version"], f"{prefijo}_pronostico": round(cand["pronostico"], 2),
                         f"{prefijo}_cota90": round(cand["cota90"], 2)})
    anterior = reg.huella.iloc[-1] if len(reg) and pd.notna(reg.huella.iloc[-1]) else ""
    fila["huella"] = huella({c: fila.get(c, np.nan) for c in COLUMNAS_SELLADAS + SELLADAS_DESDE_CMG}, anterior)
    _escribir(pd.concat([reg, pd.DataFrame([fila])], ignore_index=True))
    snap = REGISTRO / "snapshots" / f"{r['semana_base']:%Y-%m-%d}.json"
    snap.parent.mkdir(exist_ok=True)
    snap.write_text(json.dumps({
        "fecha_emision": f"{r['fecha_emision']:%Y-%m-%d}", "version_modelo": r["version_modelo"],
        "datos_hasta": {k: f"{v:%Y-%m-%d}" for k, v in r["datos_hasta"].items()},
        "variables": r["variables"], "estado": r["estado"], "motivos": r["motivos"],
        "controles": r["controles"].to_dict("records"), "candidato": r.get("candidato"),
        "candidato_cmg": r.get("candidato_cmg"),
        "precio_base": r["precio_base"], "pronostico": r["pronostico"], "cota90": r["cota90"], "cota90_vol": r["cota90_vol"],
        "desempeno_reciente": r.get("desempeno_reciente"), "reproduccion": r.get("reproduccion"),
    }, ensure_ascii=False, indent=2, default=_json), encoding="utf-8")
    print(f"Registrado: semana base {r['semana_base']:%Y-%m-%d}, pronóstico {r['pronostico']:,.1f} COP/kWh")
    return True


def calificar(d=None):
    """Completa real, error y cubierto en las emisiones cuya semana objetivo ya se publicó completa."""
    reg = _leer_registro()
    if reg.empty:
        return reg
    d = d if d is not None else dp.tabla_semanal(corregida=True)
    # Solo se califica con la demanda ya completa: si no, el precio real aún puede cambiar.
    if "dias_demanda_estimada" in d:
        firmes = d.index[d.dias_demanda_estimada == 0]
    else:
        firmes = d.index
    pendientes = reg.real.isna() & reg.semana_objetivo.isin(firmes)
    if pendientes.any():
        real = d.precio.reindex(reg.loc[pendientes, "semana_objetivo"]).to_numpy()
        reg.loc[pendientes, "real"] = np.round(real, 2)
        reg.loc[pendientes, "error"] = np.round(reg.loc[pendientes, "pronostico"] - real, 2)
        reg.loc[pendientes, "cubierto"] = real <= reg.loc[pendientes, "cota90"]
        reales = pd.Series(real, index=reg.index[pendientes])
        for p in CANDIDATOS:
            con = reales.index[reg.loc[reales.index, f"{p}_pronostico"].notna()]
            reg.loc[con, f"{p}_error"] = (reg.loc[con, f"{p}_pronostico"] - reales[con]).round(2)
            reg.loc[con, f"{p}_cubierto"] = reales[con] <= reg.loc[con, f"{p}_cota90"]
        reg.loc[pendientes, "fecha_calificacion"] = pd.Timestamp.today().normalize()
        _escribir(reg)
        print(f"Calificadas {int(pendientes.sum())} emisiones")
    return reg


if __name__ == "__main__":
    r = emitir(actualizar="--sin-actualizar" not in sys.argv[1:])
    print(f"Estado: {r['estado']}" + ("".join(f"\n  - {m}" for m in r["motivos"])))
    print(f"Semana {r['semana_objetivo']:%Y-%m-%d}: {r['pronostico']:,.1f} COP/kWh "
          f"({r['cambio_pct']:+.1f} %), cota 90 % {r['cota90']:,.1f}")
    if r["candidato"]:
        print(f"Candidato en paralelo: {r['candidato']['pronostico']:,.1f} COP/kWh, cota 90 % {r['candidato']['cota90']:,.1f}")
    if r["candidato_cmg"]:
        print(f"Candidato con costo marginal: {r['candidato_cmg']['pronostico']:,.1f} COP/kWh, "
              f"cota 90 % {r['candidato_cmg']['cota90']:,.1f}")
