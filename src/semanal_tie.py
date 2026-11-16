"""Emisión semanal del precio para la garantía TIE, con registro inmutable.

Uso:
    python src/semanal_tie.py                          # actualiza datos, emite, registra y califica
    python src/semanal_tie.py --sin-actualizar         # usa la caché local
    python src/semanal_tie.py --fecha 2026-11-13 --seco  # prueba: no registra

Sigue la regla de la Resolución CREG 004 de 2003, art. 23: el viernes de la semana s (sábado a
viernes) se calcula la garantía de la semana s+2 con los precios horarios de la semana s-1.
- Regla XM: repetir el precio promedio horario de s-1.
- Modelo: Ridge con 11 variables de s-1 (sin ofertas) y el precio de sábado a martes de s,
  con corrección de sesgo de Duan y cota conformal del 90 % (E16).
- Respaldo: si faltan los días de s, el mismo Ridge sin ellos; si falta la semana s-1, no se emite.
- Candidato en paralelo: el mismo modelo más la hidrología de sábado a jueves de s y el precio del
  martes. Se registra a su lado y lo decide el registro: con 26 semanas calificadas reemplaza al
  modelo si erra menos y su cota cubre al menos 85 %.
- Precio de exportación (el que entra en la garantía, E19): promedio de un Huber sobre el cambio del
  precio de exportación y la regla de XM, en centUSD/kWh. Solo si en la semana s-1 se exportó.
- Vigilancia: hidrología atrasada, variables fuera de lo visto, o en las últimas 52 semanas calificadas
  un error mayor que la regla, cobertura bajo 80 % o sesgo significativo (lo pide la auditoría del
  15 de noviembre de 2026, hallazgo A1). La vigilancia no cambia el pronóstico: avisa.

Cada emisión agrega una fila a `registro/pronosticos_tie.csv` encadenada con SHA-256, y un snapshot
en `registro/snapshots_tie/`. Una semana ya registrada no se reescribe; solo se completan después
las columnas de calificación.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import backtesting as bt
import calibration as cal
import config
import data_pipeline as dp
import feature_engineering as fe
import models
import monitoreo
import semanal
import xm_client as xm

RAIZ = Path(__file__).resolve().parents[1]
REGISTRO = RAIZ / "registro"
ARCHIVO = REGISTRO / "pronosticos_tie.csv"
FECHAS = ["fecha_emision", "semana_calculo", "semana_base", "semana_objetivo", "datos_precio_hasta",
          "fecha_calificacion"]
COLUMNAS = ["fecha_emision", "semana_calculo", "semana_base", "semana_objetivo", "version_modelo", "estado",
            "motivos", "datos_precio_hasta", "precio_base", "precio_parcial", "regla_xm", "pronostico",
            "cambio_pct", "cota90", "real", "error", "error_regla", "cubierto", "fecha_calificacion",
            "candidato_version", "candidato_pronostico", "candidato_cota90", "candidato_error", "candidato_cubierto",
            "expo_version", "expo_regla", "expo_pronostico", "expo_cota90", "expo_real", "expo_error",
            "expo_error_regla", "expo_cubierto", "huella"]
SELLADAS = ["fecha_emision", "semana_calculo", "semana_base", "semana_objetivo", "version_modelo", "estado",
            "motivos", "precio_base", "precio_parcial", "regla_xm", "pronostico", "cota90",
            "candidato_version", "candidato_pronostico", "candidato_cota90",
            "expo_version", "expo_regla", "expo_pronostico", "expo_cota90"]


def semanas(fecha_emision):
    """Semana de cálculo s (su sábado), semana base s-1 y semana objetivo s+2."""
    f = pd.Timestamp(fecha_emision).normalize()
    s = f - pd.Timedelta(days=(f.dayofweek - 5) % 7)
    return s, s - pd.Timedelta(weeks=1), s + pd.Timedelta(weeks=2)


def _pronosticar(d, base, variables):
    """Ridge con Duan entrenado con las filas cuyo objetivo ya se conoce, su cota conformal y
    el historial fuera de muestra para el monitoreo.

    Devuelve el pronóstico, la cota, los datos para reproducirlo sin reentrenar y el historial.
    """
    completas = d.dropna(subset=variables + ["y"])
    entren = completas[completas.index < base - pd.Timedelta(weeks=dp.HORIZONTE_TIE - 1)]
    est = models.ridge().fit(entren[variables], entren.y)
    factor = float(np.mean(np.exp(entren.y.to_numpy() - est.predict(entren[variables]))))
    precio_base = float(d.at[base, "precio"])
    pred = precio_base * float(np.exp(est.predict(d.loc[[base], variables])[0])) * factor

    # Errores fuera de muestra con el mismo esquema que E16, para calibrar la cota y monitorear.
    modelo = models.Duan("tie", variables, models.ridge)
    r = bt.backtest(completas, [modelo], inicio=config.INICIO_BACKTEST, cada=4, embargo=dp.HORIZONTE_TIE - 1)
    w = bt.ancho(r)
    w = w[w.index < base]
    h = pd.concat([pd.DataFrame({"real": w.real, "prediccion": w.tie, "ingenuo": w.base}),
                   pd.DataFrame({"real": [np.nan], "prediccion": [pred], "ingenuo": [precio_base]}, index=[base])])
    h["cota"] = cal.conformal(h.real, h.prediccion, nivel=config.NIVEL_COTA, ventana=config.VENTANA_CONFORMAL,
                              rezago=dp.HORIZONTE_TIE)
    cota = float(h.cota.iloc[-1])
    esc, reg = est[0], est[-1]
    reproduccion = {"variables": list(variables), "media": [float(m) for m in esc.mean_],
                    "escala": [float(s) for s in esc.scale_], "intercepto": float(reg.intercept_),
                    "coeficientes": [float(c) for c in reg.coef_], "alpha": float(reg.alpha_),
                    "factor_duan": factor, "margen_log": float(np.log(cota / pred)),
                    "n_entrenamiento": len(entren), "entrenamiento_hasta": f"{entren.index.max():%Y-%m-%d}"}
    return pred, cota, reproduccion, h.iloc[:-1]


def pronosticar_expo(dx, base):
    """Precio de exportación de s+2 (centUSD/kWh): promedio de Huber y la regla de XM (E19).

    `dx` es `fe.preparar_expo(dp.tabla_expo())`. Devuelve None si en la semana base no se exportó.
    """
    if base not in dx.index or pd.isna(dx.at[base, "precio"]):
        return None
    variables = config.VARIABLES_EXPO
    completas = dx.dropna(subset=variables + ["y"])
    entren = completas[completas.index < base - pd.Timedelta(weeks=dp.HORIZONTE_TIE - 1)]
    est = models.huber().fit(entren[variables], entren.y)
    regla = float(dx.at[base, "precio"])
    huber = regla * float(np.exp(est.predict(dx.loc[[base], variables])[0]))
    pred = (huber + regla) / 2
    r = bt.backtest(completas, [models.Modelo("huber", variables, models.huber)], inicio=config.INICIO_BACKTEST,
                    cada=4, embargo=dp.HORIZONTE_TIE - 1)
    w = bt.ancho(r)
    w = w[w.index < base]
    h = pd.concat([pd.DataFrame({"real": w.real, "prediccion": (w.huber + w.base) / 2}),
                   pd.DataFrame({"real": [np.nan], "prediccion": [pred]}, index=[base])])
    # Cota calibrada por régimen regulatorio de exportación (E20).
    regimen = pd.Series(dp.regimen_exportacion(h.index), index=h.index)
    cota = float(cal.conformal_regimen(h.real, h.prediccion, regimen, nivel=config.NIVEL_COTA,
                                       ventana=config.VENTANA_CONFORMAL, rezago=dp.HORIZONTE_TIE,
                                       minimo_grupo=config.MINIMO_GRUPO_REGIMEN).iloc[-1])
    esc, reg = est[0], est[-1]
    return {"version": config.VERSION_EXPO, "regla": regla, "pronostico": pred, "cota90": cota,
            "regimen_especial": bool(regimen.iloc[-1]),
            "variables": {v: float(dx.at[base, v]) for v in variables},
            "reproduccion": {"variables": list(variables), "media": [float(m) for m in esc.mean_],
                             "escala": [float(s) for s in esc.scale_], "intercepto": float(reg.intercept_),
                             "coeficientes": [float(c) for c in reg.coef_], "margen_log": float(np.log(cota / pred)),
                             "n_entrenamiento": len(entren), "entrenamiento_hasta": f"{entren.index.max():%Y-%m-%d}"}}


def reproducir_expo(expo):
    """Pronóstico y cota de exportación a partir de lo guardado, sin datos ni reentrenar."""
    m = expo["reproduccion"]
    x = np.array([expo["variables"][v] for v in m["variables"]])
    z = (x - np.array(m["media"])) / np.array(m["escala"])
    pred = (expo["regla"] * float(np.exp(m["intercepto"] + z @ np.array(m["coeficientes"]))) + expo["regla"]) / 2
    return pred, pred * float(np.exp(m["margen_log"]))


def reproducir(snapshot):
    """Pronóstico y cota a partir de un snapshot TIE, sin datos ni reentrenar."""
    m = snapshot["reproduccion"]
    x = np.array([snapshot["variables"][v] for v in m["variables"]])
    z = (x - np.array(m["media"])) / np.array(m["escala"])
    pred = snapshot["precio_base"] * float(np.exp(m["intercepto"] + z @ np.array(m["coeficientes"]))) * m["factor_duan"]
    return pred, pred * float(np.exp(m["margen_log"]))


def emitir(fecha_emision=None, actualizar=True, guardar=True):
    fecha_emision = pd.Timestamp(fecha_emision or pd.Timestamp.today()).normalize()
    if guardar and (malas := verificar_registro()):
        raise RuntimeError(f"El registro TIE fue alterado en las semanas {malas}; revísalo antes de emitir.")
    fechas = semanal.actualizar_datos() if actualizar else semanal.ultimas_fechas()
    # Las series de exportación también se actualizan: el precio de la garantía sale de ellas.
    for n in dp.SERIES_EXPO_TODAS:
        fechas[n] = xm.descargar(n).fecha.max() if actualizar else xm.ultima_fecha_en_cache(n)
    d = fe.preparar(dp.tabla_tie(recalcular=True))
    s, base, objetivo = semanas(fecha_emision)
    if base not in d.index or pd.isna(d.at[base, "precio"]):
        raise RuntimeError(f"La semana base {base:%Y-%m-%d} aún no está completa (precio hasta "
                           f"{fechas['precio']:%Y-%m-%d}); no se emite.")

    motivos = []
    variables = config.VARIABLES_TIE
    faltan = [v for v in variables if pd.isna(d.at[base, v])]
    estado = "normal"
    if faltan:
        variables = [v for v in config.VARIABLES_TIE_RESPALDO if pd.notna(d.at[base, v])]
        estado = "respaldo"
        motivos.append(f"Faltan: {', '.join(faltan)}")
    # Hidrología al día: el viernes debería llegar al menos al martes de la semana s.
    limite = s + pd.Timedelta(days=dp.DIAS_PARCIALES_TIE - 1)
    atrasadas = [f"{k} hasta {fechas[k]:%Y-%m-%d}" for k in ("aportes", "volumen_pct")
                 if k in fechas and pd.notna(fechas[k]) and fechas[k] < limite]
    if atrasadas:
        motivos.append("Series atrasadas: " + ", ".join(atrasadas))
    pred, cota, reproduccion, hist = _pronosticar(d, base, variables)
    rango = monitoreo.fuera_de_rango(d, base, variables)
    if (rango.nivel == "extrapolacion").any():
        motivos.append("Variables fuera de todo lo visto en la historia: "
                       + ", ".join(rango.loc[rango.nivel == "extrapolacion", "nombre"]))
    desempeno = monitoreo.desempeno_reciente(hist, semanas=52)
    if desempeno.get("semanas", 0) >= 8:
        if desempeno["razon_mae"] > config.RAZON_MAE_MAXIMA:
            motivos.append(f"En las últimas {desempeno['semanas']} semanas el modelo erró más que la regla de XM")
        if desempeno["cobertura"] < config.COBERTURA_MINIMA:
            motivos.append(f"La cota cubrió solo el {desempeno['cobertura']:.0%} de las últimas {desempeno['semanas']} semanas")
        if monitoreo.sesgo_significativo(desempeno):
            lado = "se quedó corto" if desempeno["sesgo"] < 0 else "se pasó"
            motivos.append(f"En las últimas {desempeno['semanas']} semanas el modelo {lado} en promedio "
                           f"{abs(desempeno['sesgo']):,.1f} COP/kWh ({abs(desempeno['sesgo_pct']):.0f} % del precio), "
                           f"de forma significativa (p = {desempeno['p_sesgo']:.2f})")
    if estado == "normal" and motivos:
        estado = "vigilancia"
    fila = d.loc[base]
    r = {
        "fecha_emision": fecha_emision, "semana_calculo": s, "semana_base": base, "semana_objetivo": objetivo,
        "version_modelo": config.VERSION_TIE + ("-respaldo" if estado == "respaldo" else ""),
        "estado": estado, "motivos": motivos, "datos_hasta": fechas,
        "precio_base": float(fila.precio), "precio_parcial": float(fila.precio_parcial) if pd.notna(fila.precio_parcial) else None,
        "regla_xm": float(fila.precio), "pronostico": pred, "cambio_pct": (pred / fila.precio - 1) * 100, "cota90": cota,
        "variables": {v: float(fila[v]) for v in variables}, "reproduccion": reproduccion,
        "desempeno_reciente": desempeno, "fuera_de_rango": rango.to_dict("records"),
    }
    # Candidato en paralelo: no cambia el pronóstico registrado y una falla suya no detiene la emisión.
    r["candidato"] = None
    faltan_c = [v for v in config.VARIABLES_TIE_CANDIDATO if pd.isna(d.at[base, v])]
    if faltan_c:
        print(f"Candidato sin calcular: faltan {', '.join(faltan_c)}", flush=True)
    else:
        try:
            p_c, c_c, rep_c, _ = _pronosticar(d, base, config.VARIABLES_TIE_CANDIDATO)
            r["candidato"] = {"version": config.VERSION_TIE_CANDIDATO, "pronostico": p_c, "cota90": c_c,
                              "variables": {v: float(fila[v]) for v in config.VARIABLES_TIE_CANDIDATO},
                              "reproduccion": rep_c}
        except Exception as e:
            print(f"No se pudo calcular el candidato: {e}", flush=True)
    # Precio de exportación (el de la garantía, E19). Sin exportaciones en s-1 no hay precio base.
    r["expo"] = None
    try:
        r["expo"] = pronosticar_expo(fe.preparar_expo(dp.tabla_expo(recalcular=True)), base)
        if r["expo"] is None:
            corte = min(fechas[n] for n in dp.SERIES_EXPO)
            if pd.isna(corte) or corte < base + pd.Timedelta(days=6):
                r["motivos"].append(f"Exportaciones publicadas solo hasta {corte:%Y-%m-%d}: la semana base no está "
                                    "completa y no se pronostica el precio de exportación")
            else:
                r["motivos"].append("Sin exportaciones en la semana base (menos de 1 GWh): no hay precio de "
                                    "exportación que pronosticar")
    except Exception as e:
        print(f"No se pudo calcular el precio de exportación: {e}", flush=True)
    if guardar:
        registrar(r)
        calificar(d)
        if actualizar:
            # El registro a una semana ya no emite, pero sus filas se siguen calificando.
            semanal.calificar(dp.tabla_semanal(recalcular=True, corregida=True))
    return r


def _texto(v):
    return semanal._texto(v)


def huella(fila, anterior=""):
    texto = anterior + "|" + "|".join(_texto(fila.get(c)) for c in SELLADAS)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _leer_registro():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    reg = pd.read_csv(ARCHIVO, parse_dates=FECHAS).reindex(columns=COLUMNAS)
    return reg.astype({c: object for c in ("motivos", "huella", "cubierto", "candidato_version", "candidato_cubierto",
                                           "expo_version", "expo_cubierto")})


def _escribir(reg):
    reg = reg.copy()
    for c in FECHAS:
        reg[c] = pd.to_datetime(reg[c]).dt.strftime("%Y-%m-%d")
    reg[COLUMNAS].to_csv(ARCHIVO, index=False)


def verificar_registro():
    reg, anterior, malas = _leer_registro(), "", []
    for _, fila in reg.iterrows():
        h = huella(fila, anterior)
        if fila.huella != h:
            malas.append(_texto(fila.semana_base))
        anterior = h
    return malas


def registrar(r):
    REGISTRO.mkdir(exist_ok=True)
    reg = _leer_registro()
    if (reg.semana_base == r["semana_base"]).any():
        print(f"La semana base {r['semana_base']:%Y-%m-%d} ya está registrada; no se sobrescribe.")
        return False
    fila = {k: r[k] for k in ("fecha_emision", "semana_calculo", "semana_base", "semana_objetivo",
                              "version_modelo", "estado")}
    fila.update({"motivos": " | ".join(r["motivos"]), "datos_precio_hasta": r["datos_hasta"]["precio"],
                 "precio_base": round(r["precio_base"], 2),
                 "precio_parcial": round(r["precio_parcial"], 2) if r["precio_parcial"] is not None else np.nan,
                 "regla_xm": round(r["regla_xm"], 2), "pronostico": round(r["pronostico"], 2),
                 "cambio_pct": round(r["cambio_pct"], 2), "cota90": round(r["cota90"], 2)})
    if cand := r.get("candidato"):
        fila.update({"candidato_version": cand["version"], "candidato_pronostico": round(cand["pronostico"], 2),
                     "candidato_cota90": round(cand["cota90"], 2)})
    if expo := r.get("expo"):
        fila.update({"expo_version": expo["version"], "expo_regla": round(expo["regla"], 2),
                     "expo_pronostico": round(expo["pronostico"], 2), "expo_cota90": round(expo["cota90"], 2)})
    anterior = reg.huella.iloc[-1] if len(reg) and pd.notna(reg.huella.iloc[-1]) else ""
    fila["huella"] = huella(fila, anterior)
    _escribir(pd.concat([reg, pd.DataFrame([fila])], ignore_index=True))
    snap = REGISTRO / "snapshots_tie" / f"{r['semana_base']:%Y-%m-%d}.json"
    snap.parent.mkdir(exist_ok=True)
    snap.write_text(json.dumps({**{k: v for k, v in r.items() if k != "datos_hasta"},
                                "datos_hasta": {k: f"{v:%Y-%m-%d}" for k, v in r["datos_hasta"].items()}},
                               ensure_ascii=False, indent=2, default=semanal._json), encoding="utf-8")
    print(f"Registrado TIE: semana objetivo {r['semana_objetivo']:%Y-%m-%d}, pronóstico {r['pronostico']:,.1f} COP/kWh")
    return True


def calificar(d=None):
    """Completa real y errores cuando la semana objetivo ya tiene sus 168 horas publicadas."""
    reg = _leer_registro()
    if reg.empty:
        return reg
    d = d if d is not None else dp.tabla_tie()
    pendientes = reg.real.isna() & reg.semana_objetivo.isin(d.index[d.precio.notna()])
    if pendientes.any():
        real = d.precio.reindex(reg.loc[pendientes, "semana_objetivo"]).to_numpy()
        reg.loc[pendientes, "real"] = np.round(real, 2)
        reg.loc[pendientes, "error"] = np.round(reg.loc[pendientes, "pronostico"] - real, 2)
        reg.loc[pendientes, "error_regla"] = np.round(reg.loc[pendientes, "regla_xm"] - real, 2)
        reg.loc[pendientes, "cubierto"] = real <= reg.loc[pendientes, "cota90"]
        reales = pd.Series(real, index=reg.index[pendientes])
        con = reales.index[reg.loc[reales.index, "candidato_pronostico"].notna()]
        reg.loc[con, "candidato_error"] = (reg.loc[con, "candidato_pronostico"] - reales[con]).round(2)
        reg.loc[con, "candidato_cubierto"] = reales[con] <= reg.loc[con, "candidato_cota90"]
        # Precio de exportación real de la semana objetivo, si se exportó.
        expo = dp.tabla_expo().precio_expo.reindex(reg.loc[pendientes, "semana_objetivo"]).to_numpy()
        reg.loc[pendientes, "expo_real"] = np.round(expo, 3)
        c2 = reales.index[reg.loc[reales.index, "expo_pronostico"].notna() & ~np.isnan(expo)]
        e2 = pd.Series(expo, index=reales.index)
        reg.loc[c2, "expo_error"] = (reg.loc[c2, "expo_pronostico"] - e2[c2]).round(3)
        reg.loc[c2, "expo_error_regla"] = (reg.loc[c2, "expo_regla"] - e2[c2]).round(3)
        reg.loc[c2, "expo_cubierto"] = e2[c2] <= reg.loc[c2, "expo_cota90"]
        reg.loc[pendientes, "fecha_calificacion"] = pd.Timestamp.today().normalize()
        _escribir(reg)
        print(f"Calificadas {int(pendientes.sum())} emisiones TIE")
    return reg


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--sin-actualizar", action="store_true")
    a.add_argument("--seco", action="store_true", help="no registra ni califica")
    a.add_argument("--fecha", help="fecha de emisión (AAAA-MM-DD); por defecto hoy")
    o = a.parse_args()
    r = emitir(o.fecha, actualizar=not o.sin_actualizar, guardar=not o.seco)
    print(f"Estado: {r['estado']}" + "".join(f"\n  - {m}" for m in r["motivos"]))
    print(f"Semana TIE {r['semana_objetivo']:%Y-%m-%d} a {r['semana_objetivo'] + pd.Timedelta(days=6):%Y-%m-%d}: "
          f"{r['pronostico']:,.1f} COP/kWh ({r['cambio_pct']:+.1f} %), cota 90 % {r['cota90']:,.1f}; "
          f"regla XM {r['regla_xm']:,.1f}")
    if r["candidato"]:
        print(f"Candidato en paralelo: {r['candidato']['pronostico']:,.1f} COP/kWh, "
              f"cota 90 % {r['candidato']['cota90']:,.1f}")
    if r["expo"]:
        print(f"Precio de exportación (garantía): {r['expo']['pronostico']:,.2f} centUSD/kWh, "
              f"cota 90 % {r['expo']['cota90']:,.2f}; regla XM {r['expo']['regla']:,.2f}")
