"""Las pruebas estadísticas deben comportarse bien con casos conocidos."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import backtesting as bt  # noqa: E402
import evaluation as ev  # noqa: E402
import models  # noqa: E402
import xm_client as xm  # noqa: E402


def test_cobertura_detecta_fallas_agrupadas():
    rng = np.random.default_rng(0)
    independientes = rng.random(2000) < 0.1
    assert ev.pruebas_cobertura(independientes)["p_independencia"] > 0.01
    agrupadas = np.repeat(rng.random(200) < 0.1, 10)
    r = ev.pruebas_cobertura(agrupadas)
    assert r["p_independencia"] < 0.001 and r["p_falla_tras_falla"] > r["p_falla_tras_acierto"]


def _perdidas(n=157, k=20, semilla=1):
    rng = np.random.default_rng(semilla)
    idx = pd.RangeIndex(n)
    return pd.Series(rng.exponential(1, n), index=idx), pd.DataFrame(rng.exponential(1, (n, k)), index=idx, columns=[f"m{i}" for i in range(k)])


def test_reality_check_controla_falsos_positivos():
    """Con modelos que solo difieren por azar, no debe rechazar mucho más que el 5 % nominal."""
    p = [ev.reality_check(*_perdidas(semilla=s), n=200, semilla=s)["p"] for s in range(40)]
    assert np.mean(np.array(p) < 0.05) <= 0.15


def test_reality_check_detecta_mejora_real():
    ref, alt = _perdidas()
    alt["bueno"] = ref * 0.5
    r = ev.reality_check(ref, alt, n=500)
    assert r["mejor"] == "bueno" and r["p"] < 0.05


def test_embargo_excluye_la_ultima_semana():
    idx = pd.date_range("2013-01-07", periods=80, freq="W-MON")
    d = pd.DataFrame({"precio": 100.0, "precio_sig": 100.0, "y": 0.0, "x": np.arange(80.0)}, index=idx)
    r0 = bt.backtest(d, [models.Modelo("R", ["x"], models.ridge)], inicio=idx[60], cada=4)
    r1 = bt.backtest(d, [models.Modelo("R", ["x"], models.ridge)], inicio=idx[60], cada=4, embargo=1)
    assert r0.n_entrenamiento.iloc[0] == 60 and r1.n_entrenamiento.iloc[0] == 59


def test_mes_vacio_no_cuenta_como_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(xm, "CACHE", tmp_path)
    mes = pd.Timestamp("2015-03-01")
    (tmp_path / "x").mkdir()
    pd.DataFrame({"fecha": pd.to_datetime([])}).to_parquet(tmp_path / "x" / "2015-03.parquet")
    assert not xm._en_cache("x", mes)
    pd.DataFrame({"fecha": [mes], "valor": [1.0]}).to_parquet(tmp_path / "x" / "2015-03.parquet")
    assert xm._en_cache("x", mes)
