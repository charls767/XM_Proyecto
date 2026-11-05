"""El corte de información (semana s conocida solo hasta el viernes) no debe usar el fin de semana."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import data_pipeline as dp  # noqa: E402
import xm_client as xm  # noqa: E402

pytestmark = pytest.mark.skipif(not (xm.CACHE / "precio").exists(), reason="falta la caché de XM")


@pytest.fixture(scope="module")
def precio_demanda():
    p = xm.descargar("precio", "2024-01-01", "2024-03-31")
    d = xm.descargar("demanda", "2024-01-01", "2024-03-31")
    return p, d


def test_rasgos_diarios_ignoran_fin_de_semana(precio_demanda):
    p, d = precio_demanda
    alterado = p.copy()
    finde = alterado.fecha.dt.weekday >= 5
    alterado.loc[finde, xm.HORAS] *= 5
    a = dp.rasgos_diarios(p, d, ultimo_dia=4)
    b = dp.rasgos_diarios(alterado, d, ultimo_dia=4)
    pd.testing.assert_frame_equal(a, b)
    # Con la semana completa, el fin de semana sí cuenta.
    assert not np.allclose(dp.rasgos_diarios(p, d, 6).ultimos2_rel, dp.rasgos_diarios(alterado, d, 6).ultimos2_rel)


def test_precio_parcial_usa_solo_lunes_a_viernes(precio_demanda):
    p, d = precio_demanda
    lv = lambda x: x[x.fecha.dt.weekday <= 4]
    parcial = dp.precio_ponderado(lv(p), lv(d), horas=120)
    alterado = p.copy()
    alterado.loc[alterado.fecha.dt.weekday >= 5, xm.HORAS] *= 5
    pd.testing.assert_frame_equal(parcial, dp.precio_ponderado(lv(alterado), lv(d), horas=120))
    assert len(parcial) >= 12


def test_corte_viernes_no_usa_la_demanda_del_fin_de_semana():
    """La demanda de sábado y domingo aún no se conoce al emitir el lunes."""
    corte = dp.tabla_semanal_corte(4)
    completa = dp.tabla_semanal(corregida=True).reindex(corte.index)
    assert "demanda_gwh" in dp.COLUMNAS_CON_REZAGO
    assert (corte.demanda_gwh < completa.demanda_gwh).all()
