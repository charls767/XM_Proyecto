"""Auditoría metodológica del modelo. Uso: python src/auditoria.py

Regenera las cifras de docs/AUDITORIA.md en results/auditoria/ a partir de las
predicciones guardadas: significancia corregida por búsqueda, cobertura, subgrupos,
efecto del embargo y del ajuste de sesgo. Solo lee resultados, no cambia ningún modelo.
"""

import json
import os
import warnings

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import backtesting as bt  # noqa: E402
import calibration as cal  # noqa: E402
import config  # noqa: E402
import data_pipeline as dp  # noqa: E402
import evaluation as ev  # noqa: E402
import feature_engineering as fe  # noqa: E402
import models  # noqa: E402

SALIDA = bt.RESULTADOS / "auditoria"
ENSAMBLE = "Ens[Ridge14+LEAR_directo]"
# Experimentos con semana base completa y las mismas semanas de prueba.
EXPERIMENTOS = {"E2": "E2", "E3E4": "E3E4", "E5E6": "E5E6", "E8": "E8", "E9_corte6": "E9", "E10_parsimonia": "E10"}


def _periodos(index):
    return pd.Series(bt.periodo(index + pd.Timedelta(weeks=1)), index=index)


def familia_de_modelos():
    """Todos los modelos comparados en el proyecto, para corregir por búsqueda."""
    fam = {}
    for archivo, etiqueta in EXPERIMENTOS.items():
        w = bt.ancho(bt.cargar(archivo))
        for c in w.columns.difference(["real", "base", "Ingenuo", "Estacional"]):
            fam[f"{etiqueta}:{c}"] = w[c]
    for archivo, etiqueta in (("E5E6_ancho", "E5E6"), ("E11_corte6_ancho", "E11")):
        w = pd.read_parquet(bt.RESULTADOS / f"{archivo}.parquet")
        for c in w.columns.difference(["real", "base", "Ingenuo"]):
            fam[f"{etiqueta}:{c}"] = w[c]
    return pd.DataFrame(fam)


def significancia():
    w = pd.read_parquet(bt.RESULTADOS / "E11_corte6_ancho.parquet")
    w = w[w.index >= "2018-01-01"]
    per = _periodos(w.index)
    filas = []
    for nombre, mascara in (("desarrollo", per == "desarrollo"), ("seleccion", per == "seleccion"),
                            ("final", per == "final"), ("total", per.notna())):
        s = w[mascara]
        for modelo, ref in ((ENSAMBLE, "Ridge14"), ("Ridge14", "Ingenuo"), (ENSAMBLE, "Ingenuo")):
            dl = (s[modelo] - s.real).abs() - (s[ref] - s.real).abs()
            est, p = ev.dm_hac(dl)
            filas.append({"periodo": nombre, "modelo": modelo, "referencia": ref, "semanas": len(s),
                          "dif_MAE": dl.mean(), "DM_HAC": est, "p": p})
    t = pd.DataFrame(filas)

    fam = familia_de_modelos()
    sel = w.index[per == "seleccion"]
    real = w.real.reindex(sel)
    ref = (w.Ridge14.reindex(sel) - real).abs()
    alt = fam.reindex(sel).sub(real, axis=0).abs().dropna(axis=1).drop(columns=["E11:Ridge14", "E10:Ridge14"], errors="ignore")
    busqueda = {"todo el proyecto": ev.reality_check(ref, alt), "solo E11": ev.reality_check(ref, alt[[c for c in alt if c.startswith("E11:")]])}
    busqueda["modelos que ganan a Ridge 14 en selección"] = int((alt.mean() < ref.mean()).sum())
    p_ens = float(t.query("periodo == 'seleccion' and modelo == @ENSAMBLE and referencia == 'Ridge14'").p.iloc[0])
    busqueda["p del ensamble con Bonferroni, familia E11"] = min(1.0, p_ens * busqueda["solo E11"]["modelos"])
    busqueda["p del ensamble con Bonferroni, todo el proyecto"] = min(1.0, p_ens * busqueda["todo el proyecto"]["modelos"])
    return t, busqueda


