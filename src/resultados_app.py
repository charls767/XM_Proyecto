"""Reúne en results/app/ lo que muestra la app de Streamlit, sin volver a correr experimentos.

Uso: python src/resultados_app.py

Toma los backtests ya guardados (E0–E14), el registro de pronósticos y la caché de datos.
La app solo lee esta carpeta: no consulta la API de XM ni reentrena modelos al abrirse.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import data_pipeline as dp  # noqa: E402
import experimentos as ex  # noqa: E402
import feature_engineering as fe  # noqa: E402
import models  # noqa: E402
import semanal  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
RES = RAIZ / "results"
SALIDA = RES / "app"

# (archivo, columna, nombre en la app, familia, descripción)
MODELOS = [
    ("E14", "Ingenuo", "Ingenuo", "Referencia", "Repite el precio de la semana base."),
    ("E0_E1", "Estacional", "Estacional", "Referencia", "Repite el precio de hace 51 semanas (misma época del año anterior)."),
    ("E14", "Ridge14", "Ridge 14 (oficial)", "Lineal", "Regresión Ridge sobre el cambio del precio con 14 variables."),
    ("E5E6", "Ridge19", "Ridge 19", "Lineal", "Ridge con 19 variables, incluye ENOS y generación térmica."),
    ("E13", "ARIMA_auto", "ARIMA", "Series de tiempo", "ARIMA con órdenes elegidos automáticamente."),
    ("E5E6", "SARIMAX", "SARIMAX", "Series de tiempo", "SARIMAX con las mismas variables exógenas."),
    ("E5E6", "LightGBM", "LightGBM", "Árboles", "Gradient boosting con las 14 variables."),
    ("E14", "LEAR_directo", "LEAR diario", "Lineal", "LASSO sobre precios diarios, agregado a la semana."),
    ("E14", "Ens[Ridge14+LEAR]", "Ensamble Ridge + LEAR", "Ensamble", "Promedio del oficial y LEAR diario (candidato 1)."),
    ("E5E6", "Ens[Ridge14+LightGBM+SARIMAX]", "Ensamble Ridge + LightGBM + SARIMAX", "Ensamble",
     "Promedio de los tres modelos."),
    ("E14", "Ridge14+cmg2d", "Ridge 14 + costo marginal", "Lineal",
     "Oficial más el costo marginal programado del lunes y martes de la semana objetivo (candidato 2). "
     "Requiere emitir con la semana objetivo ya iniciada."),
]
COTAS = {"Ingenuo": "cota_Ingenuo", "Ridge 14 (oficial)": "cota_Ridge14",
         "Ensamble Ridge + LEAR": "cota_Ens[Ridge14+LEAR]", "Ridge 14 + costo marginal": "cota_Ridge14+cmg2d"}

EPISODIOS = {**ex.EPISODIOS_ESTRES, "Período de riesgo 2026": ("2026-09-07", "2026-12-31")}
OFERTAS = ["log_oferta_termica", "log_oferta_no_termica", "brecha_oferta_nt"]


def predicciones():
    """Pronósticos fuera de muestra de cada modelo, en las semanas que tienen todos los de E14."""
    tablas = {f: pd.read_parquet(RES / f"{f}_ancho.parquet") for f in {m[0] for m in MODELOS}}
    e14 = tablas["E14"]
    p = e14[["real", "base"]].copy()
    for archivo, col, nombre, *_ in MODELOS:
        p[nombre] = tablas[archivo][col].reindex(p.index)
    for nombre, col in COTAS.items():
        p[f"cota|{nombre}"] = e14[col]
    p = p.dropna(subset=["real", "Ridge 14 (oficial)"])
    p.index.name = "semana_base"
    p.insert(0, "semana_objetivo", p.index + pd.Timedelta(weeks=1))
    return p


def catalogo():
    return pd.DataFrame([{"modelo": n, "familia": f, "descripcion": d, "tiene_cota": n in COTAS}
                         for _, _, n, f, d in MODELOS])


def ultimo_pronostico_modelo(d):
    """Explicación del pronóstico de la última semana con todas las variables, y la variante sin ofertas.

    La emisión del 12 de noviembre de 2026 salió en respaldo porque XM no había publicado las ofertas
    de noviembre. La variante sin las 3 variables de oferta es informativa: no está en el registro.
    """
    completas = d.dropna(subset=config.VARIABLES)
    semana_full = completas.index.max()
    entreno = d.dropna(subset=config.VARIABLES + ["y"])
    m = models.ridge().fit(entreno[entreno.index < semana_full][config.VARIABLES],
                           entreno[entreno.index < semana_full].y)
    fila = d.loc[semana_full]
    intercepto, aportes = semanal.contribuciones(m, fila)
    pred = float(fila.precio) * float(np.exp(m.predict(d.loc[[semana_full], config.VARIABLES])[0]))

    semana = d.index.max()
    sin = [v for v in config.VARIABLES if v not in OFERTAS]
    e2 = d.dropna(subset=sin + ["y"])
    m2 = models.ridge().fit(e2[e2.index < semana][sin], e2[e2.index < semana].y)
    pred_sin = float(d.at[semana, "precio"]) * float(np.exp(m2.predict(d.loc[[semana], sin])[0]))
    return {
        "explicacion": {
            "semana_base": f"{semana_full:%Y-%m-%d}", "precio_base": float(fila.precio), "pronostico": pred,
            "intercepto": intercepto,
            "aportes": [{"variable": v, "nombre": config.NOMBRES.get(v, v), "aporte_log": float(a),
                         "valor": float(fila[v])} for v, a in aportes.items()],
        },
        "sin_ofertas": {"semana_base": f"{semana:%Y-%m-%d}", "precio_base": float(d.at[semana, "precio"]),
                        "pronostico": pred_sin, "variables": sin},
    }


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    p = predicciones()
    p.to_parquet(SALIDA / "predicciones.parquet")
    catalogo().to_csv(SALIDA / "modelos.csv", index=False)
    pd.DataFrame([{"episodio": k, "inicio": a, "fin": b} for k, (a, b) in EPISODIOS.items()]).to_csv(
        SALIDA / "episodios.csv", index=False)

    d = fe.preparar(dp.tabla_semanal(corregida=True))
    contexto = d[["precio", "embalse_cierre", "aportes_pct_media"]]
    contexto.to_parquet(SALIDA / "contexto.parquet")

    reg = pd.read_csv(RAIZ / "registro" / "pronosticos.csv", parse_dates=semanal.FECHAS)
    # Calificación provisional con el precio vigente, para las semanas ya publicadas aunque falte demanda.
    reg["real_provisional"] = d.precio.reindex(reg.semana_objetivo).to_numpy().round(2)
    reg.to_csv(SALIDA / "registro.csv", index=False)

    with open(SALIDA / "ultimo.json", "w", encoding="utf-8") as f:
        json.dump(ultimo_pronostico_modelo(d), f, ensure_ascii=False, indent=1)
    for nombre in ["E14_confusion.csv", "E14_resumen.csv"]:
        (SALIDA / nombre).write_bytes((RES / nombre).read_bytes())
    print(f"results/app: {len(p)} semanas ({p.index.min():%Y-%m-%d} a {p.index.max():%Y-%m-%d}), "
          f"{len(MODELOS)} modelos")


if __name__ == "__main__":
    main()
