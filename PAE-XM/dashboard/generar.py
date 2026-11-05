"""Genera dashboard/index.html a partir de results/ y la tabla semanal.

Uso: python dashboard/generar.py
Requiere haber corrido los experimentos (e3e4, e7 y alertas). El pronóstico de la
semana siguiente se reentrena aquí con toda la historia disponible.
"""

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import alertas  # noqa: E402
import backtesting as bt  # noqa: E402
import calibration as cal  # noqa: E402
import data_pipeline as dp  # noqa: E402
import feature_engineering as fe  # noqa: E402
import models  # noqa: E402

RES = RAIZ / "results"
PLANTILLA = Path(__file__).parent / "plantilla.html"
SALIDA = Path(__file__).parent / "index.html"
DESDE = "2018-01-01"


def _f(x, nd=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), nd)


def _fecha(t):
    return pd.Timestamp(t).strftime("%Y-%m-%d")


def pronostico(d):
    """Ridge E1 entrenado con toda la historia; cotas con los errores fuera de muestra de E7."""
    completas = d.dropna(subset=fe.VARIABLES + ["y"])
    ultima = d.dropna(subset=fe.VARIABLES).iloc[[-1]]
    ridge = models.ridge().fit(completas[fe.VARIABLES], completas.y)
    base = float(ultima.precio.iloc[0])
    p50 = base * float(np.exp(ridge.predict(ultima[fe.VARIABLES])[0]))
    w = bt.ancho(bt.cargar("E7_base"))
    semana = ultima.index[0]
    fila = pd.DataFrame({"real": [np.nan], "base": [base], "Ridge": [p50]}, index=[semana])
    h = pd.concat([w[w.index < semana][["real", "base", "Ridge"]], fila])
    return {
        "semana_base": _fecha(semana),
        "semana_objetivo": _fecha(semana + pd.Timedelta(weeks=1)),
        "precio_base": _f(base, 1),
        "ridge": _f(p50, 1),
        "cota90": _f(cal.conformal(h.real, h.Ridge).iloc[-1], 1),
        "cota90_vol": _f(cal.conformal(h.real, h.Ridge, escala=d.volatilidad_4s).iloc[-1], 1),
        "embalse": _f(ultima.embalse_cierre.iloc[0] * 100, 1),
        "aportes_4s": _f(ultima.aportes_pct_media_4s.iloc[0] * 100, 1),
        "oni": _f(ultima.oni.iloc[0], 2),
        "fut": _f(ultima.fut.iloc[0] * 100, 1),
    }


def serie(d):
    """Precio semanal (por semana objetivo) y pronóstico fuera de muestra con su cota."""
    c = pd.read_parquet(RES / "E7_cotas.parquet")
    w = bt.ancho(bt.cargar("E7_base"))
    c = c[c.index >= DESDE]
    obj = c.index + pd.Timedelta(weeks=1)
    return [{"s": _fecha(o), "real": _f(r, 1), "ridge": _f(p, 1), "cota": _f(u, 1), "ing": _f(b, 1)}
            for o, r, p, u, b in zip(obj, c.real, w.loc[c.index, "Ridge"], c["Ridge+conformal"], c.base)]


def hidro(d):
    h = d[d.index >= DESDE]
    return [{"s": _fecha(s), "emb": _f(e * 100, 1), "apo": _f(a * 100, 1)}
            for s, e, a in zip(h.index, h.embalse_cierre, h.aportes_pct_media_4s)]


def modelos_tabla():
    e3 = pd.read_csv(RES / "E3E4_resumen.csv", index_col=0)
    filas = [("Ingenuo", "Precio de la semana anterior"),
             ("Ridge[E1]", "Ridge, 19 variables"),
             ("Ridge[E1-enos-termica]", "Ridge, 14 variables"),
             ("LightGBM[E1,defecto]", "LightGBM, por defecto"),
             ("LightGBM[E1]", "LightGBM, ajustado"),
             ("XGBoost[E1,defecto]", "XGBoost, por defecto"),
             ("XGBoost[E1]", "XGBoost, ajustado"),
             ("GBoost[E1]", "GBoost (baseline)")]
    out = []
    for k, nombre in filas:
        f = e3.loc[k]
        out.append({"modelo": nombre, "clave": k,
                    **{f"mae_{p}": _f(f[f"MAE_{p}"], 1) for p in ("desarrollo", "seleccion", "final")},
                    **{f"mej_{p}": _f(f[f"mejora_%_{p}"], 1) for p in ("desarrollo", "seleccion", "final")},
                    "ic_inf": _f(f.get("IC95_inf_vs_E1_sel"), 1), "ic_sup": _f(f.get("IC95_sup_vs_E1_sel"), 1)})
    return out


