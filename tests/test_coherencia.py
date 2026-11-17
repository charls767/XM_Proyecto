"""La app y el informe PDF usan los mismos términos, estados y cifras (src/presentacion.py es la fuente común).

Cifras del backtest 2018–2026 con su precisión (sin redondear a enteros): E26 159.6 y 142.2 COP/kWh; precio
nacional de bolsa 115.3 y 93.7 COP/kWh; exportación 5.31 y 4.83 centUSD/kWh. La cota se muestra con su nivel
nominal (90 %) separado de la cobertura observada y del exceso promedio.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import presentacion as pr  # noqa: E402

APP = RAIZ / "app" / "streamlit_app.py"
DATOS = RAIZ / "results" / "app" / "predicciones_compra.parquet"
st_testing = pytest.importorskip("streamlit.testing.v1")
pytestmark = pytest.mark.skipif(not DATOS.exists(), reason="falta results/app (python src/resultados_app.py)")
PAGINAS = ["", "compras", "bolsa", "exportacion", "pronostico", "informe", "como", "semana"]

CIFRAS = {"principal": ("159.6", "142.2", "COP/kWh"), "referencia": ("115.3", "93.7", "COP/kWh"),
          "complementario": ("5.31", "4.83", "centUSD/kWh")}
COBERTURA = {"principal": "87.6 %", "referencia": "89.2 %", "complementario": "90.6 %"}
EXCESO = {"principal": "107.2 %", "referencia": "76.8 %", "complementario": "105.1 %"}
AUSENTES = ("regla actual de xm", "techo de garantía", "ejemplo con los datos de hoy", "regla de xm", "techo")


def texto_app(pagina, monkeypatch):
    monkeypatch.setenv("APP_PAGINA", pagina)
    at = st_testing.AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, at.exception
    partes = []
    for grupo in (at.title, at.header, at.subheader, at.markdown, at.caption, at.warning, at.info):
        partes += [str(e.value) for e in grupo]
    partes += [f"{m.label} {m.value} {m.help or ''}" for m in at.metric]
    partes += [str(e.label) for e in at.expander]
    return " ".join(" ".join(partes).split())


@pytest.fixture(scope="module")
def texto_pdf(tmp_path_factory):
    pytest.importorskip("matplotlib")
    import informe_pdf
    informe_pdf.generar(destino=tmp_path_factory.mktemp("pdf") / "informe.pdf", copiar=False)
    return " ".join(" ".join(informe_pdf.TEXTO_GENERADO).split())


def test_cifras_con_precision_en_app_y_pdf(texto_pdf, monkeypatch):
    app = texto_app("", monkeypatch)
    for clave, (regla, modelo, unidad) in CIFRAS.items():
        assert f"{regla} {unidad}" in app and f"{modelo} {unidad}" in app, clave  # tarjetas de Inicio
        assert regla in texto_pdf and modelo in texto_pdf, clave  # tabla resumen del PDF
    for texto in (app, texto_pdf):
        assert "-10.9 %" in texto and "p = 0.044" in texto and "p < 0.001" in texto and "p = 0.081" in texto
        assert "COP/kWh" in texto and "centUSD/kWh" in texto
    # Ninguna tarjeta ni tabla resumen redondea a enteros los errores en COP/kWh.
    for entero in ("160 COP/kWh", "142 COP/kWh", "115 COP/kWh", "94 COP/kWh"):
        assert entero not in app


def test_estados_y_terminos_iguales(texto_pdf, monkeypatch):
    app = texto_app("", monkeypatch)
    for clave in pr.ORDEN:
        o = pr.OBJETIVO[clave]
        for termino in (o["estado"], o["nombre"], pr.ETIQUETA[clave]):
            assert termino in app and termino in texto_pdf, termino
    for termino in (pr.REGLA_NOMBRE, pr.COTA, pr.AVISO_REGISTRO):
        assert termino in texto_pdf, termino
    emision = texto_app("pronostico", monkeypatch)
    for termino in (pr.EJEMPLO, pr.RETROSPECTIVO, pr.AVISO_REGISTRO, pr.REGLA_NOMBRE, pr.COTA):
        assert termino in emision, termino
    assert pr.EJEMPLO in texto_pdf and pr.RETROSPECTIVO in texto_pdf


def test_cobertura_nominal_distinta_de_la_observada(texto_pdf, monkeypatch):
    app = texto_app("", monkeypatch)
    assert "<td>Cota: nivel nominal</td><td>90 % (conformal)</td>" in app
    # Mismos rótulos en la app (filas de la tarjeta) y en el PDF (encabezados de la tabla de estados).
    assert "Cota: nivel nominal" in texto_pdf and "Cobertura observada" in texto_pdf
    assert "Exceso promedio" in texto_pdf and "90 %" in texto_pdf
    for clave in pr.ORDEN:
        assert f"<td>Cota: cobertura observada</td><td>{COBERTURA[clave]}</td>" in app, clave
        assert f"<td>Cota: exceso promedio</td><td>{EXCESO[clave]}</td>" in app, clave
        assert COBERTURA[clave] in texto_pdf and EXCESO[clave] in texto_pdf, clave
    assert pr.COTA_DEFINICION in texto_pdf
    bolsa = texto_app("bolsa", monkeypatch)
    assert f"{pr.COTA_DEFINICION}: cobertura observada 89.2 %, exceso promedio 76.8 %" in bolsa


@pytest.mark.parametrize("pagina", PAGINAS)
def test_sin_etiquetas_antiguas_en_la_app(pagina, monkeypatch):
    bajo = texto_app(pagina, monkeypatch).lower()
    encontradas = [t for t in AUSENTES if t in bajo]
    assert not encontradas, encontradas


def test_sin_etiquetas_antiguas_en_el_pdf(texto_pdf):
    bajo = texto_pdf.lower()
    encontradas = [t for t in AUSENTES if t in bajo]
    assert not encontradas, encontradas
    assert not [f for f in pr.FRASES_PROHIBIDAS if f in bajo]
