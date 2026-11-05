"""Experimentos de la sección 5. Uso: python src/experimentos.py [e2|e3e4|e7|alertas|e8 [tx1]|e9 [viernes]|e5e6]

E0 (ingenuo y estacional) y E1 (baseline Ridge/GBoost de PAE) se corren desde
2014 para tener historial de calibración; las métricas se reportan desde 2018,
igual que el baseline, y por periodo del protocolo. E2 mide el aporte de las
variables exógenas con Ridge y ElasticNet.
"""

import json
import os
import sys

# Un hilo de BLAS por proceso: los modelos son pequeños y varios procesos en paralelo
# con 24 hilos cada uno se estorban.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import pandas as pd

import backtesting as bt
import calibration as cal
import config
import data_pipeline as dp
import evaluation as ev
import feature_engineering as fe
import models

INICIO = "2014-01-01"
INICIO_EVALUACION = "2018-01-01"


def correr_baseline(recalcular=False):
    d = fe.preparar(dp.tabla_semanal(recalcular))
    r = bt.backtest(d, models.E0 + models.E1, inicio=INICIO, cada=4)
    w = bt.ancho(r)
    w["Ridge_cota90"] = cal.conformal(w.real, w.Ridge, ventana=104)
    w["Ridge_cota90_vol"] = cal.conformal(w.real, w.Ridge, ventana=104, escala=d.volatilidad_4s)
    bt.guardar(r, "E0_E1")
    w.to_parquet(bt.RESULTADOS / "E0_E1_ancho.parquet")
    return d, w


def resumen(d, w):
    w = w[w.index >= INICIO_EVALUACION]
    modelos_ = ["Ingenuo", "Estacional", "Ridge", "GBoost"]
    out = {
        "puntuales": ev.puntuales(w, modelos_, ev.escala_mase(d)),
        "comparacion": ev.comparacion(w, modelos_),
        "por_periodo": ev.mae_por(w, modelos_, bt.periodo(w.index + pd.Timedelta(weeks=1))),
        "cotas": ev.cotas(w, ["GBoost_q90", "Ridge_cota90", "Ridge_cota90_vol"]),
    }
    for nombre, t in out.items():
        t.to_csv(bt.RESULTADOS / f"E0_E1_{nombre}.csv")
    return out


def configuraciones_e2():
    """Ridge con conjuntos de variables crecientes y leave-one-group-out; ElasticNet en los clave."""
    g, n = fe.GRUPOS, fe.GRUPOS_NUEVOS
    precio = g["precio"]
    nuevas = [v for grupo in n.values() for v in grupo]
    conjuntos = {"precio": precio}
    for k in ("calendario", "hidrologia", "ofertas", "termica", "enos"):
        conjuntos[f"precio+{k}"] = precio + g[k]
    for k in n:
        conjuntos[f"precio+{k}"] = precio + n[k]
    conjuntos["E1"] = fe.VARIABLES
    for k in ("hidrologia", "ofertas", "termica", "enos", "calendario"):
        conjuntos[f"E1-{k}"] = [v for v in fe.VARIABLES if v not in g[k]]
    # Añadida tras el leave-one-group-out: ENOS y térmica no aportaban en selección.
    conjuntos["E1-enos-termica"] = [v for v in fe.VARIABLES if v not in g["enos"] + g["termica"]]
    conjuntos["E1+nuevas"] = fe.VARIABLES + nuevas
    modelos_ = [models.Modelo("Ingenuo")]
    modelos_ += [models.Modelo(f"Ridge[{k}]", v, models.ridge) for k, v in conjuntos.items()]
    modelos_ += [models.Modelo(f"ENet[{k}]", conjuntos[k], models.elasticnet)
                 for k in ("precio", "E1", "E1+nuevas")]
    return modelos_


def correr_e2():
    """E2 sobre la tabla corregida. Mismas semanas de prueba y bloques que E1."""
    d = fe.preparar(dp.tabla_semanal(corregida=True))
    r = bt.backtest(d, configuraciones_e2(), inicio=INICIO, cada=4)
    bt.guardar(r, "E2")
    return d, bt.ancho(r)


def resumen_comparativo(w, experimento, referencia="Ridge[E1]"):
    """MAE y mejora frente al ingenuo por periodo; comparación pareada con E1 en selección."""
    w = w[w.index >= INICIO_EVALUACION]
    modelos_ = [c for c in w.columns if c not in ("real", "base")]
    periodos = bt.periodo(w.index + pd.Timedelta(weeks=1))
    mae = ev.mae_por(w, modelos_, periodos).T[["desarrollo", "seleccion", "final"]]
    mejora = (1 - mae / mae.loc["Ingenuo"]) * 100
    t = mae.add_prefix("MAE_").join(mejora.add_prefix("mejora_%_"))
    sel = w[periodos == "seleccion"]
    comp = ev.comparacion(sel, [m for m in modelos_ if m != "Ingenuo"], referencia=referencia)
    t = t.join(comp.add_suffix("_vs_E1_sel"))
    t.to_csv(bt.RESULTADOS / f"{experimento}_resumen.csv")
    return t


