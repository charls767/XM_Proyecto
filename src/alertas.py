"""Modelo C: alertas tempranas de condiciones críticas.

Cada evento se define para la semana base s con umbrales calculados solo con
información disponible al cierre de s. El horizonte h indica cuántas semanas
después de s se observa el evento; una fila s solo entra al entrenamiento cuando
su evento ya se observó (s + h ≤ semana de emisión).

Explicabilidad: contribuciones SHAP exactas de LightGBM (`pred_contrib`) y, para
la regresión logística, coeficiente × variable estandarizada (SHAP lineal).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import average_precision_score, fbeta_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import backtesting as bt
import feature_engineering as fe

UMBRAL_EMBALSE = 0.45
SALTO = np.log(1.25)


@dataclass
class Evento:
    nombre: str
    horizonte: int  # semanas después de s en que se observa
    descripcion: str


EVENTOS = [
    Evento("precio_alto", 1, "P(s+1) sobre el percentil 90 de las 156 semanas previas"),
    Evento("salto", 1, "P(s+1) al menos 25 % mayor que P(s)"),
    Evento("estres_hidrico", 4, "Embalse al cierre de s+4 por debajo de 45 %"),
]


def eventos(d):
    """Etiqueta (lo que pasa después de s) y estado actual (lo que ya se sabe en s)."""
    p90 = d.precio.rolling(156, min_periods=104).quantile(0.9)
    emb4 = d.embalse_cierre.shift(-4)
    etiqueta = pd.DataFrame({
        "precio_alto": (d.precio_sig > p90).where(d.precio_sig.notna() & p90.notna()),
        "salto": (d.y >= SALTO).where(d.y.notna()),
        "estres_hidrico": (emb4 < UMBRAL_EMBALSE).where(emb4.notna()),
    })
    estado = pd.DataFrame({
        "precio_alto": (d.precio > p90).where(p90.notna()),
        "salto": d.momentum >= SALTO,
        "estres_hidrico": d.embalse_cierre < UMBRAL_EMBALSE,
    }).astype(float)
    return etiqueta.astype(float), estado


def variables_alerta(d, estado, extra=()):
    """Variables de E1 + candidatas nuevas + los estados actuales como indicadores.
    `extra`: columnas adicionales (p. ej. las de E8)."""
    x = d[fe.VARIABLES + [v for g in fe.GRUPOS_NUEVOS.values() for v in g] + list(extra)].copy()
    for c in estado:
        x[f"estado_{c}"] = estado[c]
    return x


def logistica():
    return make_pipeline(StandardScaler(), LogisticRegressionCV(
        Cs=10, cv=TimeSeriesSplit(5), scoring="average_precision", class_weight="balanced",
        max_iter=5000))


def lightgbm_clf():
    from lightgbm import LGBMClassifier
    return LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=8, min_child_samples=20,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8, is_unbalance=True,
                          random_state=0, deterministic=True, force_row_wise=True, n_jobs=4, verbose=-1)


CLASIFICADORES = {"Logistica": logistica, "LightGBM": lightgbm_clf}


def backtest_alertas(d, inicio="2014-01-01", cada=4, extra=(), solo=None):
    """Probabilidades walk-forward por evento y modelo, con la persistencia como referencia.
    `solo`: nombres de eventos a correr (por defecto, todos)."""
    etiqueta, estado = eventos(d)
    x = variables_alerta(d, estado, extra)
    completas = x.dropna().index
    filas = []
    for ev in [e for e in EVENTOS if solo is None or e.nombre in solo]:
        y = etiqueta[ev.nombre]
        validas = completas.intersection(y.dropna().index)
        semanas = d.index[d.index.isin(validas)]
        for bloque in bt.bloques_emision(semanas, inicio, cada):
            # El evento de la fila s se conoce en s + h; la emisión del bloque es tras cerrar bloque[0].
            limite = bloque[0] - pd.Timedelta(weeks=ev.horizonte - 1)
            ent = validas[validas < limite]
            if y[ent].nunique() < 2:
                continue
            fila = pd.DataFrame({"semana_base": bloque, "evento": ev.nombre,
                                 "observado": y[bloque].to_numpy(),
                                 "Persistencia": estado.loc[bloque, ev.nombre].to_numpy()})
            for nombre, fabrica in CLASIFICADORES.items():
                m = fabrica().fit(x.loc[ent], y[ent].astype(int))
                fila[nombre] = m.predict_proba(x.loc[bloque])[:, 1]
            filas.append(fila)
    r = pd.concat(filas, ignore_index=True)
    r["estado_actual"] = [estado.at[s, e] for s, e in zip(r.semana_base, r.evento)]
    r["semana_objetivo"] = r.semana_base + pd.to_timedelta(
        r.evento.map({e.nombre: e.horizonte for e in EVENTOS}), unit="W")
    r["periodo"] = bt.periodo(r.semana_objetivo)
    return r


def umbral_f2(y, p):
    """Umbral que maximiza F2 (recall pesa el doble que precisión)."""
    candidatos = np.unique(np.round(p, 3))
    f2 = [fbeta_score(y, p >= u, beta=2, zero_division=0) for u in candidatos]
    return float(candidatos[int(np.argmax(f2))])


def evaluar(r, modelos=("Persistencia", "Logistica", "LightGBM"), periodo_umbral="desarrollo"):
    """Umbral fijado con el periodo de desarrollo y aplicado a selección y final.

    `recall_inicios`: recall solo en semanas donde el evento ocurre y no estaba
    activo al emitir, es decir, el comienzo de un episodio.
    """
    filas = []
    for ev in r.evento.unique():
        sub = r[r.evento == ev]
        dev = sub[sub.periodo == periodo_umbral]
        for m in modelos:
            u = 0.5 if m == "Persistencia" else umbral_f2(dev.observado, dev[m])
            for p, g in sub.groupby("periodo"):
                y, prob = g.observado.astype(int), g[m]
                alerta = prob >= u
                inicio = (g.observado == 1) & (g.estado_actual == 0)
                filas.append({
                    "evento": ev, "modelo": m, "periodo": p, "umbral": u,
                    "prevalencia": y.mean(), "eventos": int(y.sum()),
                    "PR_AUC": average_precision_score(y, prob) if y.sum() else np.nan,
                    "recall": alerta[y == 1].mean() if y.sum() else np.nan,
                    "precision": y[alerta].mean() if alerta.any() else np.nan,
                    "F2": fbeta_score(y, alerta, beta=2, zero_division=0),
                    "inicios": int(inicio.sum()),
                    "recall_inicios": alerta[inicio].mean() if inicio.any() else np.nan,
                    "alertas_%": alerta.mean() * 100,
                })
    return pd.DataFrame(filas)


def explicar(d, evento, hasta=None, top=5):
    """Probabilidad de la última semana disponible y sus variables con mayor contribución.

    Entrena con todas las filas cuyo evento ya se observó y explica la última fila
    con contribuciones SHAP (LightGBM) y lineales (logística), en log-odds.
    """
    ev = next(e for e in EVENTOS if e.nombre == evento)
    etiqueta, estado = eventos(d)
    x = variables_alerta(d, estado).dropna()
    y = etiqueta[evento]
    ultima = x.index.max() if hasta is None else pd.Timestamp(hasta)
    limite = ultima - pd.Timedelta(weeks=ev.horizonte - 1)
    ent = y.dropna().index.intersection(x.index)
    ent = ent[ent < limite]
    salida = {"semana_base": ultima, "evento": evento}
    for nombre, fabrica in CLASIFICADORES.items():
        m = fabrica().fit(x.loc[ent], y[ent].astype(int))
        fila = x.loc[[ultima]]
        salida[f"prob_{nombre}"] = float(m.predict_proba(fila)[0, 1])
        if nombre == "LightGBM":
            contrib = pd.Series(m.predict(fila, pred_contrib=True)[0, :-1], index=x.columns)
        else:
            esc, lr = m[0], m[-1]
            contrib = pd.Series(lr.coef_[0] * esc.transform(fila)[0], index=x.columns)
        salida[f"top_{nombre}"] = contrib.reindex(contrib.abs().sort_values(ascending=False).index)[:top]
    return salida


def importancia_shap(d, evento, desde="2022-01-01", hasta="2024-12-31"):
    """|SHAP| medio de LightGBM entrenado antes de `desde` y evaluado en [desde, hasta]."""
    ev = next(e for e in EVENTOS if e.nombre == evento)
    etiqueta, estado = eventos(d)
    x = variables_alerta(d, estado).dropna()
    y = etiqueta[evento].reindex(x.index)
    limite = pd.Timestamp(desde) - pd.Timedelta(weeks=ev.horizonte)
    ent = y[(y.index < limite) & y.notna()].index
    prueba = x[(x.index >= desde) & (x.index <= hasta)]
    m = lightgbm_clf().fit(x.loc[ent], y[ent].astype(int))
    contrib = pd.DataFrame(m.predict(prueba, pred_contrib=True)[:, :-1], columns=x.columns, index=prueba.index)
    return contrib.abs().mean().sort_values(ascending=False)
