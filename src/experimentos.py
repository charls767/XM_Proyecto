"""Experimentos de evaluación. Uso: python src/experimentos.py <comando> [opción]

Comandos: e1 (por defecto), e2, e3e4, e5e6, e7, e8 [tx1], e9 [viernes], e10, e11 [viernes], e12, e13, e14,
cortes, tuning y alertas [e8]. Cada uno escribe sus archivos en results/; el
detalle de cada experimento está en docs/EXPERIMENTOS.md.

Todos se corren desde 2014 para tener historial de calibración y se reportan desde
2018 y por periodo del protocolo (desarrollo, selección, final).
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
    for nombre, sub in (("seleccion", c[periodos == "seleccion"]), ("2018-2026", c)):
        ev.comparacion_cotas(sub, cotas, "Ridge+conformal").sort_values("dif_pinball").to_csv(
            bt.RESULTADOS / f"E7_comparacion_pinball_{nombre}.csv")
    return t


def correr_e11(ultimo_dia=6):
    """E11: LEAR diario agregado a la semana y promedio de ventanas, frente a Ridge 14."""
    import lear

    d = fe.preparar(dp.tabla_e9(ultimo_dia))
    t = dp.tabla_diaria()
    prog = fe.GRUPOS_E9["programado"]
    m = [models.Modelo("Ingenuo"),
         models.Modelo("Ridge14", config.VARIABLES, models.ridge),
         models.Modelo("Ridge14+programado", config.VARIABLES + prog, models.ridge),
         lear.VentanasRidge("Ridge14_ventanas", config.VARIABLES, models.ridge),
         lear.VentanasRidge("Ridge14+programado_ventanas", config.VARIABLES + prog, models.ridge),
         lear.LEAR("LEAR_bottomup", t, ultimo_dia, "bottomup"),
         lear.LEAR("LEAR_bottomup_ventanas", t, ultimo_dia, "bottomup", lear.VENTANAS),
         lear.LEAR("LEAR_directo", t, ultimo_dia, "directo"),
         lear.LEAR("LEAR_directo_ventanas", t, ultimo_dia, "directo", lear.VENTANAS)]
    r = bt.backtest(d, m, inicio=INICIO, cada=4, progreso=True, embargo=0 if ultimo_dia == 6 else 1)
    nombre = f"E11_corte{ultimo_dia}"
    bt.guardar(r, nombre)
    w = bt.ancho(r)
    w = ensambles_e11(w)
    w.to_parquet(bt.RESULTADOS / f"{nombre}_ancho.parquet")
    return nombre, w


def ensambles_e11(w):
    w = w.copy()
    w["Ens[Ridge14+LEAR_directo]"] = w[["Ridge14", "LEAR_directo"]].mean(axis=1)
    w["Ens[Ridge14+LEAR_directo_v]"] = w[["Ridge14", "LEAR_directo_ventanas"]].mean(axis=1)
    w["Ens[Ridge14+LEAR_bottomup_v]"] = w[["Ridge14", "LEAR_bottomup_ventanas"]].mean(axis=1)
    return w


def correr_alertas_e8():
    """Alertas de salto y precio alto con las variables de disponibilidad y escasez de E8."""
    import alertas

    d = fe.preparar(dp.tabla_semanal_e8())
    nuevas = [v for g in fe.GRUPOS_E8.values() for v in g]
    r = alertas.backtest_alertas(d, inicio=INICIO, extra=nuevas, solo=["salto", "precio_alto"])
    r.to_parquet(bt.RESULTADOS / "alertas_e8.parquet", index=False)
    t = alertas.evaluar(r[r.semana_base >= INICIO_EVALUACION])
    t.to_csv(bt.RESULTADOS / "alertas_e8_resumen.csv", index=False)
    return t


def cotas_con_alerta():
    """Cotas de E7 con régimen Mondrian dado por la alerta de salto (requiere haber corrido alertas)."""
    archivo = bt.RESULTADOS / "alertas.parquet"
    c = pd.read_parquet(bt.RESULTADOS / "E7_cotas.parquet")
    if not archivo.exists():
        return c
    w = bt.ancho(bt.cargar("E7_base"))
    s = pd.read_parquet(archivo).query("evento == 'salto'").set_index("semana_base")
    # El umbral se fija una vez por modelo; el resumen lo repite en cada periodo.
    umbrales = pd.read_csv(bt.RESULTADOS / "alertas_resumen.csv").query("evento == 'salto'").groupby("modelo").umbral.first()
    for modelo, sufijo in (("Logistica", ""), ("LightGBM", "_lgbm")):
        regimen = (s[modelo].reindex(w.index) >= umbrales[modelo]).astype(float).fillna(0)
        c[f"Ridge+mondrian_alerta_salto{sufijo}"] = cal.conformal_regimen(w.real, w.Ridge, regimen)
    c.to_parquet(bt.RESULTADOS / "E7_cotas.parquet")
    return c


def correr_cortes():
    """Ridge E1 frente al ingenuo con la semana base conocida hasta domingo, sábado, viernes o jueves."""
    filas = {}
    for k, nombre in ((6, "domingo"), (5, "sabado"), (4, "viernes"), (3, "jueves")):
        d = fe.preparar(dp.tabla_semanal_corte(k))
        r = bt.backtest(d, [models.Modelo("Ingenuo"), models.Modelo("Ridge", fe.VARIABLES, models.ridge)], inicio=INICIO,
                        embargo=0 if k == 6 else 1)
        bt.guardar(r, f"cortes_corte{k}")
        w = bt.ancho(r)
        w = w[w.index >= INICIO_EVALUACION]
        p = ev.puntuales(w, ["Ingenuo", "Ridge"], 1.0)
        filas[nombre] = {"MAE_ingenuo": p.loc["Ingenuo", "MAE"], "MAE_ridge": p.loc["Ridge", "MAE"],
                         "mejora_%": p.loc["Ridge", "mejora_MAE_%"]}
    t = pd.DataFrame(filas).T
    t.to_csv(bt.RESULTADOS / "cortes_resumen.csv")
    return t


EPISODIOS_ESTRES = {"Nino 2015-16": ("2015-08-01", "2016-05-31"),
                    "Sequia 2023-24": ("2023-09-01", "2024-06-30"),
                    "Estres oct-2024": ("2024-08-01", "2024-12-31")}


def correr_e10():
    """E10: Ridge de 19, 14 y 12 variables; estabilidad de coeficientes y episodios de estrés."""
    import numpy as np

    d = fe.preparar(dp.tabla_semanal(corregida=True))
    e14 = [v for v in fe.VARIABLES if v not in fe.GRUPOS["enos"] + fe.GRUPOS["termica"]]
    e12 = [v for v in e14 if v not in ("max_h_rel", "aportes_pct_media")]
    conjuntos = {"Ridge19": fe.VARIABLES, "Ridge14": e14, "Ridge12": e12}
    m = [models.Modelo("Ingenuo")] + [models.Modelo(k, v, models.ridge) for k, v in conjuntos.items()]
    r = bt.backtest(d, m, inicio=INICIO)
    bt.guardar(r, "E10_parsimonia")
    w = bt.ancho(r)
    for k in conjuntos:
        w[f"cota_{k}"] = cal.conformal(w.real, w[k])
    w.to_parquet(bt.RESULTADOS / "E10_parsimonia_ancho.parquet")

    completas = d.dropna(subset=fe.VARIABLES + ["y"])
    for k, cols in (("E1", fe.VARIABLES), ("14", e14)):
        coef = {}
        for anio in range(2014, 2027):
            ent = completas[completas.index < f"{anio}-01-01"]
            coef[anio] = pd.Series(models.ridge().fit(ent[cols], ent.y)[-1].coef_, index=cols)
        pd.DataFrame(coef).T.to_csv(bt.RESULTADOS / f"estabilidad_coef_{k}.csv")

    filas = []
    for episodio, (a, b) in EPISODIOS_ESTRES.items():
        s = w[(w.index >= a) & (w.index <= b)]
        for k in ["Ingenuo", *conjuntos]:
            filas.append({"episodio": episodio, "modelo": k, "semanas": len(s),
                          "MAE": (s[k] - s.real).abs().mean(), "sesgo": (s[k] - s.real).mean(),
                          "cobertura": (s.real <= s[f"cota_{k}"]).mean() if k != "Ingenuo" else np.nan})
    pd.DataFrame(filas).to_csv(bt.RESULTADOS / "E10_estres.csv", index=False)
    return w


def correr_tuning():
    """Hiperparámetros de LightGBM, XGBoost y del clasificador de dos etapas, solo con semanas antes de 2018."""
    import tuning

    d = fe.preparar(dp.tabla_semanal(corregida=True))
    out = {f: tuning.buscar(f, c, d, fe.VARIABLES)[0]
           for f, c in (("lightgbm", models.lightgbm), ("xgboost", models.xgboost))}
    d9 = fe.preparar(dp.tabla_e9(6))
    out["dosetapas"] = tuning.elegir_c_dosetapas(d9)
    return out


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
    r = bt.backtest(d, configuraciones_e9(), inicio=INICIO, cada=4, progreso=True, embargo=0 if ultimo_dia == 6 else 1)
    nombre = f"E9_corte{ultimo_dia}"
    bt.guardar(r, nombre)
    return nombre, bt.ancho(r)


def configuraciones_e12():
    """Ridge 14 con el costo marginal programado de los primeros k días de la semana objetivo,
    y la regla sin parámetros «ingenuo × cambio del costo marginal»."""
    m = [models.Modelo("Ingenuo"), models.Modelo("Ridge14", config.VARIABLES, models.ridge)]
    for k in dp.DIAS_CMG:
        m.append(models.Modelo(f"Regla_cmg{k}d", columna_referencia=f"regla_cmg{k}d"))
    for k in dp.DIAS_CMG:
        m.append(models.Modelo(f"Ridge14+cmg{k}d", config.VARIABLES + [f"cmg_{k}d_rel", "cmg_brecha"], models.ridge))
    m.append(models.Modelo("Ridge_solo_cmg3d", ["cmg_3d_rel", "cmg_brecha"], models.ridge))
    return m


def correr_e12():
    """E12: costo marginal del despacho programado (`CostMargDesp`) de la semana objetivo,
    conocido al emitir el miércoles. Semana base completa, sin embargo adicional."""
    import numpy as np

    d = fe.preparar(dp.tabla_e12())
    for k in dp.DIAS_CMG:
        d[f"regla_cmg{k}d"] = d.precio * np.exp(d[f"cmg_{k}d_rel"])
    r = bt.backtest(d, configuraciones_e12(), inicio=INICIO, cada=4, progreso=True)
    bt.guardar(r, "E12")
    w = bt.ancho(r)
    for c in ("Ridge14", "Ridge14+cmg2d", "Ridge14+cmg3d"):
        w[f"cota_{c}"] = cal.conformal(w.real, w[c], ventana=config.VENTANA_CONFORMAL)
    w.to_parquet(bt.RESULTADOS / "E12_ancho.parquet")
    return w


def resumen_e12(w):
    """MAE por periodo, diferencia contra Ridge 14 en 2018–2026 y por periodo, reality check,
    sesgo y cotas."""
    w = w[w.index >= INICIO_EVALUACION]
    puntuales = [c for c in w.columns if c not in ("real", "base") and not c.startswith("cota_")]
    periodos = bt.periodo(w.index + pd.Timedelta(weeks=1))
    t = ev.mae_por(w, puntuales, periodos).T[["desarrollo", "seleccion", "final"]].add_prefix("MAE_")
    t.insert(0, "MAE_2018-2026", w[puntuales].sub(w.real, axis=0).abs().mean())
    t["mejora_%_vs_ingenuo"] = (1 - t["MAE_2018-2026"] / t.loc["Ingenuo", "MAE_2018-2026"]) * 100
    t["sesgo"] = w[puntuales].sub(w.real, axis=0).mean()
    for nombre, mascara in (("2018-2026", slice(None)), ("seleccion", periodos == "seleccion"),
                            ("final", periodos == "final")):
        c = ev.comparacion(w[mascara], [m for m in puntuales if m != "Ridge14"], referencia="Ridge14")
        t = t.join(c[["dif_MAE", "IC95_inf", "IC95_sup", "p_DM"]].add_suffix(f"_vs_Ridge14_{nombre}"))
    t.to_csv(bt.RESULTADOS / "E12_resumen.csv")

    ref = (w.Ridge14 - w.real).abs()
    familia = [m for m in puntuales if m not in ("Ingenuo", "Ridge14")]
    rc = ev.reality_check(ref, w[familia].sub(w.real, axis=0).abs())
    cotas = ev.cotas(w, [c for c in w.columns if c.startswith("cota_")])
    cotas.to_csv(bt.RESULTADOS / "E12_cotas.csv")
    pd.Series(rc).to_csv(bt.RESULTADOS / "E12_reality_check.csv")
    return t, cotas, rc


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


def configuraciones_e13():
    """ARIMA puro, término AR dentro de Ridge y variables en frecuencia (armónicos y STFT)."""
    v, g = config.VARIABLES, fe.GRUPOS_E13
    todo = g["stft_precio"] + g["stft_aportes"] + g["stft_demanda"] + g["armonico2"]
    return [models.Modelo("Ingenuo"),
            models.Modelo("Ridge14", v, models.ridge),
            models.ArimaAuto("ARIMA_auto"),
            models.Modelo("Ridge14+AR2", v + ["rezago_2_rel"], models.ridge),
            models.Modelo("Ridge14+armonico2", v + g["armonico2"], models.ridge),
            models.Modelo("Ridge14+STFT_precio", v + g["stft_precio"], models.ridge),
            models.Modelo("Ridge14+STFT_aportes", v + g["stft_aportes"], models.ridge),
            models.Modelo("Ridge14+STFT_demanda", v + g["stft_demanda"], models.ridge),
            models.Modelo("Ridge14+STFT_todo+arm2", v + todo, models.ridge),
            models.Modelo("LightGBM14+STFT_todo", v + todo, models.lightgbm())]


def correr_e13():
    """E13: ¿ARIMA o variables en el dominio de la frecuencia mejoran a Ridge 14?
    Mismas semanas y bloques que E5/E6, sobre la tabla corregida."""
    d = fe.agregar_stft(fe.preparar(dp.tabla_semanal(corregida=True)), dp.tabla_diaria())
    m = configuraciones_e13()
    r = bt.backtest(d, m, inicio=INICIO, cada=4, progreso=True)
    bt.guardar(r, "E13")
    arima = next(x for x in m if x.nombre == "ARIMA_auto")
    pd.Series({a: f"ARIMA{o[0]},1,{o[2]}" for a, o in arima.ordenes.items()}, name="orden").to_csv(
        bt.RESULTADOS / "E13_ordenes_arima.csv", index_label="anio")
    w = bt.ancho(r)
    w["Ens[Ridge14+ARIMA]"] = w[["Ridge14", "ARIMA_auto"]].mean(axis=1)
    w.to_parquet(bt.RESULTADOS / "E13_ancho.parquet")
    return w


def resumen_e13(w):
    """MAE por periodo y comparación pareada con Ridge 14; reality check de la familia."""
    w = w[w.index >= INICIO_EVALUACION].dropna()
    periodos = bt.periodo(w.index + pd.Timedelta(weeks=1))
    mods = [c for c in w.columns if c not in ("real", "base")]
    mae = ev.mae_por(w, mods, periodos).T[["desarrollo", "seleccion", "final"]]
    t = mae.add_prefix("MAE_")
    t.insert(0, "MAE_2018-2026", w[mods].sub(w.real, axis=0).abs().mean())
    t["mejora_%_vs_ingenuo"] = (1 - t["MAE_2018-2026"] / t.loc["Ingenuo", "MAE_2018-2026"]) * 100
    for nombre, mascara in (("2018-2026", slice(None)), ("seleccion", periodos == "seleccion")):
        c = ev.comparacion(w[mascara], [m for m in mods if m != "Ridge14"], referencia="Ridge14")
        t = t.join(c[["dif_MAE", "IC95_inf", "IC95_sup", "p_DM"]].add_suffix(f"_vs_Ridge14_{nombre}"))
    t.to_csv(bt.RESULTADOS / "E13_resumen.csv")
    sel = w[periodos == "seleccion"]
    familia = [m for m in mods if m not in ("Ingenuo", "Ridge14")]
    rc = ev.reality_check((sel.Ridge14 - sel.real).abs(), sel[familia].sub(sel.real, axis=0).abs())
    pd.Series(rc).to_csv(bt.RESULTADOS / "E13_reality_check.csv")
    diagnostico_e13(w)
    return t, rc


def diagnostico_e13(w):
    """Autocorrelación del error fuera de muestra (Ljung-Box) y picos del espectro de Welch
    de las series semanales y diarias. Picos: razón entre la potencia y la mediana móvil
    de 9 frecuencias vecinas."""
    import numpy as np
    from scipy import signal
    from statsmodels.stats.diagnostic import acorr_ljungbox
    from statsmodels.tsa.stattools import acf

    filas = []
    for m in ("Ingenuo", "Ridge14", "Ridge14+AR2"):
        e = np.log(w.real / w[m]).dropna()
        lb = acorr_ljungbox(e, lags=[4, 13, 52]).lb_pvalue
        r = acf(e, nlags=2)
        filas.append({"tipo": "ljung_box", "serie": f"error {m}", "acf1": r[1], "acf2": r[2],
                      "p_lag4": lb[4], "p_lag13": lb[13], "p_lag52": lb[52]})

    d = fe.preparar(dp.tabla_semanal(corregida=True))
    dia = dp.tabla_diaria()
    series = {"log precio semanal": (np.log(d.precio), 260, "semanas"),
              "embalse semanal": (d.embalse_cierre, 260, "semanas"),
              "aportes semanales": (d.aportes_pct_media, 260, "semanas"),
              "error Ridge14": (np.log(w.real / w.Ridge14), 156, "semanas"),
              "log precio diario": (np.log(dia.precio.clip(lower=1)), 364, "dias"),
              "log demanda diaria": (np.log(dia.demanda), 364, "dias"),
              "log aportes diarios": (np.log(dia.aportes.clip(lower=1)), 364, "dias")}
    for nombre, (x, nper, unidad) in series.items():
        x = x.dropna().to_numpy()
        f, p = signal.welch(x, fs=1, nperseg=min(nper, len(x)), detrend="linear")
        f, p = f[1:], p[1:]
        razon = p / pd.Series(p).rolling(9, center=True, min_periods=1).median().to_numpy()
        for i in np.argsort(razon)[::-1][:3]:
            filas.append({"tipo": "pico_espectral", "serie": nombre, "periodo": 1 / f[i],
                          "unidad": unidad, "razon_sobre_fondo": razon[i]})
    t = pd.DataFrame(filas)
    t.to_csv(bt.RESULTADOS / "E13_diagnostico.csv", index=False)
    return t


CLASES = ("Baja", "Estable", "Sube")  # cambio < −20 %, entre ambos, ≥ +25 % (umbrales de DosEtapas)


def clase_cambio(cambio_log):
    import numpy as np
    return pd.Series(np.digitize(cambio_log, models.DosEtapas.UMBRALES), index=cambio_log.index).map(dict(enumerate(CLASES)))


def correr_e14():
    """E14: los tres modelos que se registran (oficial y dos candidatos) en un mismo walk-forward.

    E11 y E12 usaban bloques distintos, así que sus Ridge 14 no coinciden; aquí todos se
    evalúan en las mismas semanas y con los mismos reentrenamientos.
    """
    import lear

    d = fe.preparar(dp.tabla_e12())
    v_cmg = config.VARIABLES_CANDIDATO_CMG
    m = [models.Modelo("Ingenuo"),
         models.Modelo("Ridge14", config.VARIABLES, models.ridge),
         lear.LEAR("LEAR_directo", dp.tabla_diaria(), 6, "directo"),
         models.Modelo("Ridge14+cmg2d", v_cmg, models.ridge)]
    r = bt.backtest(d, m, inicio=INICIO, cada=4, progreso=True, requeridas=sorted(set(v_cmg) | {"y"}))
    bt.guardar(r, "E14")
    w = bt.ancho(r)
    w["Ens[Ridge14+LEAR]"] = w[["Ridge14", "LEAR_directo"]].mean(axis=1)
    for c in ("Ingenuo", "Ridge14", "Ens[Ridge14+LEAR]", "Ridge14+cmg2d"):
        w[f"cota_{c}"] = cal.conformal(w.real, w[c], ventana=config.VENTANA_CONFORMAL)
    w.to_parquet(bt.RESULTADOS / "E14_ancho.parquet")
    return w


def resumen_e14(w):
    """Error, sesgo, cota y significancia; matrices de confusión del sentido y del tamaño del cambio."""
    import numpy as np

    w = w[w.index >= INICIO_EVALUACION].dropna(subset=["real"])
    modelos_ = {"Ingenuo": "Referencia simple", "Ridge14": "Oficial (Ridge 14)",
                "Ens[Ridge14+LEAR]": "Candidato 1 (Ridge 14 + LEAR)", "Ridge14+cmg2d": "Candidato 2 (Ridge 14 + CMg 2 días)"}
    periodos = bt.periodo(w.index + pd.Timedelta(weeks=1))
    real_cambio = np.log(w.real / w.base)
    alta = ev.alta_variabilidad_ex_post(w)
    filas, matrices = [], []
    for m, nombre in modelos_.items():
        e = w[m] - w.real
        cubre = w.real <= w[f"cota_{m}"]
        pred_cambio = np.log(w[m] / w.base)
        fila = {"modelo": nombre, "MAE": e.abs().mean(), "sesgo": e.mean(),
                **{f"MAE_{p}": e[periodos == p].abs().mean() for p in ("desarrollo", "seleccion", "final")},
                "MAE_52s": e.tail(52).abs().mean(), "sesgo_52s": e.tail(52).mean(),
                "cobertura": cubre.mean(), "cobertura_saltos": cubre[alta].mean(),
                "exceso_cota_%": ((w[f"cota_{m}"] - w.real) / w.real)[cubre].mean() * 100}
        if m != "Ridge14":
            est, p = ev.diebold_mariano(w, m, "Ridge14")
            lo, hi = ev.ic_diferencia_mae(w, m, "Ridge14")
            fila.update(dif_vs_oficial=e.abs().mean() - (w.Ridge14 - w.real).abs().mean(), IC95_inf=lo, IC95_sup=hi, p_DM=p)
        # Sentido del cambio (el ingenuo no predice cambio: no tiene sentido).
        if m != "Ingenuo":
            fila["acierto_sentido_%"] = ((pred_cambio > 0) == (real_cambio > 0)).mean() * 100
        # Tamaño del cambio en tres clases.
        pc, rc = clase_cambio(pred_cambio), clase_cambio(real_cambio)
        cm = pd.crosstab(rc, pc).reindex(index=CLASES, columns=CLASES, fill_value=0)
        fila["acierto_clase_%"] = np.trace(cm.to_numpy()) / cm.to_numpy().sum() * 100
        for k in ("Baja", "Sube"):
            fila[f"recall_{k}_%"] = cm.at[k, k] / cm.loc[k].sum() * 100
            fila[f"precision_{k}_%"] = cm.at[k, k] / cm[k].sum() * 100 if cm[k].sum() else np.nan
        filas.append(fila)
        matrices.append(cm.rename_axis(index="real", columns="pronosticado").stack().rename("semanas")
                        .reset_index().assign(modelo=nombre, tipo="tamano"))
        if m != "Ingenuo":
            sentido = pd.crosstab(np.where(real_cambio > 0, "Sube", "Baja"), np.where(pred_cambio > 0, "Sube", "Baja"))
            sentido = sentido.reindex(index=["Baja", "Sube"], columns=["Baja", "Sube"], fill_value=0)
            matrices.append(sentido.rename_axis(index="real", columns="pronosticado").stack().rename("semanas")
                            .reset_index().assign(modelo=nombre, tipo="sentido"))
    t = pd.DataFrame(filas).set_index("modelo")
    t.to_csv(bt.RESULTADOS / "E14_resumen.csv")
    cms = pd.concat(matrices, ignore_index=True)
    cms.to_csv(bt.RESULTADOS / "E14_confusion.csv", index=False)

    # Alerta de salto (logística con el umbral fijado en desarrollo), como clasificador binario.
    a = pd.read_parquet(bt.RESULTADOS / "alertas.parquet").query("evento == 'salto' and semana_base >= @INICIO_EVALUACION")
    u = pd.read_csv(bt.RESULTADOS / "alertas_resumen.csv").query("evento == 'salto' and modelo == 'Logistica'").umbral.iloc[0]
    alerta = pd.crosstab(a.observado.map({0: "Sin salto", 1: "Salto"}), (a.Logistica >= u).map({False: "Sin alerta", True: "Alerta"}))
    alerta = alerta.reindex(index=["Sin salto", "Salto"], columns=["Sin alerta", "Alerta"], fill_value=0)
    alerta.to_csv(bt.RESULTADOS / "E14_confusion_alerta_salto.csv")
    return t, cms, alerta


def configuraciones_e15():
    """Ridge 14 y Ridge 14 + costo marginal (2 y 3 días), cada uno con y sin la corrección de Duan,
    y el oficial con alpha elegido por validación temporal en vez de leave-one-out."""
    v2 = config.VARIABLES + ["cmg_2d_rel", "cmg_brecha"]
    v3 = config.VARIABLES + ["cmg_3d_rel", "cmg_brecha"]
    return [models.Modelo("Ingenuo"),
            models.Modelo("Ridge14", config.VARIABLES, models.ridge),
            models.Modelo("Ridge14_alpha_temporal", config.VARIABLES, models.ridge_temporal),
            models.Duan("Ridge14_Duan", config.VARIABLES, models.ridge),
            models.Modelo("Ridge14+cmg2d", v2, models.ridge),
            models.Duan("Ridge14+cmg2d_Duan", v2, models.ridge),
            models.Modelo("Ridge14+cmg3d", v3, models.ridge),
            models.Duan("Ridge14+cmg3d_Duan", v3, models.ridge)]


def correr_e15():
    """E15: costo marginal de 3 días, corrección de sesgo de Duan y alpha con validación temporal.

    Todos en un mismo walk-forward (mismas semanas y reentrenamientos), con la semana base completa.
    """
    d = fe.preparar(dp.tabla_e12())
    m = configuraciones_e15()
    requeridas = sorted({v for x in m for v in x.variables} | {"y"})
    r = bt.backtest(d, m, inicio=INICIO, cada=4, progreso=True, requeridas=requeridas)
    bt.guardar(r, "E15")
    w = bt.ancho(r)
    for c in [x.nombre for x in m]:
        w[f"cota_{c}"] = cal.conformal(w.real, w[c], ventana=config.VENTANA_CONFORMAL)
    w.to_parquet(bt.RESULTADOS / "E15_ancho.parquet")
    return w


def resumen_e15(w):
    """Error, sesgo y cota por modelo; diferencias contra el oficial y de 3 contra 2 días."""
    w = w[w.index >= INICIO_EVALUACION].dropna(subset=["real"])
    puntuales = [c for c in w.columns if c not in ("real", "base") and not c.startswith("cota_")]
    periodos = bt.periodo(w.index + pd.Timedelta(weeks=1))
    alta = ev.alta_variabilidad_ex_post(w)
    filas = []
    for m in puntuales:
        e, cubre = w[m] - w.real, w.real <= w[f"cota_{m}"]
        fila = {"modelo": m, "MAE": e.abs().mean(), "sesgo": e.mean(),
                "sesgo_%": (e / w.real).mean() * 100, "quedarse_corto_%": (e < 0).mean() * 100,
                **{f"MAE_{p}": e[periodos == p].abs().mean() for p in ("desarrollo", "seleccion", "final")},
                "cobertura": cubre.mean(), "cobertura_saltos": cubre[alta].mean(),
                "exceso_cota_%": ((w[f"cota_{m}"] - w.real) / w.real)[cubre].mean() * 100}
        for ref in ("Ridge14", "Ridge14+cmg2d"):
            if m not in ("Ingenuo", ref):
                lo, hi = ev.ic_diferencia_mae(w, m, ref)
                fila.update({f"dif_vs_{ref}": e.abs().mean() - (w[ref] - w.real).abs().mean(),
                             f"IC95_inf_vs_{ref}": lo, f"IC95_sup_vs_{ref}": hi,
                             f"p_DM_vs_{ref}": ev.diebold_mariano(w, m, ref)[1]})
        filas.append(fila)
    t = pd.DataFrame(filas).set_index("modelo")
    t.to_csv(bt.RESULTADOS / "E15_resumen.csv")
    return t


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.float_format", "{:,.3f}".format)
    comando, opciones = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("e1", [])
    import trazabilidad
    trazabilidad.registrar_corrida(comando, opciones)
    if comando == "e1":
        d, w = correr_baseline()
        for nombre, t in resumen(d, w).items():
            print(f"\n== {nombre}\n{t}")
    elif comando == "e2":
        print(resumen_comparativo(correr_e2()[1], "E2").to_string())
    elif comando == "e3e4":
        print(resumen_comparativo(correr_e3e4()[1], "E3E4").to_string())
    elif comando == "e5e6":
        print(resumen_comparativo(correr_e5e6().dropna(), "E5E6", referencia="Ridge14").to_string())
    elif comando == "e7":
        _, c, reg = correr_e7()
        print(resumen_e7(c, reg).to_string())
        cotas_con_alerta()
    elif comando == "e8":
        tx1 = "tx1" in opciones
        print(resumen_comparativo(correr_e8(tx1)[1], "E8_tx1" if tx1 else "E8").to_string())
    elif comando == "e9":
        nombre, w = correr_e9(4 if "viernes" in opciones else 6)
        print(resumen_comparativo(w, nombre).to_string())
    elif comando == "e11":
        nombre, w = correr_e11(4 if "viernes" in opciones else 6)
        print(resumen_comparativo(w, nombre, referencia="Ridge14").to_string())
    elif comando == "e12":
        t, cotas, rc = resumen_e12(correr_e12())
        print(t.to_string())
        print(cotas.to_string())
        print(rc)
    elif comando == "e13":
        t, rc = resumen_e13(correr_e13())
        print(t.to_string())
        print(rc)
    elif comando == "e14":
        t, cms, alerta = resumen_e14(correr_e14())
        print(t.T.to_string())
        print(cms.pivot_table(index=["tipo", "modelo", "real"], columns="pronosticado", values="semanas").to_string())
        print(alerta.to_string())
    elif comando == "e15":
        print(resumen_e15(correr_e15()).T.to_string())
    elif comando == "e10":
        correr_e10()
        print(pd.read_csv(bt.RESULTADOS / "E10_estres.csv").to_string(index=False))
    elif comando == "cortes":
        print(correr_cortes().to_string())
    elif comando == "tuning":
        print(correr_tuning())
    elif comando == "alertas":
        if "e8" in opciones:
            print(correr_alertas_e8().to_string())
        else:
            _, _, t, imp = correr_alertas()
            print(t.to_string())
            print(imp.head(10).to_string())
    else:
        sys.exit(f"Comando desconocido: {comando}. Opciones: e1 e2 e3e4 e5e6 e7 e8 [tx1] e9 [viernes] e10 e11 [viernes] e12 e13 e14 cortes tuning alertas [e8]")
