"""Controles antes de emitir y monitoreo del desempeño reciente.

El resultado se resume en un estado:
- normal: datos completos y el modelo funcionando como en su evaluación.
- vigilancia: el pronóstico se emite, pero hay algo que pide cautela (variables
  fuera del rango histórico, desempeño reciente bajo, datos algo atrasados).
- respaldo: falta información para el modelo; se emite el pronóstico ingenuo con
  una cota calibrada sobre sus propios errores.
"""

import numpy as np
import pandas as pd

import config


def _control(nombre, estado, detalle):
    return {"control": nombre, "estado": estado, "detalle": detalle}


def cobertura_series(semana_base, datos_hasta, series=None):
    """Control: cada serie del modelo llega al domingo de la semana base.

    Una variable puede tener dato aunque le falten días (p. ej. las ofertas, que se publican
    con más rezago que el precio), y entonces no es la misma que se usó al evaluar.
    'nota' si falta menos de DIAS_FALTANTES_AVISO días; 'aviso' desde ahí. None si no hay fechas.
    """
    if not datos_hasta:
        return None
    series = series or config.SERIES_SEMANA_BASE
    domingo = semana_base + pd.Timedelta(days=6)
    faltan = {}
    for s in series:
        hasta = datos_hasta.get(s)
        dias = 7 if hasta is None or pd.isna(hasta) else (domingo - pd.Timestamp(hasta).normalize()).days
        if dias > 0:
            faltan[s] = min(dias, 7)
    if not faltan:
        return _control("Series al día", "ok", f"Las {len(series)} series llegan al domingo de la semana base")
    peor = max(faltan.values())
    texto = ", ".join(f"{s} ({n} {'día' if n == 1 else 'días'})" for s, n in faltan.items())
    return _control("Series al día", "aviso" if peor >= config.DIAS_FALTANTES_AVISO else "nota",
                    f"Les faltan días de la semana base: {texto}; las variables se calcularon con los días publicados")


def calidad(d, semana_base, fecha_emision, variables=None, datos_hasta=None):
    """Controles de la semana base. estado: ok, nota (informativo), aviso o falla.

    `datos_hasta`: última fecha publicada de cada serie, para revisar que cubran la semana base.
    """
    variables = variables or config.VARIABLES
    fila = d.loc[semana_base]
    out = []
    faltan = [v for v in variables if pd.isna(fila.get(v))]
    out.append(_control("Variables completas", "falla" if faltan else "ok",
                        "Faltan: " + ", ".join(faltan) if faltan else f"{len(variables)} variables con dato"))
    if (series := cobertura_series(semana_base, datos_hasta)) is not None:
        out.append(series)
    atraso = (pd.Timestamp(fecha_emision) - (semana_base + pd.Timedelta(days=6))).days
    out.append(_control("Datos al día", "aviso" if atraso > config.ATRASO_MAXIMO_DIAS else "ok",
                        f"La semana base cerró hace {atraso} días"))
    p = fila.precio
    out.append(_control("Precio válido", "ok" if np.isfinite(p) and p > 0 else "falla", f"{p:,.1f} COP/kWh"))
    emb = fila.embalse_cierre
    out.append(_control("Embalse en rango físico", "ok" if 0 <= emb <= 1 else "falla", f"{emb:.1%}"))
    if 0 <= emb < config.EMBALSE_BAJO:
        out.append(_control("Régimen de embalse bajo", "aviso",
                            f"Embalse en {emb:.0%}: en este régimen no hay evidencia de que el modelo supere al ingenuo"))
    estimados = int(fila.get("dias_demanda_estimada", 0) or 0)
    out.append(_control("Demanda completa", "aviso" if estimados else "ok",
                        f"{estimados} {'día' if estimados == 1 else 'días'} de la semana base con demanda estimada a partir de la generación"
                        if estimados else "Demanda publicada completa"))
    if pd.notna(fila.get("precio_ant")) and fila.precio_ant > 0:
        salto = fila.precio / fila.precio_ant
        out.append(_control("Cambio semanal plausible", "aviso" if salto > 3 or salto < 1 / 3 else "ok",
                            f"{salto - 1:+.0%} frente a la semana anterior"))
    return pd.DataFrame(out)


