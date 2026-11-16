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
    ("E15", "Ridge14_Duan", "Ridge 14 con corrección de sesgo", "Lineal",
     "Oficial con el factor de Duan: pronostica la media del precio y no la mediana (E15)."),
    ("E15", "Ridge14+cmg3d_Duan", "Ridge 14 + costo marginal 3 días", "Lineal",
     "Costo marginal programado de lunes a miércoles, con corrección de sesgo (E15). "
     "Es lo que se conoce al emitir el miércoles en la tarde."),
]
# Cota 90 % por modelo: (archivo, columna).
COTAS = {"Ingenuo": ("E14", "cota_Ingenuo"), "Ridge 14 (oficial)": ("E14", "cota_Ridge14"),
         "Ensamble Ridge + LEAR": ("E14", "cota_Ens[Ridge14+LEAR]"),
         "Ridge 14 + costo marginal": ("E14", "cota_Ridge14+cmg2d"),
         "Ridge 14 con corrección de sesgo": ("E15", "cota_Ridge14_Duan"),
         "Ridge 14 + costo marginal 3 días": ("E15", "cota_Ridge14+cmg3d_Duan")}

EPISODIOS = {**ex.EPISODIOS_ESTRES, "Período de riesgo 2026": ("2026-09-07", "2026-12-31")}


def predicciones():
    """Pronósticos fuera de muestra de cada modelo, en las semanas que tienen todos los de E14."""
    tablas = {f: pd.read_parquet(RES / f"{f}_ancho.parquet") for f in {m[0] for m in MODELOS}}
    e14 = tablas["E14"]
    p = e14[["real", "base"]].copy()
    for archivo, col, nombre, *_ in MODELOS:
        p[nombre] = tablas[archivo][col].reindex(p.index)
    for nombre, (archivo, col) in COTAS.items():
        p[f"cota|{nombre}"] = tablas[archivo][col].reindex(p.index)
    p = p.dropna(subset=["real", "Ridge 14 (oficial)"])
    p.index.name = "semana_base"
    p.insert(0, "semana_objetivo", p.index + pd.Timedelta(weeks=1))
    return p


TIE = {"Regla XM": "Regla XM (repetir s-1)", "Regla XM + sáb-mar": "Regla con sábado a martes de s",
       "Ridge14": "Ridge 14", "Ridge14_Duan": "Ridge 14 con corrección de sesgo",
       "Ridge14+parcial": "Ridge 14 + sábado a martes de s",
       "Ridge14+parcial_Duan": "Ridge 14 + sábado a martes de s, con corrección de sesgo",
       "Registrado": "Modelo registrado (sábado a martes + costo marginal mié-vie, con corrección de sesgo)",
       "Registrado sin CMg": "Modelo anterior (sin costo marginal)",
       "Candidato": "Candidato en paralelo (+ hidrología hasta el jueves y martes)"}


def predicciones_tie():
    """E16: semana TIE de sábado a viernes, base s-1 y objetivo s+2 (tres semanas después)."""
    w = pd.read_parquet(RES / "E16_ancho.parquet")
    p = w[["real", "base"]].copy()
    for col, nombre in TIE.items():
        p[nombre] = w[col]
        p[f"cota|{nombre}"] = w[f"cota_{col}"]
    p = p.dropna(subset=["real", "Ridge 14"])
    p.index.name = "semana_base"
    p.insert(0, "semana_objetivo", p.index + pd.Timedelta(weeks=3))
    return p


def ultimo_tie():
    """Pronóstico TIE ilustrativo con los datos de hoy, sin registrar (emisión en seco).

    Usa la semana base más reciente que ya tiene sus días de sábado a martes publicados; la emisión
    oficial es la del registro, los viernes. Incluye el aporte de cada variable al cambio pronosticado.
    """
    import semanal_tie
    t = dp.tabla_tie(recalcular=True)
    listas = t.dropna(subset=["precio", "precio_parcial"]).index
    if listas.empty:
        return None
    base = listas.max()
    r = semanal_tie.emitir(base + pd.Timedelta(days=13), actualizar=False, guardar=False)
    rep = r["reproduccion"]
    x = np.array([r["variables"][v] for v in rep["variables"]])
    aporte = np.array(rep["coeficientes"]) * (x - np.array(rep["media"])) / np.array(rep["escala"])
    return {
        "fecha_calculo": f"{r['fecha_emision']:%Y-%m-%d}", "semana_base": f"{r['semana_base']:%Y-%m-%d}",
        "semana_objetivo": f"{r['semana_objetivo']:%Y-%m-%d}", "estado": r["estado"], "motivos": r["motivos"],
        "regla_xm": r["regla_xm"], "pronostico": r["pronostico"], "cota90": r["cota90"],
        "candidato": r["candidato"]["pronostico"] if r["candidato"] else None,
        "factor_duan": rep["factor_duan"], "intercepto": rep["intercepto"],
        "aportes": [{"variable": v, "nombre": config.NOMBRES.get(v, v), "aporte_log": float(a), "valor": float(r["variables"][v])}
                    for v, a in zip(rep["variables"], aporte)],
    }