def cotas_tabla():
    t = pd.read_csv(RES / "E7_resumen.csv", index_col=0)
    t = t[t["seleccion:exceso_medio_%"] <= 70]
    nombres = {"Ridge+conformal": "Ridge + conformal (principal)",
               "Ridge+conformal_vol": "Ridge + conformal por volatilidad",
               "Ridge+mondrian_hidro": "Ridge + Mondrian hidrológico",
               "Ridge+ACI_0.02": "Ridge + ACI (γ 0,02)",
               "GBoost_q90+CQR": "GBoost q90 + CQR",
               "GBoost_q90": "GBoost q90 sin calibrar"}
    puntos = [{"nombre": k, "exceso": _f(f["seleccion:exceso_medio_%"], 1),
               "cob_vol": _f(f["seleccion:cobertura_alta_var"] * 100, 1),
               "cob": _f(f["seleccion:cobertura"] * 100, 1), "pinball": _f(f["seleccion:pinball"], 1),
               "destacado": k in nombres} for k, f in t.iterrows()]
    tabla = [{"nombre": v, "cob": _f(t.loc[k, "seleccion:cobertura"] * 100, 1),
              "cob_vol": _f(t.loc[k, "seleccion:cobertura_alta_var"] * 100, 1),
              "exceso": _f(t.loc[k, "seleccion:exceso_medio_%"], 0),
              "pinball": _f(t.loc[k, "seleccion:pinball"], 1),
              "cob_total": _f(t.loc[k, "2018-2026:cobertura"] * 100, 1),
              "pinball_total": _f(t.loc[k, "2018-2026:pinball"], 1)} for k, v in nombres.items()]
    return {"puntos": puntos, "tabla": tabla}


def alertas_datos(d):
    res = pd.read_csv(RES / "alertas_resumen.csv")
    r = pd.read_parquet(RES / "alertas.parquet")
    r = r[r.semana_base >= DESDE]
    shap = pd.read_csv(RES / "alertas_shap_seleccion.csv", index_col=0)
    out = []
    for ev in alertas.EVENTOS:
        x = alertas.explicar(d, ev.nombre)
        u = float(res.query("evento == @ev.nombre and modelo == 'Logistica'").umbral.iloc[0])
        sel = res.query("evento == @ev.nombre and periodo == 'seleccion'").set_index("modelo")
        sub = r[r.evento == ev.nombre]
        top = x["top_Logistica"]
        out.append({
            "evento": ev.nombre, "descripcion": ev.descripcion, "horizonte": ev.horizonte,
            "semana_objetivo": _fecha(x["semana_base"] + pd.Timedelta(weeks=ev.horizonte)),
            "puntaje": _f(x["prob_Logistica"], 3), "umbral": _f(u, 3),
            "alerta": bool(x["prob_Logistica"] >= u),
            "contrib": [{"var": k, "v": _f(v, 3)} for k, v in top.items()],
            "metricas": {m: {k: _f(sel.loc[m, k], 2) for k in ("PR_AUC", "recall", "precision", "F2", "alertas_%")}
                         | {"inicios": int(sel.loc[m, "inicios"]),
                            "recall_inicios": _f(sel.loc[m, "recall_inicios"], 2)}
                         for m in ("Persistencia", "Logistica")},
            "historia": [{"s": _fecha(o), "p": _f(p, 3), "y": int(y)}
                         for o, p, y in zip(sub.semana_objetivo, sub.Logistica, sub.observado)],
            "shap": [{"var": k, "v": _f(v, 3)} for k, v in shap[ev.nombre].sort_values(ascending=False)[:6].items()],
        })
    return out


def main():
    sem = dp.tabla_semanal(corregida=True)
    d = fe.preparar(sem)
    datos = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "datos_hasta": _fecha(sem.index.max() + pd.Timedelta(days=6)),
        "pronostico": pronostico(d),
        "serie": serie(d),
        "hidro": hidro(d),
        "modelos": modelos_tabla(),
        "cotas": cotas_tabla(),
        "alertas": alertas_datos(d),
    }
    html = PLANTILLA.read_text(encoding="utf-8").replace(
        "/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False))
    SALIDA.write_text(html, encoding="utf-8")
    print(f"{SALIDA} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
