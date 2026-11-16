"""Monto reconstruido de la garantía, vigilancia de exportación y precio de bolsa TIE reconstruido."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import data_pipeline as dp  # noqa: E402
import garantia  # noqa: E402
import semanal_tie  # noqa: E402


def test_monto_y_faltante_exceso():
    # 74.25 GWh × 10 centUSD/kWh = 7.425 millones de USD
    assert garantia.monto_usd(10.0) == pytest.approx(7.425e6)
    # El CEE se resta igual a lo garantizado y a lo liquidado: no cambia faltante ni exceso.
    f, e = garantia.faltante_exceso(np.array([12.0, 8.0]), np.array([10.0, 10.0]))
    assert f[0] == pytest.approx(garantia.monto_usd(2.0)) and f[1] == 0
    assert e[1] == pytest.approx(garantia.monto_usd(2.0)) and e[0] == 0
    t = garantia.resumen(np.array([12.0, 8.0]), {"x": np.array([10.0, 10.0])})
    assert t.at["x", "semanas_cortas"] == 1 and t.at["x", "cobertura"] == 0.5


def test_motivos_desempeno():
    assert semanal_tie.motivos_desempeno({"semanas": 5}, "X", "u") == []
    malo = {"semanas": 52, "razon_mae": 1.2, "cobertura": 0.7, "sesgo": -1.0, "sesgo_pct": -1.0, "p_sesgo": 0.5}
    m = semanal_tie.motivos_desempeno(malo, "Precio de exportación", "centUSD/kWh")
    assert len(m) == 2 and all(x.startswith("Precio de exportación:") for x in m)


@pytest.mark.skipif(not (dp.PROCESSED / "semanal_expo.parquet").exists(), reason="falta la tabla de exportación")
def test_precio_bolsa_tie_reconstruido_no_vacio():
    t = dp.tabla_expo()
    assert t.precio_bolsa_tie.notna().sum() > 0
    b = pd.Timestamp("2025-01-18")
    assert t.at[b, "precio_bolsa_tie"] / t.at[b, "trm"] * 100 == pytest.approx(16.55, abs=0.01)
