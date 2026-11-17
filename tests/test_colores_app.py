"""La app usa la paleta anterior a ISA-101 sin perder avisos ni cifras.

Revisa en los gráficos que de verdad dibuja la app (AppTest) que el fondo es claro, lo observado va en
negro, la regla en gris discontinuo, nuestro modelo en naranja y el modelo en prueba en verde punteado.
También fija las etiquetas metodológicas, los avisos y las cifras de E20 y E22 (E16/E24, E19 y E26 están
en test_presentacion.py y test_reproducibilidad_e19.py).
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import colores as col  # noqa: E402
import presentacion as pr  # noqa: E402

APP = RAIZ / "app" / "streamlit_app.py"
DATOS = RAIZ / "results" / "app" / "predicciones_tie.parquet"
st_testing = pytest.importorskip("streamlit.testing.v1")
hay_datos = pytest.mark.skipif(not DATOS.exists(), reason="falta results/app (python src/resultados_app.py)")


def luminancia(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def abrir(pagina, monkeypatch):
    monkeypatch.setenv("APP_PAGINA", pagina)
    at = st_testing.AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception, at.exception
    return at


def graficos(at):
    return [json.loads(e.proto.spec) for e in at.get("plotly_chart")]


def textos(at):
    partes = []
    for grupo in (at.title, at.subheader, at.markdown, at.caption, at.warning, at.info):
        partes += [str(e.value) for e in grupo]
    partes += [f"{m.label} {m.value}" for m in at.metric]
    return " ".join(partes)


def test_paleta_restaurada():
    assert (col.FONDO, col.FONDO_PANEL, col.TEXTO) == ("#fcfcfb", "#f0efec", "#0b0b0b")
    assert (col.REAL, col.REGLA, col.MODELO, col.PRUEBA, col.ALTERNATIVO) == (
        "#0b0b0b", "#898781", "#eb6834", "#1baf7a", "#2a78d6")
    assert (col.SUBE, col.BAJA, col.REJILLA, col.EJE) == ("#e34948", "#2a78d6", "#e1e0d9", "#c3c2b7")
    assert luminancia(col.FONDO) > 0.95 and luminancia(col.FONDO_PANEL) > 0.9  # no es gris oscuro
    assert luminancia(col.TEXTO) < 0.05
    for nombre in ("FONDO", "FONDO_PANEL", "REJILLA", "EJE", "TEXTO", "TEXTO_2", "TEXTO_TENUE", "REAL", "REGLA",
                   "MODELO", "PRUEBA", "TECHO", "SUBE", "BAJA", "ALARMA_ALTA", "ALARMA_MEDIA", "ALARMA_BAJA",
                   "TRAZO", "FUENTE", "ESTADO_COLOR", "ESTADO_TEXTO", "ESCALA_GRISES", "color_serie"):
        assert hasattr(col, nombre), nombre


def test_tema_streamlit_claro():
    tema = (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    for linea in ('base = "light"', 'primaryColor = "#2a78d6"', 'backgroundColor = "#fcfcfb"',
                  'secondaryBackgroundColor = "#f0efec"', 'textColor = "#0b0b0b"'):
        assert linea in tema


@hay_datos
def test_colores_de_las_series_en_bolsa(monkeypatch):
    figs = graficos(abrir("bolsa", monkeypatch))
    principal = figs[0]
    assert principal["layout"]["paper_bgcolor"] == col.FONDO == principal["layout"]["plot_bgcolor"]
    series = {d["name"]: d["line"] for d in principal["data"]}
    assert series["Valor observado"]["color"] == col.REAL and series["Valor observado"]["width"] >= 2.5
    assert series["Regla de referencia"] == {**series["Regla de referencia"], "color": col.REGLA, "dash": "dash"}
    assert series["Modelo registrado"]["color"] == col.MODELO and series["Modelo registrado"]["dash"] == "solid"
    assert series["Modelo en prueba"]["color"] == col.PRUEBA and series["Modelo en prueba"]["dash"] == "dot"
    calor = next(f for f in figs if f["data"][0]["type"] == "heatmap")
    assert calor["data"][0]["colorscale"][-1][1] == "#184f95"  # escala azul, no gris


@hay_datos
def test_techo_y_alerta_en_exportacion(monkeypatch):
    at = abrir("exportacion", monkeypatch)
    series = {d["name"]: d for d in graficos(at)[0]["data"]}
    techo = next(v for k, v in series.items() if k.startswith("Cota estadística calibrada"))
    assert techo["line"]["color"] == col.TECHO and techo["line"]["dash"] == "dot"
    alerta = next((v for k, v in series.items() if k.startswith("Semanas que superaron la cota")), None)
    if alerta is not None:  # triángulo rojo: la alerta no depende solo del color
        assert alerta["marker"]["color"] == col.ALARMA_ALTA and alerta["marker"]["symbol"] == "triangle-up"
    texto = textos(at).lower()
    assert "cota estadística calibrada" in texto and "no es una fórmula oficial de xm" in texto


@hay_datos
def test_inicio_conserva_etiquetas_y_avisos(monkeypatch):
    texto = textos(abrir("", monkeypatch))
    bajo = texto.lower()
    for etiqueta in ("Objetivo principal", "Objetivo de referencia", "Objetivo complementario", "Evidencia débil",
                     "Resultado no concluyente", "no es una fórmula oficial de XM"):
        assert etiqueta.lower() in bajo, etiqueta
    for aviso in (*pr.AVISOS_DISPONIBILIDAD, pr.NOTA_E22, pr.NO_VALIDADO):
        assert aviso in texto, aviso[:60]
    assert "Registro prospectivo aún no consolidado" in texto
    assert not [f for f in pr.FRASES_PROHIBIDAS if f in bajo]


@hay_datos
def test_pronostico_barras_y_avisos(monkeypatch):
    at = abrir("pronostico", monkeypatch)
    barras = graficos(at)[0]["data"][0]
    assert set(barras["marker"]["color"]) <= {col.SUBE, col.BAJA}
    texto = textos(at)
    assert "Registro prospectivo aún no consolidado" in texto
    for aviso in pr.AVISOS_DISPONIBILIDAD:
        assert aviso in texto


def test_cifras_e20_y_e22_no_cambian():
    e20 = pd.read_csv(RAIZ / "results" / "E20_cotas_regimen.csv", index_col=0)
    assert e20.cobertura.tolist() == pytest.approx([0.888889, 0.905983], abs=1e-6)
    assert e20.semanas_regimen.tolist() == [38, 38]
    e22 = pd.read_csv(RAIZ / "results" / "E22_monto.csv", index_col=0)
    assert e22.faltante_musd.iloc[:2].tolist() == pytest.approx([260.0712, 256.3921], abs=1e-4)
    assert e22.exceso_musd.iloc[:2].tolist() == pytest.approx([200.9393, 163.0156], abs=1e-4)
    assert e22.cobertura.iloc[3] == pytest.approx(0.905983, abs=1e-6)
