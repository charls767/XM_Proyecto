"""El panel presenta los tres objetivos en orden, con unidades, fechas y estados explícitos, sin lenguaje engañoso.

Comprueba la estructura pedida para un lector que no conoce el proyecto: orientación y resultado principal en
Inicio, tarjetas con las cifras del backtest (que no cambian), regla de referencia descrita como material
público de formación de XM, emisión ilustrativa separada del registro prospectivo y calendario visible.
"""
import json
import re
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


def abrir(pagina, monkeypatch):
    monkeypatch.setenv("APP_PAGINA", pagina)
    at = st_testing.AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def textos(at):
    partes = []
    for grupo in (at.title, at.header, at.subheader, at.markdown, at.caption, at.warning, at.info):
        partes += [str(e.value) for e in grupo]
    partes += [f"{m.label} {m.value}" for m in at.metric]
    partes += [str(e.label) for e in at.expander]
    return " ".join(partes)


def test_inicio_orientacion_orden_y_cifras(monkeypatch):
    texto = textos(abrir("", monkeypatch))
    assert "¿Qué hace este panel?" in texto and "Resultado principal" in texto
    assert "No reproduce una fórmula oficial de garantía y ningún modelo está validado para fijar garantías" in texto
    # Orden obligatorio: principal (E26), referencia (E16/E24), complementario (E19/E20).
    posiciones = [texto.index(f"<h4>{pr.OBJETIVO[c]['nombre']}</h4>") for c in pr.ORDEN]
    assert posiciones == sorted(posiciones)
    for c in pr.ORDEN:
        o = pr.OBJETIVO[c]
        assert o["estado"] in texto and o["variable"] in texto and pr.NOTA_CORTA[c] in texto
    # Cifras del backtest 2018–2026 (no cambian): semanas, errores, diferencia y valor p, con su unidad.
    for cifra in ("<td>113</td>", "160 COP/kWh", "142 COP/kWh", "-10.9 %", "p = 0.044",
                  "<td>461</td>", "115 COP/kWh", "94 COP/kWh", "-18.7 %", "p < 0.001",
                  "<td>117</td>", "5.31 centUSD/kWh", "4.83 centUSD/kWh", "-9.0 %", "p = 0.081"):
        assert cifra in texto, cifra
    assert "Los errores solo son comparables dentro del mismo objetivo y unidad" in texto
    assert pr.TITULO_E22.lower() in texto.lower() and pr.NOTA_E22 in texto


@pytest.mark.parametrize("pagina,unidad", [("compras", "COP/kWh"), ("bolsa", "COP/kWh"),
                                           ("exportacion", "centUSD/kWh")])
def test_paginas_de_objetivo(pagina, unidad, monkeypatch):
    at = abrir(pagina, monkeypatch)
    texto = textos(at)
    assert pr.REGLA_NOMBRE in texto and pr.NOTA_REGLA in texto
    assert "Semanas con valor observado" in texto and "Periodo" in texto and "Fuente" in texto
    figura = json.loads(at.get("plotly_chart")[0].proto.spec)
    assert unidad in figura["layout"]["yaxis"]["title"]["text"]
    nombres = {d["name"] for d in figura["data"]}
    assert {"Valor observado", "Regla de referencia", "Modelo registrado"} <= nombres
    assert not any("techo" in n.lower() or "regla actual" in n.lower() for n in nombres)


def test_emision_ilustrativa_no_es_registro(monkeypatch):
    texto = textos(abrir("pronostico", monkeypatch))
    assert "Ejemplo con los datos de hoy" not in texto
    assert "Cálculo retrospectivo; no pertenece todavía al registro prospectivo" in texto
    assert ("Este cálculo corresponde al objetivo de referencia: precio nacional de bolsa. No es una emisión actual "
            "de E26 ni representa el precio oficial de una garantía.") in texto
    for campo in ("Fecha simulada de emisión", "Semana objetivo", "Horizonte", "Objetivo pronosticado", "Unidad",
                  "Modelo utilizado", "Regla de referencia", "Estado del cálculo", "Ejemplo retrospectivo"):
        assert campo in texto, campo
    ultimo = json.loads((RAIZ / "results" / "app" / "ultimo_tie.json").read_text(encoding="utf-8"))
    if ultimo.get("estado") == "respaldo":
        assert "Estado: modelo de respaldo" in texto


def test_como_funciona_cuatro_bloques(monkeypatch):
    texto = textos(abrir("como", monkeypatch))
    for bloque in ("A. Datos", "B. Calendario", "C. Tres objetivos", "D. Evaluación"):
        assert bloque in texto
    for termino in ("walk-forward", "Diebold-Mariano", "conformal", "Cobertura", "registro prospectivo",
                    "Error absoluto medio"):
        assert termino.lower() in texto.lower(), termino
    assert "Viernes de la semana s" in texto and "semana objetivo s+2" in texto


@pytest.mark.parametrize("pagina", PAGINAS)
def test_lenguaje_preciso(pagina, monkeypatch):
    bajo = textos(abrir(pagina, monkeypatch)).lower()
    assert not [f for f in pr.FRASES_PROHIBIDAS if f in bajo]
    # "validado" solo aparece negado.
    for m in re.finditer("validado", bajo):
        assert re.search(r"(ningún modelo está|no está) $", bajo[max(0, m.start() - 20):m.start()]), \
            bajo[max(0, m.start() - 60):m.end() + 20]
