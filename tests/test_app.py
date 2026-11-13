"""La app de Streamlit abre sin errores con los resultados de results/app/."""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
DATOS = APP.parents[1] / "results" / "app" / "predicciones.parquet"

st_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.skipif(not DATOS.exists(), reason="falta results/app (python src/resultados_app.py)")
def test_app_abre_sin_errores():
    at = st_testing.AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value.startswith("Pronóstico semanal")
