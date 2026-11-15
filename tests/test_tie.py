"""La tabla TIE sigue la regla: semanas de sábado a viernes y objetivo tres semanas después."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import data_pipeline as dp  # noqa: E402

ARCHIVO = dp.PROCESSED / "semanal_tie.parquet"


@pytest.mark.skipif(not ARCHIVO.exists(), reason="falta la tabla TIE (python src/experimentos.py e16)")
def test_tabla_tie_semanas_y_horizonte():
    t = dp.tabla_tie()
    assert (t.index.dayofweek == 5).all()  # sábado
    s = t.precio_sig.dropna()
    esperado = t.precio.reindex(s.index + pd.Timedelta(weeks=dp.HORIZONTE_TIE)).to_numpy()
    assert pd.Series(esperado).notna().all()
    assert (abs(s.to_numpy() - esperado) < 1e-9).all()
    # Los días parciales son posteriores a la semana base: nunca la semana objetivo.
    assert dp.DIAS_PARCIALES_TIE <= 7