def fuera_de_rango(d, semana_base, variables=None):
    """Variables de la semana base fuera de lo visto antes de ella.

    'extrapolacion' si cae fuera del mínimo-máximo histórico; 'extremo' si cae fuera
    de los percentiles 1–99. Ridge extrapola linealmente, pero su error crece ahí.
    """
    variables = variables or config.VARIABLES
    hist = d[d.index < semana_base][variables]
    fila = d.loc[semana_base, variables]
    out = []
    for v in variables:
        x, h = fila[v], hist[v].dropna()
        if pd.isna(x) or h.empty:
            continue
        if x < h.min() or x > h.max():
            nivel = "extrapolacion"
        elif x < h.quantile(0.01) or x > h.quantile(0.99):
            nivel = "extremo"
        else:
            continue
        out.append({"variable": v, "nombre": config.NOMBRES.get(v, v), "valor": float(x),
                    "minimo": float(h.min()), "maximo": float(h.max()), "nivel": nivel})
    return pd.DataFrame(out, columns=["variable", "nombre", "valor", "minimo", "maximo", "nivel"])


def desempeno_reciente(historial, semanas=None):
    """Error y cobertura de las últimas `semanas` ya calificadas.

    historial: columnas real, prediccion, ingenuo y cota, indexado por semana base.
    """
    semanas = semanas or config.VENTANA_MONITOREO
    h = historial.dropna(subset=["real", "prediccion"]).tail(semanas)
    if h.empty:
        return {"semanas": 0}
    e = h.prediccion - h.real
    mae = e.abs().mean()
    mae_ing = (h.ingenuo - h.real).abs().mean()
    return {
        "semanas": len(h),
        "mae": float(mae),
        "mae_ingenuo": float(mae_ing),
        "razon_mae": float(mae / mae_ing) if mae_ing > 0 else np.nan,
        "cobertura": float((h.real <= h.cota).mean()),
        "sesgo": float(e.mean()),
        "sesgo_pct": float(e.mean() / h.real.mean() * 100),
        "p_sesgo": _p_sesgo(e.to_numpy()),
    }


def _p_sesgo(e):
    """p de que el sesgo medio sea cero (Newey-West): los errores se agrupan en rachas."""
    import evaluation as ev
    if len(e) < 3:
        return np.nan
    if np.allclose(e, e[0]):  # sin variación: el sesgo es exacto
        return 0.0 if e[0] != 0 else 1.0
    return float(ev.dm_hac(e)[1])


def sesgo_significativo(desempeno):
    """El sesgo reciente supera SESGO_MAXIMO del precio y es significativo (las dos cosas)."""
    p = desempeno.get("p_sesgo", np.nan)
    return (abs(desempeno.get("sesgo_pct", 0.0)) > config.SESGO_MAXIMO * 100
            and pd.notna(p) and p < config.SESGO_P)


def estado(controles, rango, desempeno):
    """Estado y motivos, en lenguaje simple."""
    motivos = []
    if (controles.estado == "falla").any():
        motivos += [f"{c.control}: {c.detalle}" for c in controles.itertuples() if c.estado == "falla"]
        return "respaldo", motivos
    motivos += [f"{c.control}: {c.detalle}" for c in controles.itertuples() if c.estado == "aviso"]
    if not rango.empty and (rango.nivel == "extrapolacion").any():
        nombres = ", ".join(rango.loc[rango.nivel == "extrapolacion", "nombre"])
        motivos.append(f"Variables fuera de todo lo visto en la historia: {nombres}")
    if desempeno.get("semanas", 0) >= 8:
        if desempeno["razon_mae"] > config.RAZON_MAE_MAXIMA:
            motivos.append(f"En las últimas {desempeno['semanas']} semanas el modelo erró más que repetir el precio anterior")
        if desempeno["cobertura"] < config.COBERTURA_MINIMA:
            motivos.append(f"La cota cubrió solo el {desempeno['cobertura']:.0%} de las últimas {desempeno['semanas']} semanas")
        if sesgo_significativo(desempeno):
            lado = "se quedó corto" if desempeno["sesgo"] < 0 else "se pasó"
            motivos.append(f"En las últimas {desempeno['semanas']} semanas el modelo {lado} en promedio "
                           f"{abs(desempeno['sesgo']):,.1f} COP/kWh ({abs(desempeno['sesgo_pct']):.0f} % del precio), "
                           f"de forma significativa (p = {desempeno['p_sesgo']:.2f})")
    return ("vigilancia" if motivos else "normal"), motivos
