"""E11: LEAR (LASSO Estimated AutoRegressive) diario, agregado a la semana objetivo.

Referencia: Lago et al. (2021), "Forecasting day-ahead electricity prices: A review of
state-of-the-art algorithms, best practices and an open-access benchmark".

Aprende de todos los días de la historia, no solo de los domingos (~6000 filas frente a
~870). Las variables de la fila t solo usan lo conocido al cierre del día t.

Dos variantes:
- bottomup: un LASSO por cada día de la semana objetivo; se agregan con la demanda de los
  mismos días de la semana anterior, igual que el precio semanal ponderado.
- directo: un solo LASSO para el cambio del promedio ponderado de la semana objetivo.

Con `ventanas`, cada predicción (en log) promedia modelos entrenados con los últimos
1, 2, 4 y 8 años y con toda la historia, para resistir mejor los cambios de régimen.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LassoLarsIC
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

VENTANAS = (365, 730, 1461, 2922, None)


def variables_diarias(t):
    """Variables de cada día t, conocidas a su cierre. `prog_t` del día siguiente se publica en t."""
    lp = np.log(t.precio.clip(lower=1))
    v = pd.DataFrame(index=t.index)
    v["nivel"] = lp
    for k in (1, 2, 3, 4, 5, 6, 7, 13, 14, 20, 21, 27, 28):
        v[f"rezago_{k}"] = lp.shift(k) - lp
    v["media_7"] = np.log(t.precio.rolling(7).mean()) - lp
    v["media_28"] = np.log(t.precio.rolling(28).mean()) - lp
    v["volatilidad_7"] = lp.diff().rolling(7).std()
    v["volatilidad_28"] = lp.diff().rolling(28).std()
    v["pico_rel"] = np.log(t.precio_max / t.precio)
    v["dispersion"] = t.precio_std / t.precio
    v["embalse"] = t.embalse
    v["embalse_cambio_7"] = t.embalse.diff(7)
    v["aportes_1"] = t.aportes / t.aportes_media
    v["aportes_7"] = t.aportes.rolling(7).sum() / t.aportes_media.rolling(7).sum()
    v["aportes_28"] = t.aportes.rolling(28).sum() / t.aportes_media.rolling(28).sum()
    v["oferta_t"] = np.log(t.oferta_t)
    v["oferta_nt"] = np.log(t.oferta_nt)
    v["brecha_nt"] = v.oferta_nt - lp
    v["brecha_t"] = v.oferta_t - lp
    v["demanda_rel"] = np.log(t.demanda / t.demanda.rolling(7).mean())
    v["utilizacion_t"] = t.gen_t / (t.cap_t * 24)
    v["participacion_t"] = t.gen_t / t.gen_total
    v["prog_rel"] = np.log(t.prog_t.shift(-1) / t.gen_t.rolling(7).mean())
    angulo = 2 * np.pi * t.index.dayofyear / 365.25
    v["sen_anio"], v["cos_anio"] = np.sin(angulo), np.cos(angulo)
    for d in range(6):
        v[f"dia_{d}"] = (t.index.weekday == d).astype(float)
    return v


def _lasso():
    return make_pipeline(StandardScaler(), LassoLarsIC(criterion="aic", max_iter=500))


class LEAR:
    """Compatible con `backtesting.backtest` (usa solo el índice semanal de `prueba`)."""

    variables = ()

    def __init__(self, nombre, diaria, ultimo_dia=6, modo="bottomup", ventanas=(None,)):
        self.nombre, self.t, self.ultimo_dia, self.modo, self.ventanas = nombre, diaria, ultimo_dia, modo, ventanas
        self.variables = []
        self.x = variables_diarias(diaria)
        # La fila `prog_rel` del último día conocido puede no tener programación aún.
        self.x["prog_rel"] = self.x.prog_rel.ffill()
        self.lp = np.log(diaria.precio.clip(lower=1))
        # Días de la semana objetivo contados desde el origen: del lunes al domingo siguientes.
        primero = 7 - ultimo_dia
        self.horizontes = list(range(primero, primero + 7))

    def _objetivo(self, h=None):
        """Cambio log desde el origen t: al día t+h (bottomup) o al promedio semanal objetivo (directo)."""
        if self.modo == "bottomup":
            return self.lp.shift(-h) - self.lp
        pd_ = (self.t.precio * self.t.demanda)
        fin = self.horizontes[-1]
        semanal = pd_.rolling(7).sum().shift(-fin) / self.t.demanda.rolling(7).sum().shift(-fin)
        return np.log(semanal) - self.lp

    def _ajustar(self, y, corte_origen, x_pred):
        """Promedio en log de un LASSO por ventana, con orígenes cuyo objetivo ya se observó."""
        datos = self.x.assign(_y=y).dropna()
        datos = datos[datos.index <= corte_origen]
        preds = []
        for w in self.ventanas:
            d = datos if w is None else datos.iloc[-w:]
            m = _lasso().fit(d.drop(columns="_y"), d._y)
            preds.append(m.predict(x_pred))
        return np.mean(preds, axis=0)

    def ajustar_predecir(self, entren, prueba):
        semanas = prueba.index
        # Al emitir el primer pronóstico del bloque se conoce hasta `ultimo_dia` de su semana base.
        conocido = semanas[0] + pd.Timedelta(days=self.ultimo_dia)
        origenes = semanas + pd.Timedelta(days=self.ultimo_dia)
        x_pred = self.x.loc[origenes]
        base = self.lp.loc[origenes].to_numpy()
        if self.modo == "directo":
            corte = conocido - pd.Timedelta(days=self.horizontes[-1])
            return np.exp(base + self._ajustar(self._objetivo(), corte, x_pred))
        # Bottom-up: un modelo por día, agregados con la demanda de los mismos días de la última
        # semana completa conocida (la base si se conoce entera; si no, la anterior).
        yh = np.column_stack([
            self._ajustar(self._objetivo(h), conocido - pd.Timedelta(days=h), x_pred) for h in self.horizontes])
        precios = np.exp(base[:, None] + yh)
        atras = 7 if self.ultimo_dia == 6 else 14
        demanda = np.column_stack([self.t.demanda.reindex(origenes + pd.Timedelta(days=h - atras)).to_numpy()
                                   for h in self.horizontes])
        return (precios * demanda).sum(axis=1) / demanda.sum(axis=1)


class VentanasRidge:
    """Ridge semanal con promedio de ventanas de calibración (52, 104, 208 y 416 semanas y toda la historia)."""

    def __init__(self, nombre, variables, fabrica, ventanas=(52, 104, 208, 416, None)):
        self.nombre, self.variables, self.fabrica, self.ventanas = nombre, list(variables), fabrica, ventanas

    def ajustar_predecir(self, entren, prueba):
        preds = []
        for w in self.ventanas:
            d = entren if w is None else entren.iloc[-w:]
            preds.append(self.fabrica().fit(d[self.variables], d.y).predict(prueba[self.variables]))
        return prueba.precio.to_numpy() * np.exp(np.mean(preds, axis=0))
