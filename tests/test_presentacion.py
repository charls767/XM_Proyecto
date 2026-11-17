"""La app y el informe PDF muestran el mismo estado metodológico de los tres objetivos, sin frases prohibidas.

Además fija las cifras del backtest 2018–2026 de E16/E24, E19 y E26: corregir la presentación no debe
cambiar modelos ni resultados.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import presentacion as pr  # noqa: E402

APP = RAIZ / "app" / "streamlit_app.py"
DATOS = RAIZ / "results" / "app"
REGLA = "Regla XM (repetir s-1)"
hay_datos = pytest.mark.skipif(not (DATOS / "predicciones_compra.parquet").exists(),
                               reason="falta results/app (python src/resultados_app.py)")

# (archivo, columna del modelo, semanas, error regla, error modelo), desde 2018.
CIFRAS = {
    "principal": ("predicciones_compra", "Modelo compras TIE (nacional × diferencial)", 113, 159.595, 142.217),
    "referencia": ("predicciones_tie",
                   "Modelo registrado (sábado a martes + costo marginal mié-vie, con corrección de sesgo)",
                   461, 115.288, 93.731),
    "complementario": ("predicciones_expo", "Modelo elegido (Huber + regla)", 117, 5.307, 4.828),
}


def prohibidas(texto):
    t = texto.lower()
    return [f for f in pr.FRASES_PROHIBIDAS if f in t]


@hay_datos
@pytest.mark.parametrize("clave", list(CIFRAS))
def test_cifras_no_cambian(clave):
    archivo, modelo, n, er, en = CIFRAS[clave]
    p = pd.read_parquet(DATOS / f"{archivo}.parquet")
    p = p[p.semana_objetivo >= "2018-01-01"].dropna(subset=["real", REGLA, modelo])
    assert len(p) == n
    assert (p[REGLA] - p.real).abs().mean() == pytest.approx(er, abs=1e-3)
    assert (p[modelo] - p.real).abs().mean() == pytest.approx(en, abs=1e-3)


def test_estados_metodologicos():
    assert pr.OBJETIVO["principal"]["estado"] == "Indicio favorable; evidencia débil"
    assert pr.OBJETIVO["complementario"]["estado"] == "No concluyente; evidencia débil"
    assert pr.OBJETIVO["referencia"]["estado"] == "Evidencia estadística favorable frente a la regla base"
    assert "Ningún modelo está validado para fijar garantías" in pr.NO_VALIDADO
    for texto in (pr.NO_VALIDADO, pr.REGLA_ATRIBUIDA, pr.NOTA_E22, pr.FUENTES, *pr.AVISOS_DISPONIBILIDAD):
        assert not prohibidas(texto), texto


def test_legible_traduce_variables():
    assert "cmg_s_rel" not in pr.legible("Faltan: cmg_s_rel")
    assert pr.sin_frases("no es el precio de la garantía") == "no es una cifra oficial del depósito"


@hay_datos
def test_pdf_tres_objetivos(tmp_path):
    pytest.importorskip("matplotlib")
    import informe_pdf
    informe_pdf.generar(destino=tmp_path / "informe.pdf", copiar=False)
    assert (tmp_path / "informe.pdf").stat().st_size > 0
    texto = " ".join(informe_pdf.TEXTO_GENERADO)
    plano = " ".join(texto.split())
    for clave in pr.ORDEN:
        o = pr.OBJETIVO[clave]
        assert o["nombre"] in plano, o["nombre"]
        assert o["estado"] in plano, o["estado"]
    for exp in ("E26", "E19", "E24"):
        assert exp in plano
    for serie in ("CompBolsaTIEMoneda", "CompBolsaTIEEner", "PrecBolsNaci", "ExportMonedaUSD", "ExpoEner", "CEE"):
        assert serie in plano, serie
    assert "cmg_s_rel" not in plano
    assert "pregunta abierta no resuelta con la información pública disponible" in plano
    assert not prohibidas(plano), prohibidas(plano)


st_testing = pytest.importorskip("streamlit.testing.v1")
PAGINAS = ["", "compras", "bolsa", "exportacion", "pronostico", "informe", "como", "semana"]


def textos_app(pagina, monkeypatch):
    monkeypatch.setenv("APP_PAGINA", pagina)
    at = st_testing.AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception, at.exception
    partes = []
    for grupo in (at.title, at.header, at.subheader, at.markdown, at.caption, at.warning, at.info, at.error):
        partes += [str(e.value) for e in grupo]
    partes += [f"{m.label} {m.value}" for m in at.metric]
    partes += [str(e.label) for e in at.expander]
    return " ".join(partes)


@hay_datos
@pytest.mark.parametrize("pagina", PAGINAS)
def test_app_sin_frases_prohibidas(pagina, monkeypatch):
    texto = textos_app(pagina, monkeypatch)
    assert not prohibidas(texto), prohibidas(texto)
    assert "cmg_s_rel" not in texto


@hay_datos
def test_inicio_estado_de_la_evidencia(monkeypatch):
    texto = textos_app("", monkeypatch)
    assert "Sí, es real" not in texto
    assert "Casi seguro" not in texto
    for clave in pr.ORDEN:
        assert pr.OBJETIVO[clave]["estado"] in texto
    assert "en los dos precios" not in texto
    for aviso in pr.AVISOS_DISPONIBILIDAD:
        assert aviso in texto
    assert "Ningún modelo está validado para fijar garantías" in texto


@hay_datos
def test_exportacion_no_concluyente(monkeypatch):
    texto = textos_app("exportacion", monkeypatch)
    assert "Casi seguro" not in texto
    assert "no concluyente; evidencia débil" in texto.lower()
