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
