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
    """DM con pérdida absoluta. Estadístico negativo: el modelo erra menos.

    Varianza de Newey-West y distribución t: las diferencias de pérdida se agrupan en los
    episodios de estrés, así que la versión con varianza simple era demasiado optimista.
    """
    return dm_hac((w[modelo] - w.real).abs() - (w[referencia] - w.real).abs())


def dm_hac(dl):
    dl = np.asarray(dl, dtype=float)
    n = len(dl)
    rezagos = int(np.floor(4 * (n / 100) ** (2 / 9)))
    u = dl - dl.mean()
    v = (u @ u) / n
    for k in range(1, rezagos + 1):
        v += 2 * (1 - k / (rezagos + 1)) * (u[k:] @ u[:-k]) / n
    est = dl.mean() / np.sqrt(v / n)
    return est, 2 * stats.t.sf(abs(est), n - 1)


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


def reality_check(perdida_ref, perdidas_alt, n=4000, q=0.1, semilla=0):
    """Reality check de White con bootstrap estacionario.

    Pregunta si el mejor de una familia de modelos supera a la referencia, teniendo en cuenta
    que se probaron muchos. Una p baja es evidencia real; una alta dice que la mejora es
    compatible con haber buscado entre muchos modelos. En simulación con la nula verdadera
    (157 semanas, 20 modelos) rechaza 6 % al nivel de 5 %. Se descartó la versión consistente
    de Hansen (SPA) porque en esa misma simulación rechazaba 11 %.
    """
    d = perdida_ref.to_numpy()[:, None] - perdidas_alt.to_numpy()  # > 0: la alternativa erra menos
    t, k = d.shape
    m = d.mean(axis=0)
    rng = np.random.default_rng(semilla)
    nula = np.empty(n)
    for b in range(n):
        idx = np.empty(t, dtype=int)
        idx[0] = rng.integers(t)
        saltos = rng.random(t) < q
        nuevos = rng.integers(t, size=t)
        for i in range(1, t):
            idx[i] = nuevos[i] if saltos[i] else (idx[i - 1] + 1) % t
        nula[b] = max(0.0, (np.sqrt(t) * (d[idx].mean(axis=0) - m)).max())
    est = max(0.0, np.sqrt(t) * m.max())
    return {"mejor": perdidas_alt.columns[int(m.argmax())], "mejora_MAE": float(m.max()), "modelos": k,
            "p": float((nula >= est).mean())}


def _log_ver(p, a, b):
    return a * np.log(max(p, 1e-12)) + b * np.log(max(1 - p, 1e-12))


def pruebas_cobertura(fallas, nivel=0.9):
    """Kupiec (¿falla con la frecuencia prometida?) y Christoffersen (¿las fallas se agrupan?)."""
    h = np.asarray(fallas, dtype=int)
    n, x = len(h), int(h.sum())
    lr_uc = -2 * (_log_ver(1 - nivel, x, n - x) - _log_ver(x / n, x, n - x))
    a, b = h[:-1], h[1:]
    n00, n01 = ((a == 0) & (b == 0)).sum(), ((a == 0) & (b == 1)).sum()
    n10, n11 = ((a == 1) & (b == 0)).sum(), ((a == 1) & (b == 1)).sum()
    p01, p11 = n01 / max(n00 + n01, 1), n11 / max(n10 + n11, 1)
    lr_ind = -2 * (_log_ver((n01 + n11) / (n - 1), n01 + n11, n00 + n10)
                   - (_log_ver(p01, n01, n00) + _log_ver(p11, n11, n10)))
    ic = stats.binomtest(n - x, n).proportion_ci(method="wilson")
    return {"semanas": n, "cobertura": 1 - x / n, "IC95_inf": ic.low, "IC95_sup": ic.high,
            "p_Kupiec": float(stats.chi2.sf(lr_uc, 1)), "p_falla_tras_falla": float(p11), "p_falla_tras_acierto": float(p01),
            "p_independencia": float(stats.chi2.sf(lr_ind, 1))}


def subgrupos(g, claves):
    """Error, sesgo y cobertura por régimen. g: columnas real, pred, ing y cota."""
    filas = []
    for nombre, clave in claves.items():
        for k, s in g.groupby(clave, observed=True):
            ae, ai = (s.pred - s.real).abs(), (s.ing - s.real).abs()
            filas.append({"grupo": nombre, "valor": k, "semanas": len(s), "precio_medio": s.real.mean(), "MAE": ae.mean(),
                          "MAE_ingenuo": ai.mean(), "mejora_%": (1 - ae.mean() / ai.mean()) * 100,
                          "MAPE_%": (ae / s.real).mean() * 100, "sesgo": (s.pred - s.real).mean(),
                          "cobertura_%": (s.real <= s.cota).mean() * 100})
    return pd.DataFrame(filas)
