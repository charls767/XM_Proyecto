"""Calibración conformal de cotas superiores (escala log).

`conformal` es igual a `PAE/modelo.py::conformal` (baseline). Las variantes de la
Etapa 5 (por régimen y adaptativa) usan la misma convención: el margen de la fila
i solo usa puntajes de filas anteriores, cuyo precio real ya se conocía al emitir.
"""

import numpy as np


def conformal(real, pred, nivel=0.9, ventana=104, minimo=26, escala=None):
    """Cota superior: pred * exp(margen), con el margen calculado solo con puntajes previos.

    real, pred: series alineadas y ordenadas por semana base. El puntaje de la
    fila i es log(real_i / pred_i), dividido por `escala` si se da. Al emitir la
    fila i ya se conoce el real de la fila i-1, así que el margen usa las filas
    anteriores a i: cuantil corregido ceil((n+1)·nivel)/n de las últimas `ventana`
    (`None` = todas).
    """
    esc = np.ones(len(pred)) if escala is None else escala.reindex(pred.index).to_numpy()
    s = np.log(real / pred).to_numpy() / esc
    margen = np.full(len(s), np.nan)
    for i in range(minimo, len(s)):
        previos = s[0 if ventana is None else max(0, i - ventana):i]
        previos = previos[~np.isnan(previos)]
        margen[i] = _cuantil_corregido(previos, nivel)
    return pred * np.exp(margen * esc)


def _cuantil_corregido(previos, nivel):
    n = len(previos)
    return np.quantile(previos, min(1.0, np.ceil((n + 1) * nivel) / n), method="higher")


def conformal_regimen(real, pred, regimen, nivel=0.9, ventana=104, minimo=26):
    """Conformal Mondrian: el margen de la fila i usa solo puntajes previos del mismo
    régimen (las últimas `ventana` filas de ese régimen). `regimen` debe ser conocido
    al emitir. Si el régimen aún tiene menos de `minimo` puntajes, usa todos los previos."""
    s = np.log(real / pred).to_numpy()
    g = regimen.reindex(pred.index).to_numpy()
    margen = np.full(len(s), np.nan)
    for i in range(minimo, len(s)):
        previos, grupo = s[:i], g[:i]
        validos = ~np.isnan(previos)
        mismo = previos[validos & (grupo == g[i])]
        if len(mismo) >= minimo:
            margen[i] = _cuantil_corregido(mismo[-ventana:], nivel)
        else:
            margen[i] = _cuantil_corregido(previos[validos][-ventana:], nivel)
    return pred * np.exp(margen)


def conformal_adaptativo(real, pred, nivel=0.9, gamma=0.01, ventana=104, minimo=26, escala=None):
    """Conformal adaptativo (ACI, Gibbs y Candès, 2021).

    El nivel efectivo se corrige con cada incumplimiento observado:
    a_{i} = a_{i-1} + gamma·(err_{i-1} − (1 − nivel)), donde err = 1 si el real superó
    la cota. Al emitir la fila i ya se conoce si la fila i-1 se cubrió. Con a ≥ 1 se
    usa el máximo de los puntajes previos.
    """
    esc = np.ones(len(pred)) if escala is None else escala.reindex(pred.index).to_numpy()
    s = np.log(real / pred).to_numpy() / esc
    margen = np.full(len(s), np.nan)
    a = nivel
    for i in range(minimo, len(s)):
        if i > minimo and not np.isnan(s[i - 1]):
            fallo = float(s[i - 1] > margen[i - 1])
            a += gamma * (fallo - (1 - nivel))
        previos = s[max(0, i - ventana):i]
        previos = previos[~np.isnan(previos)]
        margen[i] = previos.max() if a >= 1 else _cuantil_corregido(previos, max(a, 0.0))
    return pred * np.exp(margen * esc)
