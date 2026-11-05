from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import alertas  # noqa: E402
import feature_engineering as fe  # noqa: E402

SEMANAL = RAIZ / "data" / "processed" / "semanal_corregida.parquet"
pytestmark = pytest.mark.skipif(not SEMANAL.exists(), reason="falta la tabla semanal corregida")


@pytest.fixture(scope="module")
def d():
    return fe.preparar(pd.read_parquet(SEMANAL))


def test_estado_y_variables_no_usan_el_futuro(d):
    """Cambiar todo lo posterior a una semana no altera su estado ni sus variables."""
    corte = d.index[600]
    alterada = d.copy()
    futuro = alterada.index > corte
    alterada.loc[futuro, ["precio", "embalse_cierre"]] *= 3
    alterada = fe.preparar(alterada.drop(columns=[c for c in alterada if c not in d.columns[:22]]))
    _, e1 = alertas.eventos(d)
    _, e2 = alertas.eventos(alterada)
    pd.testing.assert_frame_equal(e1.loc[:corte], e2.loc[:corte])
    x1 = alertas.variables_alerta(d, e1).loc[:corte]
    x2 = alertas.variables_alerta(alterada, e2).loc[:corte]
    pd.testing.assert_frame_equal(x1, x2)


def test_horizonte_de_etiquetas(d):
    etiqueta, _ = alertas.eventos(d)
    assert etiqueta.estres_hidrico.iloc[-4:].isna().all()
    assert etiqueta.salto.iloc[-1:].isna().all()
    np.testing.assert_array_equal(
        etiqueta.estres_hidrico.dropna(),
        (d.embalse_cierre.shift(-4) < alertas.UMBRAL_EMBALSE).astype(float)[etiqueta.estres_hidrico.notna()])
