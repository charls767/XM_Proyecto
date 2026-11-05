"""Genera dashboard/index.html con el pronóstico vigente, el panel de métricas y el registro.

Uso: python dashboard/generar.py
Toma el pronóstico del mismo proceso que `src/semanal.py` (sin volver a registrar) y
las evaluaciones guardadas en results/. Requiere haber corrido los experimentos
e3e4, e7 y alertas al menos una vez.
"""

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import alertas  # noqa: E402
import calibration as cal  # noqa: E402
import config  # noqa: E402
import data_pipeline as dp  # noqa: E402
import feature_engineering as fe  # noqa: E402
import semanal  # noqa: E402

RES = RAIZ / "results"
PLANTILLA = Path(__file__).parent / "plantilla.html"
SALIDA = Path(__file__).parent / "index.html"
DESDE = "2018-01-01"


def _f(x, nd=2):
    if x is None or (isinstance(x, (float, np.floating)) and not np.isfinite(x)) or pd.isna(x):
        return None
    return round(float(x), nd)


def _fecha(t):
    return None if pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%d")


def actual(r):
    aportes = r["aportes"].copy()
    nombres = dict(config.NOMBRES)
    if {"sen_semana", "cos_semana"} <= set(aportes.index):
        # Seno y coseno son una sola idea para el lector: la época del año.
        aportes["epoca"] = aportes.pop("sen_semana") + aportes.pop("cos_semana")
        nombres["epoca"] = "Época del año"
    explicacion = [{"var": k, "nombre": nombres.get(k, k), "log": _f(v, 4),
                    "pct": _f((np.exp(v) - 1) * 100, 1)}
                   for k, v in aportes.reindex(aportes.abs().sort_values(ascending=False).index).items()]
    return {
        "fecha_emision": _fecha(r["fecha_emision"]), "semana_base": _fecha(r["semana_base"]),
        "semana_objetivo": _fecha(r["semana_objetivo"]), "estado": r["estado"], "motivos": r["motivos"],
        "datos_hasta": {k: _fecha(v) for k, v in r["datos_hasta"].items()},
        "precio_base": _f(r["precio_base"], 1), "pronostico": _f(r["pronostico"], 1),
        "cambio_pct": _f(r["cambio_pct"], 1), "cota90": _f(r["cota90"], 1), "cota90_vol": _f(r["cota90_vol"], 1),
        "intercepto_pct": _f((np.exp(r["intercepto"]) - 1) * 100, 1), "explicacion": explicacion,
        "controles": r["controles"].to_dict("records"),
        "fuera_de_rango": r["fuera_de_rango"].to_dict("records"),
        "version": r["version_modelo"],
    }


def historial(r, d):
    """Historial fuera de muestra del modelo principal (simulado) con cotas y semanas volátiles."""
    h = r["historial"].dropna(subset=["real"]).copy()
    h["cota"] = cal.conformal(h.real, h.prediccion, nivel=config.NIVEL_COTA, ventana=config.VENTANA_CONFORMAL)
    h["cota_vol"] = cal.conformal(h.real, h.prediccion, nivel=config.NIVEL_COTA,
                                  ventana=config.VENTANA_CONFORMAL, escala=d.volatilidad_4s)
    h = h[h.index >= DESDE]
    cambio = np.log(h.real / h.ingenuo).abs()
    h["volatil"] = cambio >= cambio.quantile(0.8)
    obj = h.index + pd.Timedelta(weeks=1)
    return [{"s": _fecha(o), "real": _f(f.real, 1), "pred": _f(f.prediccion, 1), "ing": _f(f.ingenuo, 1),
             "cota": _f(f.cota, 1), "cota_vol": _f(f.cota_vol, 1), "vol": bool(f.volatil)}
            for o, f in zip(obj, h.itertuples())]


def registro():
    reg = semanal._leer_registro()
    return [{c: (_fecha(v) if c in semanal.FECHAS else (None if pd.isna(v) else v)) for c, v in fila.items()}
            for fila in reg.to_dict("records")]


def hidro(d):
    h = d[d.index >= DESDE]
    return [{"s": _fecha(s), "emb": _f(e * 100, 1), "apo": _f(a * 100, 1)}
            for s, e, a in zip(h.index, h.embalse_cierre, h.aportes_pct_media_4s)]


def estres():
    t = pd.read_csv(RES / "E10_estres.csv")
    t = t[t.modelo.isin(["Ingenuo", "Ridge14"])]
    out = []
    for ep, g in t.groupby("episodio", sort=False):
        g = g.set_index("modelo")
        out.append({"episodio": ep, "semanas": int(g.loc["Ridge14", "semanas"]),
                    "mae": _f(g.loc["Ridge14", "MAE"], 1), "mae_ing": _f(g.loc["Ingenuo", "MAE"], 1),
                    "sesgo": _f(g.loc["Ridge14", "sesgo"], 1), "cobertura": _f(g.loc["Ridge14", "cobertura"] * 100, 0)})
    return out


def modelos_tabla():
    e3 = pd.read_csv(RES / "E3E4_resumen.csv", index_col=0)
    filas = [("Ingenuo", "Precio de la semana anterior"), ("Ridge[E1-enos-termica]", "Ridge, 14 variables (principal)"),
             ("Ridge[E1]", "Ridge, 19 variables"), ("LightGBM[E1]", "LightGBM, ajustado"),
             ("XGBoost[E1]", "XGBoost, ajustado"), ("GBoost[E1]", "GBoost (baseline PAE)")]
    return [{"modelo": n, **{f"mae_{p}": _f(e3.loc[k, f"MAE_{p}"], 1) for p in ("desarrollo", "seleccion", "final")},
             **{f"mej_{p}": _f(e3.loc[k, f"mejora_%_{p}"], 1) for p in ("desarrollo", "seleccion", "final")}}
            for k, n in filas]


