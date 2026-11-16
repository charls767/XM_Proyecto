"""El informe PDF se genera con los resultados de results/app/ y tiene sus seis páginas (la 2 es el objetivo principal, E26)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import informe_pdf  # noqa: E402

DATOS = Path(__file__).resolve().parents[1] / "results" / "app" / "predicciones_tie.parquet"


@pytest.mark.skipif(not DATOS.exists(), reason="falta results/app (python src/resultados_app.py)")
def test_informe_pdf_se_genera(tmp_path, monkeypatch):
    # No toca la copia que descarga la app.
    monkeypatch.setattr(informe_pdf, "DATOS", informe_pdf.DATOS)
    copia = tmp_path / "copia.pdf"
    monkeypatch.setattr(informe_pdf.shutil, "copyfile", lambda a, b: copia.write_bytes(Path(a).read_bytes()))
    ruta = informe_pdf.generar(destino=tmp_path / "informe.pdf")
    datos = ruta.read_bytes()
    assert datos.startswith(b"%PDF")
    import re
    assert len(re.findall(rb"/Type\s*/Page[^s]", datos)) == 6
    assert copia.exists()


def test_paleta_isa101_reserva_el_color_para_alarmas():
    import isa101 as isa
    grises = [isa.FONDO, isa.FONDO_PANEL, isa.REAL, isa.REGLA, isa.PRUEBA, isa.TECHO, isa.SUBE, isa.BAJA]
    for c in grises:  # lo normal va en escala de grises: R = G = B
        assert c[1:3] == c[3:5] == c[5:7], c
    assert isa.ALARMA_ALTA not in grises and isa.ESTADO_COLOR["normal"] == isa.FONDO_PANEL
