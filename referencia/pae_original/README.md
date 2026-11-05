# PAE: pronóstico semanal del precio de bolsa (versión original)

> **Referencia.** Primera versión del modelo (Ridge de 19 variables + cota conformal), conservada para trazabilidad. El proyecto vigente está en la raíz del repositorio y reproduce exactamente estos resultados (`tests/test_reproduccion.py`). La caché de la API (`datos/xm/`) no se incluye; `python xm_datos.py` la descarga.

Implementación de la propuesta *Pronóstico semanal del precio de bolsa* (caso XM–UNAL): estimar el precio de bolsa promedio de la semana s+1, ponderado por demanda, con la información disponible al cierre de la semana s.

## Archivos

| Archivo | Contenido |
|---|---|
| `xm_datos.py` | Cliente de la API de XM (`servapibi.xm.com.co`) con caché mensual en `datos/xm/`. `python xm_datos.py` descarga 2010–hoy. |
| `variables.py` | Tabla semanal (lunes a domingo) con las variables de la propuesta y ENOS (NOAA). |
| `modelo.py` | Validación walk-forward, métricas, prueba Diebold–Mariano, importancias y pronóstico de la semana siguiente. |
| `AnaliticaPAE.ipynb` | Análisis completo: calidad de datos, descriptivo, evaluación e interpretación. |

## pydataxm y la API de XM

`pydataxm` (repositorio `EquipoAnaliticaXM/API_XM`) envuelve la API pública de XM. Tiene dos clientes:

- `pydataxm.ReadDB`: API de Sinergox (`servapibi.xm.com.co`). `get_collections()` lista las 193 combinaciones métrica/entidad y `request_data(metrica, entidad, inicio, fin)` divide el rango en meses y los pide en paralelo. Las series horarias llegan en formato ancho (`Values_Hour01` … `Values_Hour24`) y las diarias como `Value`.
- `pydatasimem.ReadSIMEM`: datos abiertos de SIMEM (`simem.co`), organizados por *dataset id*.

En Python 3.14 la ruta asíncrona de `ReadDB` falla (`Timeout context manager should be used inside a task`, por `nest_asyncio` con `aiohttp` reciente). `xm_datos.py` hace las mismas peticiones al mismo servicio de forma síncrona. Para usar la librería original se puede crear un entorno con Python 3.11 o 3.12.

## Variables de la propuesta y su fuente

| Variable de la propuesta | Métrica XM (entidad) | Tratamiento semanal |
|---|---|---|
| Precio de bolsa (objetivo) | `PrecBolsNaci` (Sistema, horaria) + `DemaCome` (Sistema, horaria) | P_s = Σ P_h D_h / Σ D_h; solo semanas con 168 h |
| Nivel de embalse | `PorcVoluUtilDiar` (Sistema, diaria) | Volumen útil % al cierre (domingo), promedio y cambio semanal |
| Aportes hídricos | `AporEner`, `AporEnerMediHist` (Sistema, diaria) | Total semanal y relación con la media histórica (1 y 4 semanas) |
| Precios de oferta | `PrecOferDesp` (Recurso, horaria) + `CapEfecNeta` (Recurso, diaria) | Promedio ponderado por capacidad efectiva neta, térmico y no térmico |
| Utilización térmica | `Gene` (Recurso, horaria) + `CapEfecNeta` | FUT_s = Σ G^T / Σ C^T·24 h |
| Clasificación térmica | `ListadoRecursos` (tipo `TERMICA` o `COGENERADOR`) + `ConsCombustibleMBTU` | Los recursos que ya no figuran en el listado se clasifican como térmicos si reportan consumo de combustible |
| Fase ENOS | NOAA CPC, ONI (`oni.ascii.txt`) | Último ONI publicado al cierre de la semana; fase Niño ≥ 0.5, Niña ≤ −0.5; ONI con 3 meses de rezago |

Decisiones que la propuesta dejaba abiertas y que conviene validar con XM:

- **Semana**: lunes a domingo; el pronóstico se emite el lunes con datos hasta el domingo.
- **Ponderación de ofertas**: capacidad efectiva neta (no depende del despacho resultante). Alternativas: generación o disponibilidad declarada.
- **Publicación del ONI**: se asume disponible el día 14 del mes siguiente al cierre de la estación. El archivo de NOAA trae valores revisados, no los publicados en su momento.
- **Precio de la semana s**: se usa la versión vigente en la API; el lunes de emisión solo se conocería la versión preliminar del domingo.

## Evaluación

- Objetivo modelado: y = log(P_{s+1}/P_s); pronóstico = P_s·exp(ŷ).
- Referencia: precio de la semana anterior (ingenuo), como pide la propuesta.
- Modelos: Ridge (lineal, interpretable) y gradient boosting; cuantil 90 % como insumo para la garantía.
- Walk-forward con ventana expansiva, reentrenando cada 4 semanas. Los pronósticos empiezan en 2014 para tener historial de calibración y las métricas se reportan desde 2018.
- Métricas: MAE, RMSE, MAPE, sesgo, mejora frente al ingenuo, Diebold–Mariano y MAE en semanas de alta variabilidad.
- Cota al 90 % para la garantía: Ridge más un margen conformal (cuantil 90 % de los errores log de las últimas 104 semanas ya observadas). Hay una variante con el margen escalado por la volatilidad de las últimas 4 semanas. Se reportan cobertura (global, por año, en semanas normales y agitadas), holgura, faltante y pérdida pinball.

## Uso

```bash
python xm_datos.py
jupyter notebook AnaliticaPAE.ipynb
```
