"""Catálogo de modelos para los experimentos (E0, E1, ...).

Todos los modelos con estimador aprenden y = log(P_{s+1}/P_s) y pronostican
P_s * exp(ŷ); las referencias (ingenuo, estacional) devuelven un precio directo.
"""

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import ElasticNetCV, QuantileRegressor, RidgeCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from feature_engineering import VARIABLES


@dataclass
class Modelo:
    nombre: str
    variables: list = field(default_factory=list)
    fabrica: Callable | None = None  # None: referencia sin entrenamiento
    columna_referencia: str = "precio"

    def ajustar_predecir(self, entren, prueba):
        if self.fabrica is None:
            return prueba[self.columna_referencia].to_numpy()
        est = self.fabrica().fit(entren[self.variables], entren.y)
        return prueba.precio.to_numpy() * np.exp(est.predict(prueba[self.variables]))


def ridge():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30)))


def elasticnet():
    """Penalización y mezcla L1/L2 elegidas con validación temporal interna (5 cortes)."""
    return make_pipeline(StandardScaler(), ElasticNetCV(
        l1_ratio=[0.1, 0.5, 0.9, 1.0], alphas=50, cv=TimeSeriesSplit(5), max_iter=20000))


def gboost():
    return HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.03, max_depth=3, min_samples_leaf=20,
        l2_regularization=1.0, random_state=0)


def lightgbm(**params):
    from lightgbm import LGBMRegressor
    base = dict(n_estimators=300, learning_rate=0.03, num_leaves=8, min_child_samples=20,
                subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                random_state=0, deterministic=True, force_row_wise=True, n_jobs=4, verbose=-1)
    return lambda: LGBMRegressor(**{**base, **params})


def xgboost(**params):
    from xgboost import XGBRegressor
    base = dict(n_estimators=300, learning_rate=0.03, max_depth=3, min_child_weight=5,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, tree_method="hist",
                random_state=0, n_jobs=4)
    return lambda: XGBRegressor(**{**base, **params})


def cuantil_lineal(q, alpha=0.0):
    """Regresión cuantílica lineal sobre y = log(P_{s+1}/P_s), con penalización L1 `alpha`."""
    return lambda: make_pipeline(StandardScaler(), QuantileRegressor(quantile=q, alpha=alpha, solver="highs"))


def lightgbm_cuantil(q):
    from lightgbm import LGBMRegressor
    return lambda: LGBMRegressor(objective="quantile", alpha=q, n_estimators=300, learning_rate=0.03,
                                 num_leaves=8, min_child_samples=20, subsample=0.8, subsample_freq=1,
                                 colsample_bytree=0.8, random_state=0, deterministic=True,
                                 force_row_wise=True, n_jobs=4, verbose=-1)


def gboost_cuantil(q):
    return lambda: HistGradientBoostingRegressor(
        loss="quantile", quantile=q, max_iter=300, learning_rate=0.03, max_depth=3,
        min_samples_leaf=20, random_state=0)


# E0: referencias. E1: baseline de PAE/modelo.py con las mismas variables e hiperparámetros.
E0 = [
    Modelo("Ingenuo"),
    Modelo("Estacional", columna_referencia="precio_hace_51"),
]
E1 = [
    Modelo("Ridge", VARIABLES, ridge),
    Modelo("GBoost", VARIABLES, gboost),
    Modelo("GBoost_q90", VARIABLES, gboost_cuantil(0.9)),
]


class DosEtapas:
    """Modelo en dos etapas (hurdle), como el de Herrera-Mejía et al. (2026).

    Etapa 1: regresión logística multinomial que clasifica la semana s+1 en baja
    (y ≤ log 0.8), normal o subida (y ≥ log 1.25). La penalización C = 0.01 se eligió
    por log-loss con validación temporal usando solo semanas anteriores a 2018
    (`results/tuning_dosetapas.json`); elegirla en cada bloque con LogisticRegressionCV
    hacía el walk-forward cientos de veces más lento.
    Etapa 2: un Ridge por régimen, entrenado solo con las semanas de ese régimen.

    Modos de combinación:
    - "media": log(Σ p_k exp(ŷ_k)), la media del precio bajo la mezcla.
    - "duro": la regresión del régimen más probable.
    - "apilado": Ridge sobre las variables de regresión más p(baja) y p(subida); las
      probabilidades de entrenamiento son fuera de muestra (cortes temporales) para
      que Ridge no aprenda de probabilidades sobreajustadas.
    """

    UMBRALES = (np.log(0.8), np.log(1.25))

    def __init__(self, nombre, variables, variables_clf, modo="media", minimo_regimen=20, C=0.01):
        self.nombre, self.modo, self.minimo, self.C = nombre, modo, minimo_regimen, C
        self.vars_reg, self.vars_clf = list(variables), list(variables_clf)
        self.variables = list(dict.fromkeys(self.vars_reg + self.vars_clf))

    def _clasificador(self):
        from sklearn.linear_model import LogisticRegression
        return make_pipeline(StandardScaler(), LogisticRegression(C=self.C, max_iter=5000))

    def _regimen(self, y):
        return np.digitize(y, self.UMBRALES)  # 0 baja, 1 normal, 2 subida

    def _probabilidades(self, clf, X):
        p = np.zeros((len(X), 3))
        p[:, clf[-1].classes_] = clf.predict_proba(X)
        return p

    def ajustar_predecir(self, entren, prueba):
        c = self._regimen(entren.y.to_numpy())
        clf = self._clasificador().fit(entren[self.vars_clf], c)
        p = self._probabilidades(clf, prueba[self.vars_clf])
        if self.modo == "apilado":
            oof = np.full((len(entren), 3), np.nan)
            for a, b in TimeSeriesSplit(5).split(entren):
                if len(np.unique(c[a])) < 3:
                    continue
                m = self._clasificador().fit(entren[self.vars_clf].iloc[a], c[a])
                oof[b] = self._probabilidades(m, entren[self.vars_clf].iloc[b])
            ok = ~np.isnan(oof[:, 0])
            Xe = np.column_stack([entren[self.vars_reg].to_numpy()[ok], oof[ok][:, [0, 2]]])
            reg = ridge().fit(Xe, entren.y.to_numpy()[ok])
            yhat = reg.predict(np.column_stack([prueba[self.vars_reg].to_numpy(), p[:, [0, 2]]]))
            return prueba.precio.to_numpy() * np.exp(yhat)
        global_ = ridge().fit(entren[self.vars_reg], entren.y)
        por_regimen = []
        for k in range(3):
            filas = c == k
            m = ridge().fit(entren[self.vars_reg][filas], entren.y[filas]) if filas.sum() >= self.minimo else global_
            por_regimen.append(m.predict(prueba[self.vars_reg]))
        yk = np.column_stack(por_regimen)
        if self.modo == "duro":
            yhat = yk[np.arange(len(yk)), p.argmax(axis=1)]
        else:
            yhat = np.log((p * np.exp(yk)).sum(axis=1))
        return prueba.precio.to_numpy() * np.exp(yhat)
