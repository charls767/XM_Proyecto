"""Cada una de las ocho páginas de la app de Streamlit abre sin errores con los resultados de results/app/."""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
DATOS = APP.parents[1] / "results" / "app" / "predicciones_tie.parquet"
PAGINAS = {"": "Modelos para anticipar precios relacionados con las obligaciones TIE",
           "compras": "Compras TIE en bolsa — objetivo principal",
           "bolsa": "Precio nacional de bolsa — objetivo de referencia",
           "exportacion": "Precio realizado de exportación — objetivo complementario",
           "pronostico": "Emisión ilustrativa y registro prospectivo", "informe": "Informe PDF",
           "como": "Cómo se construyen y evalúan los modelos",
           "semana": "Experimento complementario: horizonte de una semana"}

st_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.skipif(not DATOS.exists(), reason="falta results/app (python src/resultados_app.py)")
@pytest.mark.parametrize("pagina", list(PAGINAS))
def test_pagina_abre_sin_errores(pagina, monkeypatch):
    monkeypatch.setenv("APP_PAGINA", pagina)
    at = st_testing.AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception, at.exception
    assert at.title[0].value.startswith(PAGINAS[pagina])
