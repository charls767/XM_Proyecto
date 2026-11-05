"""Métricas de la sección 3 de la propuesta v2.0.

Todas reciben el formato ancho de `backtesting.ancho` (columnas `real`, `base` y
una por modelo) restringido a las semanas que se quieren evaluar.
"""

import numpy as np
import pandas as pd
from scipy import stats


def escala_mase(d, hasta="2021-12-31"):
    """MAE del pronóstico ingenuo en el periodo de desarrollo; escala fija del MASE."""
    dev = d[d.index <= hasta].dropna(subset=["precio", "precio_sig"])
    return (dev.precio_sig - dev.precio).abs().mean()


def puntuales(w, modelos, escala, referencia="Ingenuo"):
    filas = {}
    for m in modelos:
        e = w[m] - w.real
        filas[m] = {
            "MAE": e.abs().mean(),
            "RMSE": np.sqrt((e ** 2).mean()),
            "MASE": e.abs().mean() / escala,
            "WAPE_%": e.abs().sum() / w.real.sum() * 100,
            "MAPE_%": (e.abs() / w.real).mean() * 100,
            "sesgo": e.mean(),
        }
    t = pd.DataFrame(filas).T
    t["mejora_MAE_%"] = (1 - t.MAE / t.loc[referencia, "MAE"]) * 100
    return t


def diebold_mariano(w, modelo, referencia="Ingenuo"):
    """DM con pérdida absoluta, h=1. Estadístico negativo: el modelo erra menos."""
    dl = (w[modelo] - w.real).abs() - (w[referencia] - w.real).abs()
    est = dl.mean() / np.sqrt(dl.var(ddof=1) / len(dl))
    return est, 2 * stats.norm.sf(abs(est))


def ic_diferencia_mae(w, modelo, referencia="Ingenuo", bloque=8, n=2000, semilla=0):
    """IC 95 % por bootstrap de bloques móviles para MAE(modelo) − MAE(referencia)."""
    dl = ((w[modelo] - w.real).abs() - (w[referencia] - w.real).abs()).to_numpy()
    return ic_bootstrap(dl, bloque, n, semilla)


def ic_bootstrap(dl, bloque=8, n=2000, semilla=0):
    """IC 95 % de la media de una diferencia de pérdidas por bootstrap de bloques móviles."""
    dl = np.asarray(dl)
    rng = np.random.default_rng(semilla)
    k = int(np.ceil(len(dl) / bloque))
    inicios = rng.integers(0, len(dl) - bloque + 1, size=(n, k))
    idx = (inicios[..., None] + np.arange(bloque)).reshape(n, -1)[:, :len(dl)]
    medias = dl[idx].mean(axis=1)
    return np.percentile(medias, [2.5, 97.5])


def comparacion(w, modelos, referencia="Ingenuo"):
    filas = {}
    for m in modelos:
        if m == referencia:
            continue
        est, p = diebold_mariano(w, m, referencia)
        lo, hi = ic_diferencia_mae(w, m, referencia)
        filas[m] = {"dif_MAE": (w[m] - w.real).abs().mean() - (w[referencia] - w.real).abs().mean(),
                    "IC95_inf": lo, "IC95_sup": hi, "DM": est, "p_DM": p}
    return pd.DataFrame(filas).T


def pinball(w, columna, nivel=0.9):
    e = w.real - w[columna]
    return np.maximum(nivel * e, (nivel - 1) * e)


def comparacion_cotas(w, columnas, referencia, nivel=0.9):
    """Diferencia de pinball medio frente a la cota de referencia, con IC por bootstrap de bloques."""
    base = pinball(w, referencia, nivel)
    filas = {}
    for c in columnas:
        if c == referencia:
            continue
        dl = (pinball(w, c, nivel) - base).to_numpy()
        lo, hi = ic_bootstrap(dl)
        filas[c] = {"dif_pinball": dl.mean(), "IC95_inf": lo, "IC95_sup": hi}
    return pd.DataFrame(filas).T


def alta_variabilidad_ex_post(w, cuantil=0.8):
    """Semanas del quintil superior de |log(P_{s+1}/P_s)|. Definición del baseline;
    sirve para evaluar, no para decidir antes de emitir."""
    cambio = np.log(w.real / w.base).abs()
    return cambio >= cambio.quantile(cuantil)


def cotas(w, columnas, nivel=0.9, alta=None):
    """Cobertura, exceso de cota y pérdida pinball de cada cota superior."""
    alta = alta_variabilidad_ex_post(w) if alta is None else alta
    filas = {}
    for c in columnas:
        cubre = w.real <= w[c]
        e = w.real - w[c]
        filas[c] = {
            "cobertura": cubre.mean(),
            "cobertura_min_anual": cubre.groupby(w.index.year).mean().min(),
            "cobertura_normal": cubre[~alta].mean(),
            "cobertura_alta_var": cubre[alta].mean(),
            "exceso_medio_%": ((w[c] - w.real) / w.real)[cubre].mean() * 100,
            "faltante_medio_%": ((w.real - w[c]) / w.real)[~cubre].mean() * 100,
            "pinball": np.maximum(nivel * e, (nivel - 1) * e).mean(),
        }
    return pd.DataFrame(filas).T


def mae_por(w, modelos, grupos):
    return w[modelos].sub(w.real, axis=0).abs().groupby(grupos).mean()
