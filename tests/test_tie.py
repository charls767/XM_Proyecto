"""La tabla TIE sigue la regla: semanas de sábado a viernes y objetivo tres semanas después."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import data_pipeline as dp  # noqa: E402

ARCHIVO = dp.PROCESSED / "semanal_tie.parquet"


def test_semana_de_exportacion_incompleta_no_tiene_precio():
    """Auditoría de exportación, A2: los días después de la última fecha publicada no cuentan como cero."""
    dias = pd.date_range("2026-11-07", periods=6, freq="D")
    h = pd.date_range(dias[0], periods=24 * 6, freq="h")
    e = pd.Series(1000.0, index=h)
    u = pd.Series(500.0, index=h)
    c = pd.Series(2e6, index=h)
    sem = pd.DatetimeIndex(["2026-11-07"])
    incompleta = dp._semanal_expo(sem, 7, e, u, c, corte=pd.Timestamp("2026-11-12"))
    assert incompleta.usd.isna().all() and incompleta.energia.isna().all()
    completa = dp._semanal_expo(sem, 7, e, u, c, corte=pd.Timestamp("2026-11-13"))
    assert completa.usd.iloc[0] == pytest.approx(50.0)  # el día 13 sin fila cuenta como sin exportación


@pytest.mark.skipif(not ARCHIVO.exists(), reason="falta la tabla TIE (python src/experimentos.py e16)")
def test_costo_marginal_de_miercoles_a_viernes_de_la_semana_en_curso():
    """E24: para la semana base del 1-feb-2025, el viernes de cálculo es el 14-feb y se usan el miércoles 12,
    jueves 13 y viernes 14, que XM publica la víspera: nunca días de la semana objetivo."""
    import numpy as np
    import xm_client as xm
    t = dp.tabla_tie()
    cm = xm.a_horario(xm.leer_cache("costo_marginal"))
    dias = pd.date_range("2025-02-12", "2025-02-14")
    esperado = cm[cm.index.normalize().isin(dias)].groupby(cm.index.normalize()[cm.index.normalize().isin(dias)]).mean().mean()
    assert t.at[pd.Timestamp("2025-02-01"), "cmg_s"] == pytest.approx(esperado)
    assert t.at[pd.Timestamp("2025-02-01"), "cmg_s_rel"] == pytest.approx(np.log(esperado / t.at[pd.Timestamp("2025-02-01"), "precio"]))


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
