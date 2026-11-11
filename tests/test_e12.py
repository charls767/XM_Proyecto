"""El costo marginal de E12 debe usar solo los primeros k días de la semana objetivo."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import data_pipeline as dp  # noqa: E402
import xm_client as xm  # noqa: E402

pytestmark = pytest.mark.skipif(not (xm.CACHE / "costo_marginal").exists(), reason="falta la caché de XM")


@pytest.fixture(scope="module")
def cmg():
    return xm.descargar("costo_marginal", "2024-01-01", "2024-03-31")


@pytest.mark.parametrize("k", dp.DIAS_CMG)
def test_solo_usa_los_primeros_k_dias_de_la_semana_objetivo(cmg, k):
    alterado = cmg.copy()
    alterado.loc[alterado.fecha.dt.weekday >= k, xm.HORAS] *= 5
    a, b = dp.costo_marginal(cmg), dp.costo_marginal(alterado)
    # La semana base completa sí cambia, así que se compara el numerador: el promedio de los k días.
    num_a = np.exp(a[f"cmg_{k}d_rel"]) * a.cmg_semana
    num_b = np.exp(b[f"cmg_{k}d_rel"]) * b.cmg_semana
    pd.testing.assert_series_equal(num_a, num_b, check_names=False)


def test_se_asigna_a_la_semana_base(cmg):
    v = dp.costo_marginal(cmg)
    h = xm.a_horario(cmg)
    lunes_sig = h["2024-01-15"].mean()  # lunes de la semana siguiente a la base del 8 de enero
    semana_base = h["2024-01-08":"2024-01-14"].mean()
    assert np.isclose(v.loc["2024-01-08", "cmg_1d_rel"], np.log(lunes_sig / semana_base))