def configuraciones_e3e4():
    """LightGBM (E3) y XGBoost (E4) con hiperparámetros elegidos antes de 2018
    (`tuning.py`), frente a Ridge E1, su versión de 14 variables y el GBoost del baseline."""
    sin_enos_termica = [v for v in fe.VARIABLES if v not in fe.GRUPOS["enos"] + fe.GRUPOS["termica"]]
    lgb = json.loads((bt.RESULTADOS / "tuning_lightgbm.json").read_text())
    xgb = json.loads((bt.RESULTADOS / "tuning_xgboost.json").read_text())
    return [
        models.Modelo("Ingenuo"),
        models.Modelo("Ridge[E1]", fe.VARIABLES, models.ridge),
        models.Modelo("Ridge[E1-enos-termica]", sin_enos_termica, models.ridge),
        models.Modelo("GBoost[E1]", fe.VARIABLES, models.gboost),
        models.Modelo("LightGBM[E1,defecto]", fe.VARIABLES, models.lightgbm()),
        models.Modelo("LightGBM[E1]", fe.VARIABLES, models.lightgbm(**lgb)),
        models.Modelo("LightGBM[E1-enos-termica]", sin_enos_termica, models.lightgbm(**lgb)),
        models.Modelo("XGBoost[E1,defecto]", fe.VARIABLES, models.xgboost()),
        models.Modelo("XGBoost[E1]", fe.VARIABLES, models.xgboost(**xgb)),
        models.Modelo("XGBoost[E1-enos-termica]", sin_enos_termica, models.xgboost(**xgb)),
    ]


def correr_e3e4():
    d = fe.preparar(dp.tabla_semanal(corregida=True))
    r = bt.backtest(d, configuraciones_e3e4(), inicio=INICIO, cada=4)
    bt.guardar(r, "E3E4")
    return d, bt.ancho(r)


def regimenes(d):
    """Regímenes conocidos al emitir (cierre de la semana s), para la calibración Mondrian.

    vol: volatilidad de 4 semanas sobre su percentil 80 histórico (solo semanas previas).
    hidro: aportes de 4 semanas por debajo del 80 % de la media histórica.
    """
    umbral = d.volatilidad_4s.expanding(52).quantile(0.8)
    vol = (d.volatilidad_4s > umbral).astype(float)
    hidro = (d.aportes_pct_media_4s < 0.8).astype(float)
    return pd.DataFrame({"vol": vol, "hidro": hidro, "vol_o_hidro": ((vol + hidro) > 0).astype(float)})


def correr_e7():
    """E7: cotas superiores al 90 % sobre la tabla corregida.

    Puntos de partida: Ridge E1 (pronóstico puntual) y tres modelos cuantílicos
    (lineal con L1 = 0.02 elegido antes de 2018, LightGBM y el GBoost del baseline).
    """
    d = fe.preparar(dp.tabla_semanal(corregida=True))
    base = [
        models.Modelo("Ingenuo"),
        models.Modelo("Ridge", fe.VARIABLES, models.ridge),
        models.Modelo("QR_lineal_q90", fe.VARIABLES, models.cuantil_lineal(0.9, alpha=0.02)),
        models.Modelo("LightGBM_q90", fe.VARIABLES, models.lightgbm_cuantil(0.9)),
        models.Modelo("GBoost_q90", fe.VARIABLES, models.gboost_cuantil(0.9)),
    ]
    r = bt.backtest(d, base, inicio=INICIO, cada=4)
    bt.guardar(r, "E7_base")
    w = bt.ancho(r)
    reg = regimenes(d)

    c = pd.DataFrame(index=w.index)
    c["Ridge+conformal"] = cal.conformal(w.real, w.Ridge)  # referencia (baseline)
    c["Ridge+conformal_vol"] = cal.conformal(w.real, w.Ridge, escala=d.volatilidad_4s)
    for k in reg:
        c[f"Ridge+mondrian_{k}"] = cal.conformal_regimen(w.real, w.Ridge, reg[k])
    for g in (0.005, 0.01, 0.02, 0.05):
        c[f"Ridge+ACI_{g}"] = cal.conformal_adaptativo(w.real, w.Ridge, gamma=g)
        c[f"Ridge+ACI_vol_{g}"] = cal.conformal_adaptativo(w.real, w.Ridge, gamma=g, escala=d.volatilidad_4s)
    for q in ("QR_lineal_q90", "LightGBM_q90", "GBoost_q90"):
        c[q] = w[q]
        c[f"{q}+CQR"] = cal.conformal(w.real, w[q])
        c[f"{q}+CQR_mondrian_vol"] = cal.conformal_regimen(w.real, w[q], reg["vol"])
    c.insert(0, "real", w.real)
    c.insert(1, "base", w.base)
    c.to_parquet(bt.RESULTADOS / "E7_cotas.parquet")
    return d, c, reg


