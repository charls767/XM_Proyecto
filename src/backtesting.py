"""Motor de backtesting walk-forward que reproduce la emisión semanal real.

Al cierre de la semana base s (domingo) se emite, el lunes siguiente, el
pronóstico de P_{s+1}. Una fila s entra al entrenamiento solo cuando P_{s+1} ya
se observó, es decir, cuando su semana objetivo terminó antes de la emisión.

Cada predicción se guarda en formato largo con su fecha de emisión, semana
objetivo, modelo, conjunto de variables, valor observado y error, para poder
comparar experimentos de forma emparejada.
"""

from pathlib import Path
import time

import numpy as np
import pandas as pd

RESULTADOS = Path(__file__).resolve().parents[1] / "results"

# Protocolo de validación temporal, por semana objetivo.
PERIODOS = [
    ("desarrollo", "2010-01-01", "2021-12-31"),
    ("seleccion", "2022-01-01", "2024-12-31"),
    ("final", "2025-01-01", "2100-01-01"),
]


def periodo(semanas_objetivo):
    s = pd.DatetimeIndex(semanas_objetivo)
    etiqueta = np.full(len(s), None, dtype=object)
    for nombre, ini, fin in PERIODOS:
        etiqueta[(s >= ini) & (s <= fin)] = nombre
    return etiqueta


def bloques_emision(semanas, inicio, cada):
    """Semanas base de prueba, agrupadas en bloques de reentrenamiento."""
    prueba = semanas[semanas >= pd.Timestamp(inicio)]
    return [prueba[i:i + cada] for i in range(0, len(prueba), cada)]


def backtest(d, modelos, inicio="2014-01-01", cada=4, requeridas=None, progreso=False, embargo=0):
    """Walk-forward con ventana expansiva, reentrenando cada `cada` semanas.

    `requeridas`: columnas que deben estar completas para que una semana sea de
    prueba. Por defecto, la unión de las variables de todos los modelos más `y`, de
    modo que todos se evalúan sobre las mismas semanas. Cada modelo entrena con las
    semanas anteriores en que sus propias variables están completas, así que añadir
    a la comparación un modelo con variables de rezago largo no recorta el
    entrenamiento de los demás.

    `embargo`: semanas adicionales excluidas antes de cada bloque. Con la semana base
    cortada antes del domingo hay que usar 1: la fila s0-1 tiene como objetivo la semana
    s0 completa, que aún no se conoce al emitir s0 (auditoría, hallazgo de fuga).
    """
    if requeridas is None:
        requeridas = sorted({v for m in modelos for v in m.variables} | {"y"})
    semanas_prueba = d.dropna(subset=requeridas).index
    completas = {m.nombre: d.dropna(subset=m.variables + ["y"]) for m in modelos}
    filas = []
    bloques = bloques_emision(semanas_prueba, inicio, cada)
    t0 = time.time()
    for i, bloque in enumerate(bloques, 1):
        if progreso and (i == 1 or i % 10 == 0 or i == len(bloques)):
            print(f"bloque {i}/{len(bloques)} ({bloque[0]:%Y-%m-%d}) {time.time() - t0:.0f} s", flush=True)
        prueba = d.loc[bloque]
        for m in modelos:
            entren = completas[m.nombre]
            entren = entren[entren.index < bloque[0] - pd.Timedelta(weeks=embargo)]
            filas.append(pd.DataFrame({
                "semana_base": bloque,
                "modelo": m.nombre,
                "prediccion": m.ajustar_predecir(entren, prueba),
                "observado": prueba.precio_sig.to_numpy(),
                "precio_base": prueba.precio.to_numpy(),
                "n_entrenamiento": len(entren),
                "variables": ",".join(m.variables),
            }))
    r = pd.concat(filas, ignore_index=True)
    r["fecha_emision"] = r.semana_base + pd.Timedelta(days=7)
    r["semana_objetivo"] = r.semana_base + pd.Timedelta(weeks=1)
    r["error"] = r.prediccion - r.observado
    r["periodo"] = periodo(r.semana_objetivo)
    return r


def ancho(r, valor="prediccion"):
    """Formato ancho por semana base: observado, precio base y una columna por modelo."""
    w = r.pivot(index="semana_base", columns="modelo", values=valor)
    base = r.drop_duplicates("semana_base").set_index("semana_base")
    w.insert(0, "real", base.observado)
    w.insert(1, "base", base.precio_base)
    w.columns.name = None
    return w


def guardar(r, experimento):
    RESULTADOS.mkdir(exist_ok=True)
    archivo = RESULTADOS / f"{experimento}.parquet"
    r.to_parquet(archivo, index=False)
    return archivo


def cargar(experimento):
    return pd.read_parquet(RESULTADOS / f"{experimento}.parquet")
