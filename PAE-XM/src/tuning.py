"""Búsqueda aleatoria de hiperparámetros con validación temporal interna.

Solo usa semanas base anteriores a `hasta` (por defecto, antes del inicio de la
evaluación en 2018), así que los hiperparámetros elegidos no conocen ninguna
semana evaluada. La métrica es el MAE del precio, no del cambio log.
"""

import json

import numpy as np
import pandas as pd
from sklearn.model_selection import ParameterSampler, TimeSeriesSplit

import backtesting as bt

ESPACIOS = {
    "lightgbm": {
        "n_estimators": [100, 200, 400, 800],
        "learning_rate": [0.01, 0.02, 0.05, 0.1],
        "num_leaves": [4, 8, 16, 31],
        "min_child_samples": [10, 20, 40, 80],
        "subsample": [0.6, 0.8, 1.0],
        "colsample_bytree": [0.5, 0.8, 1.0],
        "reg_lambda": [0.0, 1.0, 5.0, 20.0],
        "objective": ["regression", "regression_l1", "huber"],
    },
    "xgboost": {
        "n_estimators": [100, 200, 400, 800],
        "learning_rate": [0.01, 0.02, 0.05, 0.1],
        "max_depth": [2, 3, 4, 6],
        "min_child_weight": [1, 5, 10, 20],
        "subsample": [0.6, 0.8, 1.0],
        "colsample_bytree": [0.5, 0.8, 1.0],
        "reg_lambda": [0.0, 1.0, 5.0, 20.0],
        "objective": ["reg:squarederror", "reg:absoluteerror", "reg:pseudohubererror"],
    },
}


def mae_cv(fabrica, d, variables, cortes=5):
    """MAE del precio en cortes expansivos (TimeSeriesSplit) sobre `d`."""
    errores = []
    for ent, val in TimeSeriesSplit(cortes).split(d):
        a, b = d.iloc[ent], d.iloc[val]
        pred = b.precio * np.exp(fabrica().fit(a[variables], a.y).predict(b[variables]))
        errores.append((pred - b.precio_sig).abs())
    return pd.concat(errores).mean()


def buscar(familia, constructor, d, variables, hasta="2018-01-01", n=40, semilla=0):
    d = d.dropna(subset=variables + ["y"])
    d = d[d.index < hasta]
    filas = []
    for params in ParameterSampler(ESPACIOS[familia], n_iter=n, random_state=semilla):
        filas.append({**params, "MAE_cv": mae_cv(constructor(**params), d, variables)})
    t = pd.DataFrame(filas).sort_values("MAE_cv").reset_index(drop=True)
    t.to_csv(bt.RESULTADOS / f"tuning_{familia}.csv", index=False)
    mejor = t.iloc[0].drop("MAE_cv").to_dict()
    mejor = {k: (int(v) if isinstance(v, float) and v.is_integer() and k != "reg_lambda" else v)
             for k, v in mejor.items()}
    (bt.RESULTADOS / f"tuning_{familia}.json").write_text(json.dumps(mejor, indent=2))
    return mejor, t