def alertas_datos(r):
    res = pd.read_csv(RES / "alertas_resumen.csv")
    hist = pd.read_parquet(RES / "alertas.parquet")
    hist = hist[hist.semana_base >= DESDE]
    out = []
    for e in alertas.EVENTOS:
        a = r["alertas"][e.nombre]
        sel = res.query("evento == @e.nombre and periodo == 'seleccion' and modelo == 'Logistica'").iloc[0]
        sub = hist[hist.evento == e.nombre]
        out.append({
            "evento": e.nombre, "descripcion": e.descripcion, "semana_objetivo": _fecha(a["semana_objetivo"]),
            "puntaje": _f(a["puntaje"], 3), "umbral": _f(a["umbral"], 3), "alerta": bool(a["alerta"]),
            "principales": [{"var": k, "v": _f(v, 3)} for k, v in a["principales"].items()],
            "recall": _f(sel.recall * 100, 0), "precision": _f(sel.precision * 100, 0),
            "inicios": int(sel.inicios), "inicios_ok": int(round(sel.recall_inicios * sel.inicios)),
            "historia": [{"s": _fecha(o), "p": _f(p, 3), "y": int(y)}
                         for o, p, y in zip(sub.semana_objetivo, sub.Logistica, sub.observado)],
        })
    return out


def candidato_simulado():
    """Oficial frente al candidato en la evaluación simulada 2018–2026 (E11, semana completa)."""
    w = pd.read_parquet(RES / "E11_corte6_ancho.parquet")
    columnas = {"oficial": "Ridge14", "candidato": "Ens[Ridge14+LEAR_directo]"}
    for c in columnas.values():
        w["cota " + c] = cal.conformal(w.real, w[c], nivel=config.NIVEL_COTA, ventana=config.VENTANA_CONFORMAL)
    w = w[w.index >= DESDE]
    out = {}
    for nombre, c in columnas.items():
        e = w.real - w["cota " + c]
        out[nombre] = {"mae": _f((w[c] - w.real).abs().mean(), 1),
                       "sesgo": _f((w[c] - w.real).mean(), 1),
                       "cobertura": _f((w.real <= w["cota " + c]).mean() * 100, 1),
                       "pinball": _f(np.maximum(0.9 * e, -0.1 * e).mean(), 2)}
    return out


def nota_registro(r):
    """Si la emisión registrada de esta semana difiere de la de hoy, se muestra sin reescribir el registro
    (p. ej. porque XM completó la demanda o se corrigió un dato después de emitir)."""
    reg = semanal._leer_registro()
    fila = reg[reg.semana_base == r["semana_base"]]
    if fila.empty or abs(fila.pronostico.iloc[0] / r["pronostico"] - 1) < 0.005:
        return None
    return {"fecha_emision": _fecha(fila.fecha_emision.iloc[0]), "pronostico": _f(fila.pronostico.iloc[0], 1),
            "precio_base": _f(fila.precio_base.iloc[0], 1)}


def main():
    r = semanal.emitir(actualizar=False, guardar=False)
    d = fe.preparar(dp.tabla_semanal(corregida=True))
    datos = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "actual": {**actual(r), "nota_registro": nota_registro(r)}, "historial": historial(r, d), "registro": registro(),
        "hidro": hidro(d), "estres": estres(), "modelos": modelos_tabla(), "alertas": alertas_datos(r),
        "candidato": {"actual": {k: (_f(v, 1) if k != "version" else v) for k, v in r["candidato"].items()} if r["candidato"] else None,
                      "simulado": candidato_simulado(), "revision": config.REVISION_CANDIDATO,
                      "decision": config.DECISION_CANDIDATO},
        "metas": {"mejora_mae": 10, "cobertura": config.NIVEL_COTA * 100, "cobertura_volatil": 85,
                  "ventana": config.VENTANA_MONITOREO},
        "nombres": {**config.NOMBRES, **{k: v for k, v in alertas_nombres().items()}},
    }
    html = PLANTILLA.read_text(encoding="utf-8").replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False))
    SALIDA.write_text(html, encoding="utf-8")
    print(f"{SALIDA} ({len(html) / 1024:.0f} KB)")


def alertas_nombres():
    return {
        "momentum": "Cambio frente a la semana anterior", "max_h_rel": "Pico horario frente al promedio",
        "fut": "Utilización térmica", "participacion_termica": "Participación térmica", "oni": "ONI",
        "oni_rezago": "ONI hace 3 meses", "fase_enos": "Fase ENOS", "rezago_2_rel": "Precio hace 2 semanas",
        "rezago_3_rel": "Precio hace 3 semanas", "tendencia_4s": "Tendencia 4 semanas",
        "tendencia_8s": "Tendencia 8 semanas", "tendencia_13s": "Tendencia 13 semanas",
        "volatilidad_4s": "Volatilidad 4 semanas", "volatilidad_13s": "Volatilidad 13 semanas",
        "demanda_crec_anual": "Crecimiento anual de la demanda", "demanda_cambio": "Cambio semanal de la demanda",
        "embalse_anomalia": "Embalse frente a la misma semana histórica", "oni_cambio_3m": "Cambio del ONI en 3 meses",
        "estado_precio_alto": "Ya en precio alto", "estado_salto": "Ya hubo salto",
        "estado_estres_hidrico": "Ya en estrés hídrico",
    }


if __name__ == "__main__":
    main()
