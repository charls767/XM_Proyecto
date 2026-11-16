"""Emisión TIE: calendario de la regla y registro encadenado."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import semanal_tie as st  # noqa: E402


def test_semanas_de_la_regla():
    # Ejemplo del material de XM: cálculo el viernes 14-feb-2025 para la semana 22 a 28 de febrero.
    s, base, objetivo = st.semanas("2025-02-14")
    assert s == pd.Timestamp("2025-02-08") and base == pd.Timestamp("2025-02-01")
    assert objetivo == pd.Timestamp("2025-02-22")
    # Cualquier día de la misma semana TIE da las mismas semanas.
    assert st.semanas("2025-02-08") == (s, base, objetivo)


def test_emision_en_seco_se_reproduce_desde_el_snapshot():
    """Emite con la caché local para el viernes 13-nov-2026, sin registrar, y reconstruye el
    pronóstico y la cota solo con lo que guarda el snapshot."""
    import data_pipeline as dp
    if not (dp.RAW / "xm" / "precio" / "2026-11.parquet").exists():
        import pytest
        pytest.skip("falta la caché de precios de noviembre de 2026")
    r = st.emitir("2026-11-13", actualizar=False, guardar=False)
    assert r["semana_base"] == pd.Timestamp("2026-10-31")
    assert r["semana_objetivo"] == pd.Timestamp("2026-11-21")
    assert r["estado"] in ("normal", "vigilancia", "respaldo")
    assert r["cota90"] > r["pronostico"] > 0
    # El entrenamiento solo usa filas cuyo objetivo ya terminó antes de la emisión.
    hasta = pd.Timestamp(r["reproduccion"]["entrenamiento_hasta"])
    assert hasta + pd.Timedelta(weeks=3, days=6) < pd.Timestamp("2026-11-13")
    pred, cota = st.reproducir({"variables": r["variables"], "precio_base": r["precio_base"],
                                "reproduccion": r["reproduccion"]})
    assert abs(pred - r["pronostico"]) < 1e-6 and abs(cota - r["cota90"]) < 1e-6
    # El candidato en paralelo también se reproduce desde lo que guarda.
    c = r["candidato"]
    assert c is not None
    pred_c, cota_c = st.reproducir({"variables": c["variables"], "precio_base": r["precio_base"],
                                    "reproduccion": c["reproduccion"]})
    assert abs(pred_c - c["pronostico"]) < 1e-6 and abs(cota_c - c["cota90"]) < 1e-6


def test_precio_de_exportacion_cuadra_con_el_ejemplo_de_xm():
    """Semana base del 18 al 24 de enero de 2025: XM proyectó 22.75 centUSD/kWh tras restar el CEE.
    El precio total debe ser algo mayor (24.3) y el pronóstico debe reproducirse desde lo guardado."""
    import data_pipeline as dp
    import pytest
    if not (dp.RAW / "xm" / "expo_usd" / "2025-01.parquet").exists():
        pytest.skip("falta la caché de exportaciones")
    t = dp.tabla_expo()
    p = t.at[pd.Timestamp("2025-01-18"), "precio_expo"]
    assert 22.75 < p < 22.75 + 3  # el CEE es de unos pocos centavos
    assert t.at[pd.Timestamp("2025-01-18"), "precio_expo_sig"] == t.at[pd.Timestamp("2025-02-08"), "precio_expo"]
    r = st.emitir("2025-02-14", actualizar=False, guardar=False)
    e = r["expo"]
    assert e is not None and e["regla"] == pytest.approx(t.at[pd.Timestamp("2025-02-01"), "precio_expo"])
    pred, cota = st.reproducir_expo(e)
    assert abs(pred - e["pronostico"]) < 1e-6 and abs(cota - e["cota90"]) < 1e-6 and cota > pred


def test_registro_detecta_alteracion(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "ARCHIVO", tmp_path / "pronosticos_tie.csv")
    monkeypatch.setattr(st, "REGISTRO", tmp_path)
    r = {"fecha_emision": pd.Timestamp("2026-11-20"), "semana_calculo": pd.Timestamp("2026-11-14"),
         "semana_base": pd.Timestamp("2026-11-07"), "semana_objetivo": pd.Timestamp("2026-11-28"),
         "version_modelo": "prueba", "estado": "normal", "motivos": [], "datos_hasta": {"precio": pd.Timestamp("2026-11-17")},
         "precio_base": 400.0, "precio_parcial": 410.0, "regla_xm": 400.0, "pronostico": 405.0,
         "cambio_pct": 1.25, "cota90": 600.0, "variables": {}, "modelo": {}}
    assert st.registrar(r)
    assert not st.registrar(r)  # no se reescribe
    assert st.verificar_registro() == []
    reg = pd.read_csv(st.ARCHIVO)
    reg.loc[0, "pronostico"] = 999.0
    reg.to_csv(st.ARCHIVO, index=False)
    assert st.verificar_registro() == ["2026-11-07"]
