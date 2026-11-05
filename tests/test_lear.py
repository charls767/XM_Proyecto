"""LEAR no debe usar nada posterior a lo conocido al emitir cada pronóstico."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import lear  # noqa: E402

DIARIA = RAIZ / "data" / "processed" / "diaria.parquet"
pytestmark = pytest.mark.skipif(not DIARIA.exists(), reason="falta la tabla diaria")


@pytest.fixture(scope="module")
def t():
    return pd.read_parquet(DIARIA)


def _prueba(semana):
    return pd.DataFrame(index=pd.DatetimeIndex([pd.Timestamp(semana)]))


@pytest.mark.parametrize("ultimo_dia", [6, 4])
@pytest.mark.parametrize("modo", ["bottomup", "directo"])
def test_futuro_no_cambia_el_pronostico(t, ultimo_dia, modo):
    semana = pd.Timestamp("2023-06-05")
    conocido = semana + pd.Timedelta(days=ultimo_dia)
    alterada = t.copy()
    columnas = [c for c in t.columns if c != "prog_t"]
    alterada.loc[alterada.index > conocido, columnas] *= 3
    # La generación programada del día siguiente sí se conoce al cierre del día.
    alterada.loc[alterada.index > conocido + pd.Timedelta(days=1), "prog_t"] *= 3
    a = lear.LEAR("a", t, ultimo_dia, modo).ajustar_predecir(None, _prueba(semana))
    b = lear.LEAR("b", alterada, ultimo_dia, modo).ajustar_predecir(None, _prueba(semana))
    np.testing.assert_allclose(a, b)


def test_corte_viernes_ignora_el_fin_de_semana(t):
    """Con corte el viernes, el sábado y el domingo de la semana base no cuentan."""
    semana = pd.Timestamp("2023-06-05")
    alterada = t.copy()
    finde = [semana + pd.Timedelta(days=5), semana + pd.Timedelta(days=6)]
    alterada.loc[finde, ["precio", "demanda", "precio_max", "precio_std"]] *= 3
    a = lear.LEAR("a", t, 4, "bottomup").ajustar_predecir(None, _prueba(semana))
    b = lear.LEAR("b", alterada, 4, "bottomup").ajustar_predecir(None, _prueba(semana))
    np.testing.assert_allclose(a, b)


def test_las_semanas_del_bloque_usan_el_mismo_modelo(t):
    """Un bloque se entrena con lo conocido en su primera semana, aunque pronostique las siguientes."""
    semanas = pd.date_range("2023-06-05", periods=4, freq="7D")
    alterada = t.copy()
    fin_primera = semanas[0] + pd.Timedelta(days=6)
    # Se altera el precio de la última semana del bloque solo después de su propio origen.
    alterada.loc[alterada.index > semanas[-1] + pd.Timedelta(days=6), "precio"] *= 3
    a = lear.LEAR("a", t, 6, "directo").ajustar_predecir(None, pd.DataFrame(index=semanas))
    b = lear.LEAR("b", alterada, 6, "directo").ajustar_predecir(None, pd.DataFrame(index=semanas))
    np.testing.assert_allclose(a, b)
    assert fin_primera < semanas[-1]
