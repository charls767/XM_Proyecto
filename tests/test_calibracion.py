from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import calibration as cal  # noqa: E402


def _serie(n=400, semilla=0):
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("2014-01-06", periods=n, freq="W-MON")
    pred = pd.Series(np.exp(rng.normal(5, 0.3, n)), index=idx)
    real = pred * np.exp(rng.normal(0, 0.2, n))
    return real, pred


def test_aci_sin_adaptacion_es_conformal():
    real, pred = _serie()
    np.testing.assert_allclose(cal.conformal_adaptativo(real, pred, gamma=0.0), cal.conformal(real, pred))


def test_mondrian_con_un_regimen_es_conformal():
    real, pred = _serie()
    regimen = pd.Series(1.0, index=pred.index)
    np.testing.assert_allclose(cal.conformal_regimen(real, pred, regimen), cal.conformal(real, pred))


def test_cobertura_cercana_al_nivel():
    real, pred = _serie(n=3000, semilla=1)
    for cota in (cal.conformal(real, pred), cal.conformal_adaptativo(real, pred, gamma=0.02)):
        cubre = (real <= cota)[cota.notna()]
        assert abs(cubre.mean() - 0.9) < 0.02


def test_sin_fuga_de_informacion():
    """Cambiar el real de la última semana no altera ninguna cota."""
    real, pred = _serie()
    alterado = real.copy()
    alterado.iloc[-1] *= 10
    regimen = pd.Series(np.arange(len(pred)) % 2, index=pred.index, dtype=float)
    for f in (lambda r: cal.conformal(r, pred),
              lambda r: cal.conformal_adaptativo(r, pred, gamma=0.05),
              lambda r: cal.conformal_regimen(r, pred, regimen)):
        np.testing.assert_allclose(f(real), f(alterado))
