"""El precio reconstruido de exportación no puede presentarse como el precio oficial de la garantía.

Revisa el código, la app y la documentación principal. Las bitácoras y auditorías antiguas conservan su
texto original y no se revisan.
"""
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import config  # noqa: E402

ARCHIVOS = sorted(set(RAIZ.glob("src/*.py")) | set(RAIZ.glob("app/*.py"))
                  | {RAIZ / f for f in ("README.md", "FICHA_TECNICA.md", "docs/SUPUESTOS.md", "docs/VARIABLES_XM.md",
                                       "docs/EXPERIMENTOS.md", "docs/PREGUNTAS_XM.md", "docs/CONSULTA_CRM_XM.md")})


def test_ningun_objetivo_es_oficial_ni_validado():
    assert set(config.OBJETIVOS) == {"principal", "referencia", "complementario"}
    for clave, o in config.OBJETIVOS.items():
        for campo in ("nombre", "columna", "unidad", "fuente", "frecuencia", "tipo", "validacion"):
            assert o[campo], f"{clave}: falta {campo}"
        assert o["oficial"] is False, f"{clave} no puede marcarse como oficial sin confirmación de XM"
        assert "reconstruido, no oficial" in config.etiqueta_objetivo(clave)
    assert "no el precio de la garantía" in config.OBJETIVOS["complementario"]["validacion"].lower() or \
        "no es el precio" in config.OBJETIVOS["complementario"]["validacion"].lower() or \
        "no el precio" in config.OBJETIVOS["complementario"]["validacion"].lower()


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: str(p.relative_to(RAIZ)))
def test_sin_frases_que_presenten_el_precio_reconstruido_como_oficial(archivo):
    if not archivo.exists():
        pytest.skip("no existe")
    texto = archivo.read_text(encoding="utf-8").lower()
    if archivo.name == "config.py":
        # La lista de frases prohibidas vive aquí: se quita antes de revisar.
        texto = re.sub(r"frases_prohibidas = \(.*?\)", "", texto, flags=re.S)
    encontradas = []
    for frase in config.FRASES_PROHIBIDAS:
        for m in re.finditer(re.escape(frase), texto):
            # Se admite cuando la misma oración lo niega ("no es…", "no publica…", "ninguna…") o lo pregunta.
            # La oración empieza en el punto o en el separador de tabla anterior (los saltos de línea de un
            # docstring no la cortan).
            inicio = max(texto.rfind(".", 0, m.start()), texto.rfind("|", 0, m.start()), m.start() - 200)
            oracion = texto[inicio:m.end()]
            if re.search(r"\bno\b|ninguna|¿", oracion):
                continue
            encontradas.append(frase)
    assert not encontradas, f"{archivo.name}: {sorted(set(encontradas))}"
