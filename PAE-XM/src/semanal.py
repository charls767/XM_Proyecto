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
            "real", "error", "cubierto", "fecha_calificacion"]


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
    fechas = actualizar_datos() if actualizar else ultimas_fechas()
    d = fe.preparar(dp.tabla_semanal(recalcular=actualizar, corregida=True))
    semana = d.index.max()
    fila = d.loc[semana]

    controles = monitoreo.calidad(d, semana, fecha_emision)
    rango = monitoreo.fuera_de_rango(d, semana)
    hist = historial_fuera_de_muestra(d)
    hist["cota"] = cal.conformal(hist.real, hist.prediccion, nivel=config.NIVEL_COTA, ventana=config.VENTANA_CONFORMAL)
    desempeno = monitoreo.desempeno_reciente(hist)
    estado, motivos = monitoreo.estado(controles, rango, desempeno)

    base = float(fila.precio)
    completas = d.dropna(subset=config.VARIABLES + ["y"])
    completas = completas[completas.index < semana]
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
    avisos = _alertas(d)

    resultado = {
        "fecha_emision": fecha_emision, "semana_base": semana, "semana_objetivo": semana + pd.Timedelta(weeks=1),
        "version_modelo": config.VERSION_MODELO, "estado": estado, "motivos": motivos,
        "datos_hasta": fechas, "precio_base": base, "pronostico": pronostico,
        "cambio_pct": (pronostico / base - 1) * 100, "cota90": cota, "cota90_vol": cota_vol, "ingenuo": base,
        "intercepto": intercepto, "aportes": aportes, "controles": controles, "fuera_de_rango": rango,
        "desempeno_reciente": desempeno, "alertas": avisos, "historial": hist,
        "variables": fila[config.VARIABLES].astype(float).to_dict(),
    }
    if guardar:
        registrar(resultado)
        calificar(d)
    return resultado


def _leer_registro():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    return pd.read_csv(ARCHIVO, parse_dates=FECHAS)


FECHAS = ["fecha_emision", "semana_base", "semana_objetivo", "datos_precio_hasta", "fecha_calificacion"]


def _escribir(reg):
    reg = reg.copy()
    for c in FECHAS:
        reg[c] = pd.to_datetime(reg[c]).dt.strftime("%Y-%m-%d")
    reg[COLUMNAS].to_csv(ARCHIVO, index=False)


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
    _escribir(pd.concat([reg, pd.DataFrame([fila])], ignore_index=True))
    snap = REGISTRO / "snapshots" / f"{r['semana_base']:%Y-%m-%d}.json"
    snap.parent.mkdir(exist_ok=True)
    snap.write_text(json.dumps({
        "fecha_emision": f"{r['fecha_emision']:%Y-%m-%d}", "version_modelo": r["version_modelo"],
        "datos_hasta": {k: f"{v:%Y-%m-%d}" for k, v in r["datos_hasta"].items()},
        "variables": r["variables"], "estado": r["estado"], "motivos": r["motivos"],
        "controles": r["controles"].to_dict("records"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Registrado: semana base {r['semana_base']:%Y-%m-%d}, pronóstico {r['pronostico']:,.1f} COP/kWh")
    return True


def calificar(d=None):
    """Completa real, error y cubierto en las emisiones cuya semana objetivo ya se publicó completa."""
    reg = _leer_registro()
    if reg.empty:
        return reg
    d = d if d is not None else dp.tabla_semanal(corregida=True)
    pendientes = reg.real.isna() & reg.semana_objetivo.isin(d.index)
    if pendientes.any():
        reg["cubierto"] = reg["cubierto"].astype(object)  # vacía se lee como float; guarda sí/no
        real = d.precio.reindex(reg.loc[pendientes, "semana_objetivo"]).to_numpy()
        reg.loc[pendientes, "real"] = np.round(real, 2)
        reg.loc[pendientes, "error"] = np.round(reg.loc[pendientes, "pronostico"] - real, 2)
        reg.loc[pendientes, "cubierto"] = real <= reg.loc[pendientes, "cota90"]
        reg.loc[pendientes, "fecha_calificacion"] = pd.Timestamp.today().normalize()
        _escribir(reg)
        print(f"Calificadas {int(pendientes.sum())} emisiones")
    return reg


if __name__ == "__main__":
    r = emitir(actualizar="--sin-actualizar" not in sys.argv[1:])
    print(f"Estado: {r['estado']}" + ("".join(f"\n  - {m}" for m in r["motivos"])))
    print(f"Semana {r['semana_objetivo']:%Y-%m-%d}: {r['pronostico']:,.1f} COP/kWh "
          f"({r['cambio_pct']:+.1f} %), cota 90 % {r['cota90']:,.1f}")
