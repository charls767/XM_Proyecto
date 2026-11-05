"""Proceso semanal: explicación exacta, monitoreo y registro inmutable."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import config  # noqa: E402
import feature_engineering as fe  # noqa: E402
import models  # noqa: E402
import monitoreo  # noqa: E402
import semanal  # noqa: E402

SEMANAL = RAIZ / "data" / "processed" / "semanal_corregida.parquet"
pytestmark = pytest.mark.skipif(not SEMANAL.exists(), reason="falta la tabla semanal corregida")


@pytest.fixture(scope="module")
def d():
    return fe.preparar(pd.read_parquet(SEMANAL))


def test_explicacion_suma_el_pronostico(d):
    ent = d.dropna(subset=config.VARIABLES + ["y"])
    ent = ent[ent.index < "2022-01-01"]
    m = models.ridge().fit(ent[config.VARIABLES], ent.y)
    fila = d.loc["2023-06-05"]
    intercepto, aportes = semanal.contribuciones(m, fila)
    pred = m.predict(d.loc[["2023-06-05"], config.VARIABLES])[0]
    assert intercepto + aportes.sum() == pytest.approx(pred, abs=1e-10)


def test_dato_faltante_pasa_a_respaldo(d):
    semana = d.index[-2]
    roto = d.copy()
    roto.loc[semana, "embalse_cambio"] = np.nan
    controles = monitoreo.calidad(roto, semana, semana + pd.Timedelta(days=8))
    estado, motivos = monitoreo.estado(controles, monitoreo.fuera_de_rango(roto, semana), {"semanas": 0})
    assert estado == "respaldo"
    assert any("embalse_cambio" in m for m in motivos)


def test_detecta_extrapolacion(d):
    semana = d.index[-2]
    raro = d.copy()
    raro.loc[semana, "aportes_pct_media_4s"] = d.aportes_pct_media_4s.max() + 1
    rango = monitoreo.fuera_de_rango(raro, semana)
    assert "aportes_pct_media_4s" in set(rango.loc[rango.nivel == "extrapolacion", "variable"])
    estado, _ = monitoreo.estado(monitoreo.calidad(raro, semana, semana + pd.Timedelta(days=8)), rango, {"semanas": 0})
    assert estado == "vigilancia"


def test_desempeno_bajo_pide_vigilancia():
    idx = pd.date_range("2025-01-06", periods=30, freq="W-MON")
    h = pd.DataFrame({"real": 100.0, "ingenuo": 101.0, "prediccion": 120.0, "cota": 90.0}, index=idx)
    des = monitoreo.desempeno_reciente(h)
    assert des["razon_mae"] > 1 and des["cobertura"] == 0
    estado, motivos = monitoreo.estado(pd.DataFrame(columns=["control", "estado", "detalle"]), pd.DataFrame(columns=["nivel"]), des)
    assert estado == "vigilancia" and len(motivos) == 2


def _emision(semana, pronostico):
    return {"fecha_emision": semana + pd.Timedelta(days=8), "semana_base": semana,
            "semana_objetivo": semana + pd.Timedelta(weeks=1), "version_modelo": "prueba", "estado": "normal",
            "motivos": [], "datos_hasta": {"precio": semana + pd.Timedelta(days=6)}, "precio_base": 100.0,
            "pronostico": pronostico, "cambio_pct": pronostico - 100, "cota90": 150.0, "cota90_vol": 160.0,
            "ingenuo": 100.0, "alertas": {"salto": {"puntaje": 0.1}}, "variables": {},
            "controles": pd.DataFrame(columns=["control", "estado", "detalle"])}


def test_registro_no_sobrescribe_y_califica(tmp_path, monkeypatch, d):
    monkeypatch.setattr(semanal, "REGISTRO", tmp_path)
    monkeypatch.setattr(semanal, "ARCHIVO", tmp_path / "pronosticos.csv")
    semana = d.index[-3]
    assert semanal.registrar(_emision(semana, 90.0)) is True
    assert semanal.registrar(_emision(semana, 999.0)) is False
    reg = semanal._leer_registro()
    assert len(reg) == 1 and reg.pronostico.iloc[0] == 90.0
    reg = semanal.calificar(d)
    real = d.precio[semana + pd.Timedelta(weeks=1)]
    assert reg.real.iloc[0] == pytest.approx(real, abs=0.01)
    assert bool(reg.cubierto.iloc[0]) == (real <= 150.0)