EXPO = {"Regla XM": "Regla XM (repetir s-1)", "Regla sáb-mar": "Regla con sábado a martes de s",
        "Mitad Huber + mitad regla": "Modelo elegido (Huber + regla)", "Ens Huber+sáb-mar": "Huber + sábado a martes",
        "Huber expo": "Huber", "Nacional×spread 4s": "Precio nacional × diferencial",
        "Ens Ridge+Nac4s+sáb-mar": "Ridge + nacional + sábado a martes", "LightGBM expo": "LightGBM"}


def predicciones_expo():
    """E19: precio de exportación TIE (centUSD/kWh), semana s+2 desde s-1, semanas con exportación."""
    w = pd.read_parquet(RES / "E19_ancho.parquet")
    p = w[["real", "base"]].copy()
    for col, nombre in EXPO.items():
        p[nombre] = w[col]
        # El elegido usa la cota calibrada por régimen regulatorio (E20).
        p[f"cota|{nombre}"] = w[f"cota_regimen_{col}"] if f"cota_regimen_{col}" in w else w[f"cota_{col}"]
    p["regimen_expo"] = w.regimen_expo
    p = p.dropna(subset=["real"])
    p.index.name = "semana_base"
    p.insert(0, "semana_objetivo", p.index + pd.Timedelta(weeks=3))
    return p


COMPRA = {"Regla XM": "Regla XM (repetir s-1)", "Nacional×spread s-1": "Modelo compras TIE (nacional × diferencial)"}


def predicciones_compra():
    """E26: objetivo principal, precio de las compras TIE en bolsa (COP/kWh), s+2 desde s-1."""
    w = pd.read_parquet(RES / "E26_ancho.parquet")
    p = w[["real", "base"]].copy()
    for col, nombre in COMPRA.items():
        p[nombre] = w[col]
        p[f"cota|{nombre}"] = w[f"cota_{col}"]
    p = p.dropna(subset=["real"])
    p.index.name = "semana_base"
    p.insert(0, "semana_objetivo", p.index + pd.Timedelta(weeks=3))
    return p


def catalogo():
    return pd.DataFrame([{"modelo": n, "familia": f, "descripcion": d, "tiene_cota": n in COTAS}
                         for _, _, n, f, d in MODELOS])


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    p = predicciones()
    p.to_parquet(SALIDA / "predicciones.parquet")
    predicciones_tie().to_parquet(SALIDA / "predicciones_tie.parquet")
    predicciones_expo().to_parquet(SALIDA / "predicciones_expo.parquet")
    predicciones_compra().to_parquet(SALIDA / "predicciones_compra.parquet")
    te = dp.tabla_expo()
    te[["precio", "precio_expo_cop", "precio_expo", "energia_expo_gwh"]].to_parquet(SALIDA / "contexto_expo.parquet")
    with open(SALIDA / "ultimo_tie.json", "w", encoding="utf-8") as f:
        json.dump(ultimo_tie(), f, ensure_ascii=False, indent=1)
    reg_tie = RAIZ / "registro" / "pronosticos_tie.csv"
    if reg_tie.exists():
        (SALIDA / "registro_tie.csv").write_bytes(reg_tie.read_bytes())
    catalogo().to_csv(SALIDA / "modelos.csv", index=False)
    pd.DataFrame([{"episodio": k, "inicio": a, "fin": b} for k, (a, b) in EPISODIOS.items()]).to_csv(
        SALIDA / "episodios.csv", index=False)

    d = fe.preparar(dp.tabla_semanal(corregida=True))
    reg = pd.read_csv(RAIZ / "registro" / "pronosticos.csv", parse_dates=semanal.FECHAS)
    # Calificación provisional con el precio vigente, para las semanas ya publicadas aunque falte demanda.
    reg["real_provisional"] = d.precio.reindex(reg.semana_objetivo).to_numpy().round(2)
    reg.to_csv(SALIDA / "registro.csv", index=False)

    # Archivos que la app ya no usa (versiones anteriores): se borran para no confundir.
    for viejo in ("contexto.parquet", "ultimo.json", "E14_confusion.csv", "E14_resumen.csv"):
        (SALIDA / viejo).unlink(missing_ok=True)
    print(f"results/app: {len(p)} semanas ({p.index.min():%Y-%m-%d} a {p.index.max():%Y-%m-%d}), "
          f"{len(MODELOS)} modelos")


if __name__ == "__main__":
    main()
