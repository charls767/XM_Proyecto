"""El motor debe reproducir el modelo original (referencia/pae_original) antes de aceptar mejoras.

Requiere haber corrido `python src/experimentos.py` (results/E0_E1_ancho.parquet)
y que existan los archivos de `referencia/pae_original/datos`.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
PAE = RAIZ / "referencia" / "pae_original" / "datos"
sys.path.insert(0, str(RAIZ / "src"))

import evaluation as ev  # noqa: E402

pytestmark = pytest.mark.skipif(not (PAE / "predicciones_walk_forward.csv").exists(),
                                reason="faltan los resultados del baseline PAE")


@pytest.fixture(scope="module")
def nuevo():
    return pd.read_parquet(RAIZ / "results" / "E0_E1_ancho.parquet")


@pytest.fixture(scope="module")
def baseline():
    return pd.read_csv(PAE / "predicciones_walk_forward.csv", index_col=0, parse_dates=True)


def test_tabla_semanal_identica():
    nueva = pd.read_parquet(RAIZ / "data" / "processed" / "semanal.parquet")
    original = pd.read_csv(PAE / "semanal.csv", index_col=0, parse_dates=True)
    pd.testing.assert_frame_equal(nueva[original.columns], original, check_freq=False,
                                  check_names=False, rtol=1e-9)


@pytest.mark.parametrize("col", ["real", "Ridge", "GBoost", "GBoost_q90", "Ridge_cota90", "Ridge_cota90_vol"])
def test_predicciones_identicas(nuevo, baseline, col):
    b = baseline.rename(columns={"Ingenuo": "base"})
    comun = nuevo.index.intersection(b.index)
    assert len(comun) == len(b)
    np.testing.assert_allclose(nuevo.loc[comun, col], b.loc[comun, col], rtol=1e-8)


def test_metricas_reportadas(nuevo):
    w = nuevo[nuevo.index >= "2018-01-01"]
    p = ev.puntuales(w, ["Ingenuo", "Ridge", "GBoost"], escala=1.0)
    assert p.loc["Ridge", "MAE"] == pytest.approx(54.303, abs=1e-3)
    assert p.loc["GBoost", "MAE"] == pytest.approx(56.706, abs=1e-3)
    assert p.loc["Ingenuo", "MAE"] == pytest.approx(66.553, abs=1e-3)
    c = ev.cotas(w, ["Ridge_cota90"])
    assert c.loc["Ridge_cota90", "cobertura"] == pytest.approx(0.902, abs=1e-3)
    assert c.loc["Ridge_cota90", "pinball"] == pytest.approx(15.718, abs=1e-3)


@pytest.mark.parametrize("experimento", ["E2", "E3E4", "E8", "E8_tx1", "E9_corte6", "E9_corte4"])
def test_experimento_mismas_semanas_que_e1(nuevo, experimento):
    archivo = RAIZ / "results" / f"{experimento}.parquet"
    if not archivo.exists():
        pytest.skip(f"{experimento} no se ha corrido")
    r = pd.read_parquet(archivo)
    assert set(r.semana_base) == set(nuevo.index)
    assert r.groupby("modelo").size().nunique() == 1


def test_tabla_tx1_conserva_objetivo_vigente():
    e8, tx1 = RAIZ / "data" / "processed" / "semanal_e8.parquet", RAIZ / "data" / "processed" / "semanal_tx1.parquet"
    if not (e8.exists() and tx1.exists()):
        pytest.skip("faltan las tablas E8")
    a, b = pd.read_parquet(e8), pd.read_parquet(tx1)
    pd.testing.assert_series_equal(a.precio_sig, b.precio_sig)
    # La semana s usa TX1 donde existe; la diferencia con el vigente es pequeña pero no nula.
    dif = (b.precio / a.precio - 1)[b.precio_es_tx1].abs()
    assert 0 < dif.median() < 0.05