def resumen_e7(c, reg):
    c = c[c.index >= INICIO_EVALUACION]
    cotas = [x for x in c.columns if x not in ("real", "base")]
    periodos = bt.periodo(c.index + pd.Timedelta(weeks=1))
    tablas = []
    for p in ("desarrollo", "seleccion", "final"):
        sub = c[periodos == p]
        t = ev.cotas(sub, cotas)
        r = reg.reindex(sub.index)
        t["cobertura_regimen_vol"] = [(sub.real <= sub[x])[r.vol == 1].mean() for x in cotas]
        t["cobertura_regimen_hidro"] = [(sub.real <= sub[x])[r.hidro == 1].mean() for x in cotas]
        tablas.append(t.add_prefix(f"{p}:"))
    t = pd.concat(tablas, axis=1)
    total = ev.cotas(c, cotas).add_prefix("2018-2026:")
    t = t.join(total).sort_values("seleccion:pinball")
    t.to_csv(bt.RESULTADOS / "E7_resumen.csv")
    return t


def correr_alertas():
    """Modelo C: backtest de alertas, métricas por periodo e importancia SHAP en selección."""
    import alertas

    d = fe.preparar(dp.tabla_semanal(corregida=True))
    r = alertas.backtest_alertas(d, inicio=INICIO)
    r.to_parquet(bt.RESULTADOS / "alertas.parquet", index=False)
    t = alertas.evaluar(r[r.semana_base >= INICIO_EVALUACION])
    t.to_csv(bt.RESULTADOS / "alertas_resumen.csv", index=False)
    imp = pd.DataFrame({e.nombre: alertas.importancia_shap(d, e.nombre) for e in alertas.EVENTOS})
    imp = imp.loc[imp.mean(axis=1).sort_values(ascending=False).index]
    imp.to_csv(bt.RESULTADOS / "alertas_shap_seleccion.csv")
    return d, r, t, imp


def configuraciones_e8():
    """Ridge E1 y su versión de 14 variables, más cada grupo de datos nuevos y todos juntos;
    LightGBM por defecto con todo, por si el margen de reserva actúa de forma no lineal."""
    g8 = fe.GRUPOS_E8
    nuevas = [v for grupo in g8.values() for v in grupo]
    e1_14 = [v for v in fe.VARIABLES if v not in fe.GRUPOS["enos"] + fe.GRUPOS["termica"]]
    conjuntos = {"E1": fe.VARIABLES, "E1-enos-termica": e1_14}
    for k, v in g8.items():
        conjuntos[f"E1+{k}"] = fe.VARIABLES + v
    conjuntos["E1+e8"] = fe.VARIABLES + nuevas
    conjuntos["E1-enos-termica+e8"] = e1_14 + nuevas
    conjuntos["precio+e8"] = fe.GRUPOS["precio"] + nuevas
    modelos_ = [models.Modelo("Ingenuo")]
    modelos_ += [models.Modelo(f"Ridge[{k}]", v, models.ridge) for k, v in conjuntos.items()]
    modelos_ += [models.Modelo("LightGBM[E1+e8,defecto]", fe.VARIABLES + nuevas, models.lightgbm())]
    return modelos_


def correr_e8(tx1=False):
    """Con `tx1=True`, las variables de precio de la semana s usan la versión TX1
    (la disponible al emitir); el precio objetivo sigue siendo el vigente."""
    tabla = dp.tabla_semanal_tx1() if tx1 else dp.tabla_semanal_e8()
    d = fe.preparar(tabla)
    r = bt.backtest(d, configuraciones_e8(), inicio=INICIO, cada=4)
    bt.guardar(r, "E8_tx1" if tx1 else "E8")
    return d, bt.ancho(r)


