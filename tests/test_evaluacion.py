"""Las pruebas estadísticas deben comportarse bien con casos conocidos."""

import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

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


def test_mes_vacio_sin_columnas_no_falla(tmp_path, monkeypatch):
    """La API sin datos produce un archivo sin columnas, no uno con `fecha` vacía."""
    monkeypatch.setattr(xm, "CACHE", tmp_path)
    (tmp_path / "x").mkdir()
    pd.DataFrame().to_parquet(tmp_path / "x" / "2015-03.parquet", index=False)
    assert not xm._en_cache("x", pd.Timestamp("2015-03-01"))
    assert pd.isna(xm.ultima_fecha_en_cache("x"))
    pd.DataFrame({"fecha": [pd.Timestamp("2015-02-10")]}).to_parquet(tmp_path / "x" / "2015-02.parquet", index=False)
    assert xm.ultima_fecha_en_cache("x") == pd.Timestamp("2015-02-10")


@pytest.mark.parametrize("respuesta", [
    pd.DataFrame(),
    pd.DataFrame({"fecha": [pd.Timestamp("2026-10-01")], "codigo": ["S"], "valor": [9.0]}),
])
def test_respuesta_incompleta_no_borra_la_cache(tmp_path, monkeypatch, respuesta):
    monkeypatch.setattr(xm, "CACHE", tmp_path)
    monkeypatch.setitem(xm.SERIES, "x", ("M", "Sistema", "daily"))
    mes = pd.Timestamp("2026-10-01")
    guardado = pd.DataFrame({"fecha": pd.date_range(mes, periods=2), "codigo": "S", "valor": [1.0, 2.0]})
    (tmp_path / "x").mkdir()
    guardado.to_parquet(xm._archivo("x", mes), index=False)
    xm._guardar("x", mes, respuesta)
    pd.testing.assert_frame_equal(pd.read_parquet(xm._archivo("x", mes)), guardado)


def test_respuesta_completa_actualiza_la_cache(tmp_path, monkeypatch):
    """Una revisión de XM con los mismos días o más sí reemplaza lo guardado."""
    monkeypatch.setattr(xm, "CACHE", tmp_path)
    monkeypatch.setitem(xm.SERIES, "x", ("M", "Sistema", "daily"))
    mes = pd.Timestamp("2026-10-01")
    (tmp_path / "x").mkdir()
    pd.DataFrame({"fecha": [mes], "codigo": ["S"], "valor": [1.0]}).to_parquet(xm._archivo("x", mes), index=False)
    revision = pd.DataFrame({"fecha": [mes], "codigo": ["S"], "valor": [5.0]})
    xm._guardar("x", mes, revision)
    assert pd.read_parquet(xm._archivo("x", mes)).valor.iloc[0] == 5.0


def test_listado_vencido_sobrevive_a_una_caida(tmp_path, monkeypatch):
    monkeypatch.setattr(xm, "CACHE", tmp_path)
    archivo = tmp_path / "listado_recursos.parquet"
    pd.DataFrame({"Code": ["A"], "Type": ["TERMICA"]}).to_parquet(archivo)
    viejo = pd.Timestamp.now().timestamp() - 40 * 86400
    os.utime(archivo, (viejo, viejo))

    def caida(*a, **k):
        raise OSError("API caída")

    monkeypatch.setattr(xm, "_post", caida)
    assert xm.listado_recursos().Code.tolist() == ["A"]
    archivo.unlink()
    with pytest.raises(OSError):
        xm.listado_recursos()
