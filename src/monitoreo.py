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


def calidad(d, semana_base, fecha_emision, variables=None):
    """Controles de la semana base. estado: ok, aviso o falla."""
    variables = variables or config.VARIABLES
    fila = d.loc[semana_base]
    out = []
    faltan = [v for v in variables if pd.isna(fila.get(v))]
    out.append(_control("Variables completas", "falla" if faltan else "ok",
                        "Faltan: " + ", ".join(faltan) if faltan else f"{len(variables)} variables con dato"))
    atraso = (pd.Timestamp(fecha_emision) - (semana_base + pd.Timedelta(days=6))).days
    out.append(_control("Datos al día", "aviso" if atraso > config.ATRASO_MAXIMO_DIAS else "ok",
                        f"La semana base cerró hace {atraso} días"))
    p = fila.precio
    out.append(_control("Precio válido", "ok" if np.isfinite(p) and p > 0 else "falla", f"{p:,.1f} COP/kWh"))
    emb = fila.embalse_cierre
    out.append(_control("Embalse en rango físico", "ok" if 0 <= emb <= 1 else "falla", f"{emb:.1%}"))
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
    mae = (h.prediccion - h.real).abs().mean()
    mae_ing = (h.ingenuo - h.real).abs().mean()
    return {
        "semanas": len(h),
        "mae": float(mae),
        "mae_ingenuo": float(mae_ing),
        "razon_mae": float(mae / mae_ing) if mae_ing > 0 else np.nan,
        "cobertura": float((h.real <= h.cota).mean()),
        "sesgo": float((h.prediccion - h.real).mean()),
    }


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
    return ("vigilancia" if motivos else "normal"), motivos
