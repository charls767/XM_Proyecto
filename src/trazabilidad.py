"""Trazabilidad de corridas sin servidores: results/corridas.jsonl.

Cada experimento anota su comando, commit, si había cambios sin guardar, huella de los
datos y versiones. Para un proyecto de una persona con corridas semanales, esto cubre lo
que aportaría MLflow (saber con qué código y datos salió cada resultado) sin operar un servicio.
"""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess

RAIZ = Path(__file__).resolve().parents[1]


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def huella_datos(archivo=RAIZ / "data" / "processed" / "semanal_corregida.parquet"):
    return hashlib.sha256(archivo.read_bytes()).hexdigest()[:16] if archivo.exists() else None


def registrar_corrida(comando, opciones=()):
    import numpy
    import pandas
    import sklearn

    corrida = {
        "fecha": datetime.now().isoformat(timespec="seconds"), "comando": comando, "opciones": list(opciones),
        "commit": _git("rev-parse", "--short", "HEAD"), "cambios_sin_guardar": bool(_git("status", "--porcelain", "src")),
        "datos": huella_datos(), "python": platform.python_version(),
        "versiones": {"numpy": numpy.__version__, "pandas": pandas.__version__, "scikit-learn": sklearn.__version__},
    }
    with open(RAIZ / "results" / "corridas.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(corrida, ensure_ascii=False) + "\n")
    return corrida