def cobertura_y_subgrupos():
    e = pd.read_parquet(bt.RESULTADOS / "E10_parsimonia_ancho.parquet")
    e = e[e.index >= "2018-01-01"]
    per = _periodos(e.index)
    fallas = e.real > e.cota_Ridge14
    cob = pd.DataFrame({k: ev.pruebas_cobertura(fallas[m]) for k, m in
                        (("2018-2026", per.notna()), ("desarrollo", per == "desarrollo"), ("seleccion", per == "seleccion"), ("final", per == "final"))}).T

    d = fe.preparar(dp.tabla_semanal(corregida=True)).reindex(e.index)
    g = pd.DataFrame({"real": e.real, "pred": e.Ridge14, "ing": e.Ingenuo, "cota": e.cota_Ridge14})
    claves = {
        "ENOS": d.fase_enos.map({-1: "Niña", 0: "Neutral", 1: "Niño"}),
        "embalse": pd.cut(d.embalse_cierre, [0, .45, .6, .75, 1]).astype(str),
        "precio": pd.qcut(d.precio, 4, labels=["1 bajo", "2", "3", "4 alto"]),
        "direccion del precio": pd.Series(np.where(g.real > g.ing, "sube", "baja"), index=g.index),
    }
    sub = ev.subgrupos(g, claves)
    ae = (g.pred - g.real).abs().sort_values(ascending=False)
    sesgo_t, sesgo_p = ev.dm_hac(g.pred - g.real)
    extras = {"porcion del error en el 10 % peor de semanas": float(ae.head(len(ae) // 10).sum() / ae.sum()),
              "acierto de la direccion del cambio": float(((g.pred > g.ing) == (g.real > g.ing)).mean()),
              "sesgo COP/kWh": float((g.pred - g.real).mean()), "p del sesgo": float(sesgo_p)}
    return cob, sub, extras


def _walk_forward(d, columnas, embargo=0):
    r = bt.backtest(d, [models.Modelo("Ingenuo"), models.Modelo("M", columnas, models.ridge)], inicio=config.INICIO_BACKTEST,
                    embargo=embargo, requeridas=columnas + ["y"])
    return bt.ancho(r)


def efecto_embargo():
    """Cuánto inflaba los resultados del corte al viernes no dejar la semana de embargo."""
    d = fe.preparar(dp.tabla_e9(4))
    filas = {}
    for nombre, cols in (("Ridge 14", config.VARIABLES), ("Ridge 14 + programado", config.VARIABLES + fe.GRUPOS_E9["programado"])):
        for emb in (0, 1):
            w = _walk_forward(d, cols, emb)
            cota = cal.conformal(w.real, w.M, rezago=1 + emb)
            m = w.index >= "2018-01-01"
            e = w.real[m] - cota[m]
            filas[f"{nombre}, embargo {emb}"] = {"MAE": (w.M[m] - w.real[m]).abs().mean(), "cobertura": (w.real[m] <= cota[m]).mean(),
                                                 "pinball": np.maximum(.9 * e, -.1 * e).mean()}
    return pd.DataFrame(filas).T


def ajuste_de_sesgo():
    """Ridge minimiza el error en log y exp(ŷ) estima la mediana: el nivel queda corto.
    Mide el factor de Duan (smearing), calculado solo con errores ya observados."""
    w = _walk_forward(fe.preparar(dp.tabla_semanal(corregida=True)), config.VARIABLES)
    res = np.exp(np.log(w.real / w.M))
    factor = res.shift(1).rolling(104, min_periods=26).mean().fillna(1.0)
    aj = w.M * factor
    m = w.index >= "2018-01-01"
    return pd.DataFrame({"sin ajuste": {"MAE": (w.M[m] - w.real[m]).abs().mean(), "sesgo": (w.M[m] - w.real[m]).mean()},
                         "con ajuste de Duan": {"MAE": (aj[m] - w.real[m]).abs().mean(), "sesgo": (aj[m] - w.real[m]).mean()}}).T


def principal():
    warnings.filterwarnings("ignore")
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.float_format", "{:,.3f}".format)
    t, busqueda = significancia()
    cob, sub, extras = cobertura_y_subgrupos()
    tablas = {"significancia": t, "cobertura": cob, "subgrupos": sub, "embargo": efecto_embargo(), "sesgo": ajuste_de_sesgo()}
    for nombre, tabla in tablas.items():
        tabla.to_csv(SALIDA / f"{nombre}.csv")
        print(f"\n== {nombre}\n{tabla.to_string()}")
    resumen = {"busqueda": busqueda, "extras": extras}
    (SALIDA / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    principal()
