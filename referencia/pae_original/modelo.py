"""Pronóstico de P_{s+1} con validación walk-forward (ventana expansiva).

Se modela el cambio logarítmico y = log(P_{s+1} / P_s) y el pronóstico es
P_s * exp(ŷ). Así la referencia ingenua (P_{s+1} = P_s) equivale a ŷ = 0 y los
modelos solo tienen que explicar la desviación respecto a ella.
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

VARIABLES = [
    "log_precio", "momentum", "cv_diario", "ultimo_dia_rel", "max_h_rel",
    "embalse_cierre", "embalse_cambio", "aportes_pct_media", "aportes_pct_media_4s",
    "log_oferta_termica", "log_oferta_no_termica", "brecha_oferta_nt",
    "fut", "participacion_termica",
    "oni", "oni_rezago", "fase_enos",
    "sen_semana", "cos_semana",
]


GRUPOS = {
    "precio": ["log_precio", "momentum", "cv_diario", "ultimo_dia_rel", "max_h_rel"],
    "hidrologia": ["embalse_cierre", "embalse_cambio", "aportes_pct_media", "aportes_pct_media_4s"],
    "ofertas": ["log_oferta_termica", "log_oferta_no_termica", "brecha_oferta_nt"],
    "termica": ["fut", "participacion_termica"],
    "enos": ["oni", "oni_rezago", "fase_enos"],
    "calendario": ["sen_semana", "cos_semana"],
}


def preparar(sem):
    d = sem.copy()
    d["log_precio"] = np.log(d.precio)
    d["momentum"] = np.log(d.precio / d.precio_ant)
    d["cv_diario"] = d.precio_std_diaria / d.precio
    d["ultimo_dia_rel"] = np.log(d.precio_ultimo_dia / d.precio)
    d["max_h_rel"] = np.log(d.precio_max_h / d.precio)
    d["log_oferta_termica"] = np.log(d.oferta_termica)
    d["log_oferta_no_termica"] = np.log(d.oferta_no_termica)
    d["brecha_oferta_nt"] = np.log(d.oferta_no_termica / d.precio)
    d["y"] = np.log(d.precio_sig / d.precio)
    return d


def modelos():
    return {
        "Ridge": make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30))),
        "GBoost": HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.03, max_depth=3, min_samples_leaf=20,
            l2_regularization=1.0, random_state=0),
    }


def cuantil(q):
    return HistGradientBoostingRegressor(
        loss="quantile", quantile=q, max_iter=300, learning_rate=0.03, max_depth=3,
        min_samples_leaf=20, random_state=0)


def walk_forward(d, inicio_prueba="2018-01-01", cada=4, cuantiles=(0.9,)):
    """Reentrena cada `cada` semanas con todo lo anterior y pronostica las siguientes.

    Una fila de la semana s solo entra al entrenamiento cuando P_{s+1} ya se observó,
    es decir, cuando el origen del pronóstico es posterior a s.
    """
    d = d.dropna(subset=VARIABLES + ["y"])
    prueba = d.index[d.index >= pd.Timestamp(inicio_prueba)]
    filas = []
    for i in range(0, len(prueba), cada):
        bloque = prueba[i:i + cada]
        entren = d[d.index < bloque[0]]
        X, y = entren[VARIABLES], entren.y
        Xb = d.loc[bloque, VARIABLES]
        pred = pd.DataFrame(index=bloque)
        pred["real"] = d.loc[bloque, "precio_sig"]
        pred["Ingenuo"] = d.loc[bloque, "precio"]
        for nombre, m in modelos().items():
            pred[nombre] = pred.Ingenuo * np.exp(m.fit(X, y).predict(Xb))
        for q in cuantiles:
            pred[f"GBoost_q{int(q * 100)}"] = pred.Ingenuo * np.exp(cuantil(q).fit(X, y).predict(Xb))
        filas.append(pred)
    return pd.concat(filas)


def ablacion(d, inicio_prueba="2018-01-01", cada=4):
    """MAE de Ridge en walk-forward con el grupo de precio solo, sumando cada grupo
    del sistema por separado y con todos. Mide el aporte de cada grupo sobre el precio."""
    conjuntos = {"solo precio": GRUPOS["precio"]}
    for g in ("hidrologia", "ofertas", "termica", "enos", "calendario"):
        conjuntos[f"precio + {g}"] = GRUPOS["precio"] + GRUPOS[g]
    conjuntos["todas"] = VARIABLES
    d = d.dropna(subset=VARIABLES + ["y"])
    prueba = d.index[d.index >= pd.Timestamp(inicio_prueba)]
    real, base = d.loc[prueba, "precio_sig"], d.loc[prueba, "precio"]
    r = {"ingenuo": (base - real).abs().mean()}
    for nombre, cols in conjuntos.items():
        pred = pd.Series(index=prueba, dtype=float)
        for i in range(0, len(prueba), cada):
            bloque = prueba[i:i + cada]
            entren = d[d.index < bloque[0]]
            m = modelos()["Ridge"].fit(entren[cols], entren.y)
            pred[bloque] = base[bloque] * np.exp(m.predict(d.loc[bloque, cols]))
        r[nombre] = (pred - real).abs().mean()
    t = pd.Series(r).rename("MAE").to_frame()
    t["mejora_vs_ingenuo"] = 1 - t.MAE / r["ingenuo"]
    return t


def metricas(pred, columnas=("Ingenuo", "Ridge", "GBoost")):
    r = {}
    for c in columnas:
        e = pred[c] - pred.real
        r[c] = {
            "MAE": e.abs().mean(),
            "RMSE": np.sqrt((e ** 2).mean()),
            "MAPE_%": (e.abs() / pred.real).mean() * 100,
            "sesgo": e.mean(),
        }
    t = pd.DataFrame(r).T
    t["MAE_vs_ingenuo"] = 1 - t.MAE / t.loc["Ingenuo", "MAE"]
    return t


def diebold_mariano(pred, modelo, referencia="Ingenuo"):
    """Prueba DM (h=1, pérdida absoluta). p < 0.05 con estadístico negativo:
    el modelo tiene menor error que la referencia."""
    dl = (pred[modelo] - pred.real).abs() - (pred[referencia] - pred.real).abs()
    est = dl.mean() / np.sqrt(dl.var(ddof=1) / len(dl))
    return est, 2 * stats.norm.sf(abs(est))


def por_periodo(pred, columnas=("Ingenuo", "Ridge", "GBoost")):
    """MAE por año y en semanas de alta variabilidad (quintil superior de |cambio real|)."""
    abs_err = pred[list(columnas)].sub(pred.real, axis=0).abs()
    anual = abs_err.groupby(pred.index.year).mean()
    cambio = np.log(pred.real / pred.Ingenuo).abs()
    alta = cambio >= cambio.quantile(0.8)
    resumen = pd.DataFrame({
        "normal": abs_err[~alta].mean(),
        "alta_variabilidad": abs_err[alta].mean(),
    }).T
    return anual, resumen


def conformal(pred, columna, nivel=0.9, ventana=104, minimo=26, escala=None):
    """Cota superior calibrada por conformal con ventana móvil (escala log).

    Puntaje de la semana s: log(P_{s+1} / cota_s), dividido por `escala` si se da
    (p. ej. la volatilidad reciente, para ensanchar la cota en semanas agitadas).
    Al emitir el pronóstico de la semana t ya se conoce P_t, así que solo entran
    los puntajes de filas anteriores a t. El ajuste es el cuantil empírico
    corregido ceil((n+1)·nivel)/n de los últimos `ventana` puntajes (`None` = todos).
    """
    esc = np.ones(len(pred)) if escala is None else escala.reindex(pred.index).to_numpy()
    s = np.log(pred.real / pred[columna]).to_numpy() / esc
    ajuste = np.full(len(s), np.nan)
    for i in range(minimo, len(s)):
        previos = s[0 if ventana is None else max(0, i - ventana):i]
        previos = previos[~np.isnan(previos)]
        n = len(previos)
        ajuste[i] = np.quantile(previos, min(1.0, np.ceil((n + 1) * nivel) / n), method="higher")
    return pred[columna] * np.exp(ajuste * esc)


def volatilidad(sem, semanas=4):
    """Desviación del cambio log semanal en las últimas `semanas`, conocida al cierre de s."""
    return np.log(sem.precio / sem.precio_ant).rolling(semanas).std()


def evaluar_cota(pred, columnas, nivel=0.9):
    """Cobertura (global, peor año, semanas normales y de alta variabilidad),
    holgura sobre el precio real y pérdida pinball de cada cota."""
    cambio = np.log(pred.real / pred.Ingenuo).abs()
    alta = cambio >= cambio.quantile(0.8)
    r = {}
    for c in columnas:
        cota, real = pred[c], pred.real
        cubre = real <= cota
        e = real - cota
        r[c] = {
            "cobertura": cubre.mean(),
            "cobertura_min_anual": cubre.groupby(pred.index.year).mean().min(),
            "cobertura_normal": cubre[~alta].mean(),
            "cobertura_alta_var": cubre[alta].mean(),
            "holgura_media_%": ((cota - real) / real)[cubre].mean() * 100,
            "faltante_medio_%": ((real - cota) / real)[~cubre].mean() * 100,
            "pinball": np.maximum(nivel * e, (nivel - 1) * e).mean(),
        }
    return pd.DataFrame(r).T


def importancias(d, inicio_prueba="2018-01-01"):
    """Coeficientes estandarizados de Ridge e importancia por permutación del GBoost,
    entrenados antes de `inicio_prueba` y evaluados en el periodo de prueba."""
    d = d.dropna(subset=VARIABLES + ["y"])
    ent, pru = d[d.index < inicio_prueba], d[d.index >= inicio_prueba]
    m = modelos()
    ridge = m["Ridge"].fit(ent[VARIABLES], ent.y)
    gb = m["GBoost"].fit(ent[VARIABLES], ent.y)
    perm = permutation_importance(gb, pru[VARIABLES], pru.y, n_repeats=20, random_state=0,
                                  scoring="neg_mean_absolute_error")
    return pd.DataFrame({
        "coef_ridge": ridge[-1].coef_,
        "perm_gboost": perm.importances_mean,
    }, index=VARIABLES).sort_values("perm_gboost", ascending=False)


def pronostico_siguiente(d, pred_hist=None, ventana=104):
    """Entrena con toda la historia y pronostica la semana posterior a la última completa.

    Con `pred_hist` (salida de walk_forward) añade las cotas al 90 % calibradas
    por conformal con los últimos `ventana` errores fuera de muestra."""
    completa = d.dropna(subset=VARIABLES + ["y"])
    ultima = d.dropna(subset=VARIABLES).iloc[[-1]]
    out = {"semana_base": ultima.index[0], "precio_base": ultima.precio.iloc[0]}
    for nombre, m in modelos().items():
        out[nombre] = out["precio_base"] * np.exp(m.fit(completa[VARIABLES], completa.y).predict(ultima[VARIABLES])[0])
    out["GBoost_q90"] = out["precio_base"] * np.exp(
        cuantil(0.9).fit(completa[VARIABLES], completa.y).predict(ultima[VARIABLES])[0])
    if pred_hist is not None:
        # Fila nueva sin precio real: conformal() la ajusta solo con las filas anteriores.
        sem = ultima.index[0]
        h = pd.concat([pred_hist[pred_hist.index < sem],
                       pd.DataFrame({"real": np.nan, "Ingenuo": out["precio_base"],
                                     "Ridge": out["Ridge"]}, index=[sem])])
        out["Ridge_cota90"] = conformal(h, "Ridge", ventana=ventana).iloc[-1]
        out["Ridge_cota90_vol"] = conformal(h, "Ridge", ventana=ventana,
                                            escala=volatilidad(d)).iloc[-1]
    return pd.Series(out)
