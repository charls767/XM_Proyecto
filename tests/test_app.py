"""Cada página de la app de Streamlit abre sin errores con los resultados de results/app/."""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
DATOS = APP.parents[1] / "results" / "app" / "predicciones_tie.parquet"
PAGINAS = {"": "¿Cuánto costará la energía", "exportacion": "Precio de exportación", "bolsa": "Precio de bolsa",
           "pronostico": "Pronóstico de esta semana", "semana": "Extra: el precio de la semana siguiente",
           "como": "Cómo funciona"}

st_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.skipif(not DATOS.exists(), reason="falta results/app (python src/resultados_app.py)")
@pytest.mark.parametrize("pagina", list(PAGINAS))
def test_pagina_abre_sin_errores(pagina, monkeypatch):
    monkeypatch.setenv("APP_PAGINA", pagina)
    at = st_testing.AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception, at.exception
    assert at.title[0].value.startswith(PAGINAS[pagina])
