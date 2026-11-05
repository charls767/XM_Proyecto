# XM_Proyecto

Pronóstico semanal del precio de bolsa del Mercado de Energía Mayorista (MEM) colombiano, cota de riesgo al 90 % y alertas tempranas. Caso XM–UNAL.

La pregunta de trabajo: con la información disponible al cierre de una semana, ¿qué tan bien se anticipa el precio de bolsa promedio de la siguiente, ponderado por demanda, como insumo para la garantía de los intercambios de energía con Ecuador?

| Carpeta | Contenido |
|---|---|
| [`PAE-XM/`](PAE-XM/README.md) | Proyecto v2.0: datos, motor de backtesting, modelos, cotas, alertas, pruebas y dashboard. **Empieza aquí.** |
| [`PAE/`](PAE/README.md) | Modelo original (Ridge + conformal) y su notebook `AnaliticaPAE.ipynb`, que PAE-XM reproduce exactamente. |

## Instalación

Requiere **Python 3.11**: la librería oficial `pydataxm` falla en 3.12 o superior por su dependencia `nest_asyncio`.

```bash
cd PAE-XM
python3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q tests
```

Los datos de XM ya vienen en `PAE-XM/data/` y `PAE/datos/`. `PAE-XM/README.md` explica cómo actualizarlos, cómo correr cada experimento y cómo regenerar el dashboard.

## Fuentes

- API pública de XM (`servapibi.xm.com.co`), consultada con [`pydataxm`](https://github.com/EquipoAnaliticaXM/API_XM).
- Índice ONI de NOAA CPC para la fase de El Niño–Oscilación del Sur.

Prototipo académico; no es una publicación oficial de XM.