def configuraciones_e9():
    """Ridge E1 con variables diarias y de despacho programado; modelo en dos etapas
    con sus tres modos de combinación, con y sin esas variables."""
    nuevas = [v for g in fe.GRUPOS_NUEVOS.values() for v in g]
    e9 = [v for g in fe.GRUPOS_E9.values() for v in g]
    m = [models.Modelo("Ingenuo"), models.Modelo("Ridge[E1]", fe.VARIABLES, models.ridge)]
    for k, v in fe.GRUPOS_E9.items():
        m.append(models.Modelo(f"Ridge[E1+{k}]", fe.VARIABLES + v, models.ridge))
    m.append(models.Modelo("Ridge[E1+e9]", fe.VARIABLES + e9, models.ridge))
    for modo in ("media", "duro", "apilado"):
        m.append(models.DosEtapas(f"DosEtapas_{modo}[E1]", fe.VARIABLES, fe.VARIABLES + nuevas, modo))
    m.append(models.DosEtapas("DosEtapas_media[E1+e9]", fe.VARIABLES + e9, fe.VARIABLES + nuevas + e9, "media"))
    m.append(models.DosEtapas("DosEtapas_apilado[E1+e9]", fe.VARIABLES + e9, fe.VARIABLES + nuevas + e9, "apilado"))
    return m


def correr_e9(ultimo_dia=6):
    """E9 con la información de la semana s hasta `ultimo_dia` (6 = domingo, 4 = viernes)."""
    d = fe.preparar(dp.tabla_e9(ultimo_dia))
    r = bt.backtest(d, configuraciones_e9(), inicio=INICIO, cada=4, progreso=True)
    nombre = f"E9_corte{ultimo_dia}"
    bt.guardar(r, nombre)
    return nombre, bt.ancho(r)


def ensambles(w, ventana=52):
    """E6: ensambles en escala de precio, formados después del backtest con pronósticos
    fuera de muestra. Los pesos adaptativos usan solo errores de semanas anteriores
    (la semana s-1 ya está calificada al emitir s)."""
    w = w.copy()
    w["Ens[Ridge14+LightGBM]"] = w[["Ridge14", "LightGBM"]].mean(axis=1)
    w["Ens[Ridge14+LightGBM+SARIMAX]"] = w[["Ridge14", "LightGBM", "SARIMAX"]].mean(axis=1)
    miembros = ["Ridge14", "LightGBM", "SARIMAX"]
    err = pd.DataFrame({m: (w[m] - w.real).abs() for m in miembros})
    inv = 1 / err.rolling(ventana, min_periods=26).mean().shift(1)
    pesos = inv.div(inv.sum(axis=1), axis=0)
    w["Ens[pesos por error]"] = (w[miembros] * pesos).sum(axis=1).where(pesos.notna().all(axis=1))
    return w


def correr_e5e6():
    """E5 (SARIMAX) frente al modelo principal y sus alternativas, más los ensambles de E6."""
    d = fe.preparar(dp.tabla_semanal(corregida=True))
    m = [models.Modelo("Ingenuo"),
         models.Modelo("Ridge14", config.VARIABLES, models.ridge),
         models.Modelo("Ridge19", fe.VARIABLES, models.ridge),
         models.Modelo("LightGBM", fe.VARIABLES, models.lightgbm()),
         models.Sarimax("SARIMAX", config.VARIABLES)]
    r = bt.backtest(d, m, inicio=INICIO, cada=4, progreso=True)
    bt.guardar(r, "E5E6")
    w = ensambles(bt.ancho(r))
    w.to_parquet(bt.RESULTADOS / "E5E6_ancho.parquet")
    return w


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.float_format", "{:,.3f}".format)
    if "e5e6" in sys.argv[1:]:
        w = correr_e5e6()
        print(resumen_comparativo(w.dropna(), "E5E6", referencia="Ridge14").to_string())
    elif "e9" in sys.argv[1:]:
        nombre, w = correr_e9(4 if "viernes" in sys.argv[1:] else 6)
        print(resumen_comparativo(w, nombre).to_string())
    elif "e8" in sys.argv[1:]:
        tx1 = "tx1" in sys.argv[1:]
        _, w = correr_e8(tx1)
        print(resumen_comparativo(w, "E8_tx1" if tx1 else "E8").to_string())
    elif "alertas" in sys.argv[1:]:
        _, _, t, imp = correr_alertas()
        print(t.to_string())
        print(imp.head(10).to_string())
    elif "e7" in sys.argv[1:]:
        _, c, reg = correr_e7()
        print(resumen_e7(c, reg).to_string())
    elif "e2" in sys.argv[1:]:
        _, w = correr_e2()
        print(resumen_comparativo(w, "E2").to_string())
    elif "e3e4" in sys.argv[1:]:
        _, w = correr_e3e4()
        print(resumen_comparativo(w, "E3E4").to_string())
    else:
        d, w = correr_baseline()
        for nombre, t in resumen(d, w).items():
            print(f"\n== {nombre}\n{t}")
