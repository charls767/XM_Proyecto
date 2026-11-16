"""E19 se reproduce desde cero con el código actual: mismas predicciones, cotas, resumen, fechas y semanas.

Reconstruye las tablas semanales desde la caché cruda (`data/raw/xm/`) en una carpeta temporal y corre el
backtest completo de E19; compara con los resultados guardados en results/. Así un cambio en otro
experimento (como E24 con `VARIABLES_TIE`) no puede alterar E19 sin que se note.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import backtesting as bt  # noqa: E402
import config  # noqa: E402
import data_pipeline as dp  # noqa: E402
import experimentos as ex  # noqa: E402

GUARDADO = RAIZ / "results"
pytestmark = pytest.mark.skipif(not (GUARDADO / "E19_ancho.parquet").exists(), reason="faltan los resultados de E19")


def test_e19_usa_las_variables_de_la_emision():
    huber = next(m for m in ex.configuraciones_e19() if m.nombre == "Huber expo")
    assert list(huber.variables) == list(config.VARIABLES_EXPO)
    assert "cmg_s_rel" not in huber.variables


def test_e19_se_reproduce_desde_cero(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "PROCESSED", tmp_path / "processed")
    (tmp_path / "processed").mkdir()
    monkeypatch.setattr(bt, "RESULTADOS", tmp_path / "results")
    w = ex.correr_e19()

    guardado = pd.read_parquet(GUARDADO / "E19_ancho.parquet")
    assert w.index.equals(guardado.index)  # mismas semanas base y fechas
    assert list(w.columns) == list(guardado.columns)
    pd.testing.assert_frame_equal(w, guardado, check_exact=False, rtol=1e-9, atol=1e-12)

    largo = pd.read_parquet(tmp_path / "results" / "E19.parquet")
    pd.testing.assert_frame_equal(largo, pd.read_parquet(GUARDADO / "E19.parquet"), check_exact=False, rtol=1e-9,
                                  atol=1e-12)

    t = ex.resumen_e19(w)
    g = pd.read_csv(GUARDADO / "E19_resumen.csv", index_col=0)
    pd.testing.assert_frame_equal(t[g.columns].astype(float), g.astype(float), check_exact=False, rtol=1e-9,
                                  check_names=False)
    elegido = t.loc["Mitad Huber + mitad regla"]
    assert int(elegido.semanas) == 117
    assert elegido.MAE == pytest.approx(4.8279, abs=1e-4)
    assert t.loc["Regla XM", "MAE"] == pytest.approx(5.3067, abs=1e-4)
