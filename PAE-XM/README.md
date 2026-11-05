# PAE-XM v2.0

Continuación modular de `../PAE`. La carpeta `PAE` (baseline: `modelo.py`, `AnaliticaPAE.ipynb`) no se modifica.

## Estado

**Etapa 1 (auditoría), Etapa 2 (backtesting), E2 (aporte de exógenas), E3/E4 (LightGBM, XGBoost), E7 (cotas), Modelo C (alertas), dashboard, E8 (datos nuevos y versión del precio) y E9 (latencia, información diaria y dos etapas) listos.** El motor nuevo reproduce el baseline exactamente, verificado por `tests/test_reproduccion.py`.

| Métrica (2018–2026) | Baseline PAE | PAE-XM E1 |
|---|---|---|
| MAE Ridge / GBoost / Ingenuo | 54.303 / 56.706 / 66.553 | idéntico |
| Cota Ridge calibrada: cobertura / pinball | 0.902 / 15.718 | idéntico |

## Estructura

```
data/raw/            caché de la API de XM (copiada de PAE/datos) y ONI de NOAA
data/processed/      semanal.parquet, auditoria.csv, diccionario_datos.csv, clasificacion_recursos.csv
src/xm_client.py          cliente de la API (copia de PAE/xm_datos.py)
src/data_pipeline.py      tabla semanal (copia de PAE/variables.py) + diccionario + auditoría
src/feature_engineering.py variables del baseline + referencia estacional + volatilidad ex ante
src/models.py             catálogo de modelos: E0 (ingenuo, estacional), E1 (Ridge, GBoost, GBoost q90)
src/backtesting.py        walk-forward con registro por emisión y periodos del protocolo
src/calibration.py        conformal con ventana móvil, escala de volatilidad, por régimen (Mondrian) y adaptativo (ACI)
src/evaluation.py         MAE, RMSE, MASE, WAPE, sesgo, DM, IC bootstrap, métricas de cota
src/tuning.py             búsqueda de hiperparámetros con validación temporal antes de 2018
src/experimentos.py       corre E0+E1, E2, E3/E4 y E7 y escribe results/
src/graficas.py           frontera de compromiso de E7
src/alertas.py            Modelo C: eventos críticos, backtest de clasificación, SHAP y alerta actual
dashboard/generar.py      arma dashboard/index.html con los resultados y el pronóstico vigente
dashboard/plantilla.html  diseño del tablero (el generador inserta los datos)
tests/                    reproducción del baseline, calibración y alertas (incluidas pruebas de no fuga)
```

## Uso

```bash
python src/experimentos.py
python -m pytest -q tests
```

`data_pipeline.tabla_semanal(recalcular=True)` reconstruye la tabla desde la caché; `xm_client.descargar_todo()` actualiza la caché desde la API.

## Registro de predicciones

`results/E0_E1.parquet` guarda una fila por semana y modelo con: `semana_base`, `fecha_emision` (lunes posterior), `semana_objetivo`, `modelo`, `variables`, `n_entrenamiento`, `prediccion`, `observado`, `error` y `periodo` (desarrollo ≤ 2021, selección 2022–2024, final ≥ 2025, por semana objetivo). `results/E0_E1_ancho.parquet` tiene el mismo contenido por semana, con las cotas calibradas.

## Hallazgos de la Etapa 1

- **Duplicados en `CapEfecNeta`.** La API repite filas (fecha, recurso) para TBQ3, TBQ4, TGJ1, TYP1 y TMB1 en enero de 2010 y 2011, más días sueltos en 2016 y 2018. En el baseline esto duplica la capacidad térmica del FUT y el peso de esas ofertas en 12 semanas. `tabla_semanal(corregida=True)` los elimina. El MAE de Ridge pasa de 54.303 a 54.340, un efecto despreciable. Se recomienda usar la tabla corregida desde E2.
- **`PrecOferDesp`** no tiene datos el 2021-02-17; esa semana promedia 6 días.
- **`ConsCombustibleMBTU`** tiene una fila por recurso y combustible; no son duplicados y solo se usa para clasificar.
- **Disponibilidad**: `diccionario_datos.csv` registra el supuesto de publicación de cada serie. Pendiente de confirmar con XM.

## Hallazgos de la reproducción por periodo (MAE, COP/kWh)

| Periodo (semana objetivo) | Ingenuo | Estacional | Ridge | Mejora Ridge |
|---|---|---|---|---|
| desarrollo (2018–2021) | 28.3 | 96.7 | 22.5 | 20.5 % |
| selección (2022–2024) | 116.5 | 251.0 | 91.6 | 21.4 % |
| final (2025–2026) | 67.7 | 424.3 | 62.4 | 7.9 % |

- En 2025–2026 Ridge queda por debajo de la meta de 10 % de mejora. Ese periodo ya se vio al diseñar el baseline, así que debe tratarse como exploratorio (sección 6 de la propuesta).
- La referencia estacional (misma semana del año anterior) es mucho peor que el ingenuo, con MAE de 217 frente a 67 en 2018–2026. No sirve como línea base de comparación.
- El MASE usa como escala el MAE del ingenuo en 2010–2021. Como los precios posteriores son más altos, el MASE > 1 refleja el nivel del precio y no un mal desempeño. Para comparar modelos conviene la mejora relativa dentro de cada periodo.

## E2: aporte de las variables exógenas

`python src/experimentos.py e2`. Usa la tabla corregida, las mismas 667 semanas de prueba y los mismos bloques que E1. Ridge recorre conjuntos de variables crecientes desde el precio solo y quita un grupo a la vez (leave-one-group-out); ElasticNet elige su penalización con validación temporal interna (`TimeSeriesSplit`, 5 cortes). La decisión se toma en el periodo de **selección (2022–2024)**; el periodo final es exploratorio. Resultados completos en `results/E2_resumen.csv`.

| Modelo | MAE desarrollo | MAE selección | MAE final | Mejora selección | Dif. vs E1 en selección (IC 95 %) |
|---|---|---|---|---|---|
| Ingenuo | 28.3 | 116.5 | 67.8 | — | |
| Ridge solo precio | 22.2 | 103.3 | 60.6 | 11.4 % | +11.7 (5.1 a 19.9) |
| **Ridge E1 (19 variables)** | 22.6 | **91.6** | 62.4 | **21.4 %** | referencia |
| Ridge E1 sin ENOS ni térmica (14) | 21.8 | 92.0 | 62.7 | 21.1 % | +0.3 (−1.4 a 1.8) |
| Ridge E1 sin hidrología | 23.7 | 98.8 | 60.0 | 15.2 % | +7.2 (3.2 a 12.3) |
| Ridge E1 sin calendario | 23.0 | 96.4 | 62.5 | 17.3 % | +4.8 (1.2 a 9.5) |
| Ridge E1 sin ofertas | 22.5 | 94.3 | 61.7 | 19.1 % | +2.7 (0.1 a 7.3) |
| Ridge E1 + variables nuevas | 21.9 | 94.9 | 60.1 | 18.6 % | +3.3 (0.4 a 7.6) |
| ElasticNet E1 | 22.6 | 96.1 | 62.1 | 17.6 % | +4.5 (2.7 a 6.0) |

Conclusiones:

- **Las exógenas sí aportan, pero solo bajo estrés.** En 2022–2024 bajan el MAE de 103.3 (solo precio) a 91.6, una diferencia significativa. En 2018–2021 no cambian nada (22.2 frente a 22.6), y en 2025–2026 el modelo con solo precio es algo mejor.
- **Lo que más pesa es la hidrología** (embalse y aportes), seguida del calendario y, en menor medida, las ofertas.
- **ENOS y utilización térmica no añaden información** una vez están la hidrología y el precio. Quitarlos no cambia el error (+0.3, IC incluye 0). El modelo de 14 variables es equivalente y más simple. La hipótesis de la propuesta sobre ENOS no se sostiene a una semana; podría revisarse en horizontes mensuales.
- **Las variables nuevas de la Etapa 3** (rezagos y tendencias del precio, volatilidad, demanda, anomalía del embalse, cambio del ONI) no mejoran el periodo de selección y, todas juntas, lo empeoran. En el periodo final sí ayudan (11.3 %). Ese cambio de ordenamiento entre periodos indica inestabilidad, así que no se adoptan.
- **ElasticNet con validación temporal es peor que Ridge** (+4.5, significativo).
- **Periodo final (exploratorio):** Ridge E1 y su versión de 14 variables no alcanzan la meta de 10 % (7.9 % y 7.5 %). Los modelos más simples sí la alcanzan (precio + demanda 12.4 %, precio + térmica 12.4 %). Puede ser un cambio de régimen o sobreajuste al estrés de 2022–2024; hay que vigilarlo con validación prospectiva.

**Decisión de E2:** se mantiene Ridge E1 como referencia y se propone la versión de 14 variables (sin ENOS ni térmica) como candidata, por ser equivalente y más simple. E3/E4 (LightGBM, XGBoost) se compararán contra ambas.

## E3/E4: LightGBM y XGBoost

`python src/experimentos.py e3e4`. Los hiperparámetros se eligieron con búsqueda aleatoria (40 configuraciones por familia) y validación temporal interna (`TimeSeriesSplit`, 5 cortes) usando **solo semanas anteriores a 2018** (`src/tuning.py`, `results/tuning_*.json`). Así ninguna semana evaluada influyó en ellos. Se corren también con parámetros por defecto, para medir el efecto del ajuste. Mismas 667 semanas y bloques que E1.

| Modelo | MAE desarrollo | MAE selección | MAE final | Mejora selección | Dif. vs Ridge E1 en selección (IC 95 %) |
|---|---|---|---|---|---|
| Ingenuo | 28.3 | 116.5 | 67.8 | — | |
| **Ridge E1** | 22.6 | **91.6** | 62.4 | **21.4 %** | referencia |
| Ridge E1 sin ENOS ni térmica | 21.8 | 92.0 | 62.7 | 21.1 % | +0.3 (−1.4 a 1.8) |
| LightGBM E1, por defecto | 22.2 | 93.7 | 66.8 | 19.6 % | +2.1 (−3.7 a 9.0) |
| XGBoost E1, por defecto | 22.2 | 95.6 | 65.4 | 18.0 % | +4.0 (−1.7 a 12.2) |
| LightGBM E1, ajustado | **21.1** | 96.9 | **61.5** | 16.9 % | +5.3 (1.0 a 10.2) |
| GBoost E1 (baseline) | 22.6 | 97.1 | 63.4 | 16.7 % | +5.5 (−1.4 a 14.7) |
| XGBoost E1, ajustado | 21.7 | 99.1 | 63.3 | 15.0 % | +7.5 (3.0 a 13.7) |

Conclusiones:

- **Ningún modelo de boosting supera a Ridge en el periodo de selección.** Los ajustados son significativamente peores (+5.3 y +7.5 COP/kWh); los de parámetros por defecto quedan a la par, sin diferencia significativa.
- **El ajuste de hiperparámetros no generaliza al estrés.** Antes de 2018 los árboles ajustados ganaban a Ridge en validación interna (MAE 28.3 y 27.7 frente a 34.4), y en 2018–2021, un periodo también tranquilo, LightGBM ajustado es el mejor modelo (25.5 % de mejora). En 2022–2024 pasa al revés: lo aprendido en años de precios bajos no se traslada a la sequía.
- **La razón probable es la extrapolación.** Los árboles no extrapolan fuera del rango visto en entrenamiento, mientras que Ridge sí lo hace linealmente. La importancia por permutación en el periodo de selección (`results/E3E4_importancia_seleccion.csv`) lo respalda. Los tres modelos dependen sobre todo de la tendencia dentro de la semana (`ultimo_dia_rel`). Ridge además aprovecha el cambio del embalse y la estacionalidad, que los árboles casi no usan.
- **Los errores de Ridge, LightGBM y XGBoost están muy correlacionados** (0.96 a 0.98). Un ensamble (E6) tiene poco margen de mejora.
- **Periodo final (exploratorio):** LightGBM ajustado logra 9.2 % frente a 7.9 % de Ridge. Ninguno llega a la meta de 10 %.

**Decisión de E3/E4:** Ridge E1 sigue como mejor modelo puntual. El boosting no justifica su complejidad para el horizonte semanal con esta muestra. Si se retoma, habría que ajustar sus hiperparámetros incluyendo episodios de estrés (por ejemplo, la sequía de 2015–2016) o combinarlo con un componente lineal que permita extrapolar.

## E7: cotas superiores al 90 %

`python src/experimentos.py e7`. Sobre la tabla corregida y con las mismas semanas que E1 se compararon 25 cotas:

- **Referencia:** Ridge + conformal con ventana de 104 semanas (la del baseline) y su variante escalada por volatilidad.
- **Por régimen (Mondrian):** el margen se calcula solo con semanas del mismo régimen, conocido al emitir: volatilidad de 4 semanas sobre su percentil 80 histórico, aportes de 4 semanas bajo 80 % de la media, o cualquiera de los dos.
- **Adaptativa (ACI):** el nivel se corrige con cada incumplimiento observado, γ ∈ {0.005, 0.01, 0.02, 0.05}, con y sin escala de volatilidad.
- **Regresión cuantílica directa:** lineal con L1 = 0.02 (elegido con datos anteriores a 2018), LightGBM y el GBoost del baseline; cada una sola, con CQR (conformal sobre el cuantil) y con CQR por régimen.

La elección se hace en el periodo de selección (2022–2024). Tablas completas en `results/E7_resumen.csv`; diferencias de pinball con IC por bootstrap en `results/E7_comparacion_pinball_*.csv`; frontera en `results/E7_frontera_seleccion.png` y `results/E7_frontera_2018-2026.png`.

| Cota (selección 2022–2024) | Cobertura | Cob. semanas volátiles | Exceso medio | Pinball | Dif. pinball vs ref. (IC 95 %) |
|---|---|---|---|---|---|
| **Ridge + conformal (referencia)** | 87.9 % | 65.6 % | 41 % | 26.5 | — |
| Ridge + Mondrian (vol. o hidro) | 85.4 % | 62.5 % | 41 % | 25.6 | −0.9 (−2.3 a 0.7) |
| Ridge + Mondrian (hidro) | 86.0 % | 65.6 % | 36 % | 26.3 | −0.3 (−2.5 a 2.0) |
| LightGBM q90 + CQR Mondrian (vol.) | 89.2 % | 65.6 % | 47 % | 26.4 | −0.1 (−2.6 a 2.5) |
| GBoost q90 + CQR | 90.4 % | 65.6 % | 48 % | 26.6 | +0.1 (−2.5 a 2.3) |
| Ridge + ACI (γ = 0.02) | 87.3 % | 68.8 % | 44 % | 28.2 | +1.7 |
| Ridge + ACI con volatilidad (γ = 0.005) | 87.3 % | 75.0 % | 51 % | 33.0 | |
| Ridge + conformal con volatilidad | 88.5 % | 78.1 % | 58 % | 34.9 | |
| GBoost q90 sin calibrar | 79.0 % | 56.2 % | 39 % | 27.9 | |

En 2018–2026 la referencia en la tabla corregida da cobertura 90.2 % y pinball 15.74 (15.72 en el baseline).

Conclusiones:

- **Ningún método mejora el pinball de forma significativa** frente a Ridge + conformal. En selección todos los IC incluyen 0, y en 2018–2026 también (el mejor, Mondrian vol. o hidro, −0.23 con IC de −0.90 a 0.50). La meta de bajar de 15.7 no se alcanza con evidencia.
- **Ningún método llega a 85 % en semanas volátiles.** El máximo es 78 % (conformal escalado por volatilidad), a cambio de 17 puntos más de exceso medio y pinball 34.9 frente a 26.5. La frontera de Pareto muestra que cada punto de cobertura en semanas volátiles cuesta exceso en todas las demás semanas. Las semanas de saltos grandes son en buena parte impredecibles con la información disponible al emitir.
- **Los regímenes ex ante no capturan las semanas volátiles.** Mondrian por volatilidad o por hidrología no sube la cobertura en semanas de alta variabilidad (62–66 %), porque la volatilidad reciente o los aportes bajos anticipan mal cuál será la semana del salto.
- **La regresión cuantílica directa subcubre** (78–84 % en selección) y necesita CQR. Con CQR iguala a la referencia, pero con más exceso.
- **ACI no aporta**, y con escala de volatilidad es inestable: con γ ≥ 0.01 el margen se dispara (exceso medio de 74 % a 820 %).
- **En selección, la cobertura global de la referencia (87.9 %) queda algo por debajo de 90 %**, porque 2022–2024 fue más difícil que la historia de calibración. En 2018–2021 y 2025–2026 cubre 90.9 % y 92.6 %.

**Decisión de E7:** se mantiene **Ridge + conformal (104 semanas)** como cota principal, porque es la más simple y ninguna alternativa la supera con evidencia. Si XM prioriza no quedar descubierto en semanas agitadas, la alternativa es **Ridge + conformal escalado por volatilidad**: 78 % de cobertura en semanas volátiles, con más recursos inmovilizados. Elegir entre ambas requiere el costo relativo de sobre- y subestimar, que depende de la regla de la garantía. Para acercarse a la meta de 85 % haría falta información nueva que anticipe los saltos, no otro método de calibración: por ejemplo, el pronóstico de aportes de XM o los mantenimientos programados.

## Modelo C: alertas tempranas

`python src/experimentos.py alertas`. Tres eventos, con umbrales calculados solo con información disponible al emitir:

| Evento | Definición | Horizonte |
|---|---|---|
| `precio_alto` | P(s+1) sobre el percentil 90 de las 156 semanas previas | 1 semana |
| `salto` | P(s+1) al menos 25 % mayor que P(s) | 1 semana |
| `estres_hidrico` | Embalse al cierre de s+4 por debajo de 45 % | 4 semanas (a 1 semana la persistencia acierta 88 % y no hay nada que anticipar) |

**Montaje del modelo:**
- **Modelos:** regresión logística (L2, penalización elegida con validación temporal y pesos balanceados) y LightGBM.
- **Variables:** las 19 de E1, las candidatas nuevas y el estado actual de cada evento.
- **Backtest:** walk-forward con los mismos bloques que E1. Una fila solo entra al entrenamiento cuando su evento ya se observó (s + h ≤ emisión).
- **Umbral de alerta:** el que maximiza F2 en el periodo de desarrollo, fijo después. Las probabilidades de la logística balanceada son puntajes, no probabilidades calibradas.
- **Referencia:** la persistencia (alertar si el evento está activo hoy).
- **Inicios:** `recall_inicios` mide cuántos comienzos de episodio, sin el evento activo al emitir, se anticipan.

Resultados en el periodo de selección (2022–2024; tabla completa en `results/alertas_resumen.csv`):

| Evento | Modelo | PR-AUC | Recall | Precisión | F2 | Recall en inicios | % semanas con alerta |
|---|---|---|---|---|---|---|---|
| estrés hídrico (prev. 9 %) | Persistencia | 0.54 | 71 % | 71 % | 0.71 | 0 de 4 | 9 % |
| | **Logística** | 0.85 | **100 %** | **82 %** | **0.96** | **4 de 4** | 11 % |
| | LightGBM | 0.96 | 100 % | 52 % | 0.84 | 4 de 4 | 17 % |
| precio alto (prev. 33 %) | Persistencia | 0.65 | 75 % | 75 % | 0.75 | 0 de 13 | 33 % |
| | Logística | 0.84 | 87 % | 61 % | 0.80 | 6 de 13 | 47 % |
| | **LightGBM** | 0.87 | 85 % | 67 % | 0.80 | 7 de 13 | 42 % |
| salto ≥ 25 % (prev. 22 %) | Persistencia | 0.24 | 29 % | 29 % | 0.29 | 0 de 25 | 22 % |
| | **Logística** | 0.53 | 69 % | 41 % | 0.60 | 15 de 25 | 38 % |
| | LightGBM | 0.50 | 89 % | 32 % | 0.65 | 21 de 25 | 62 % |

Conclusiones:

- **Estrés hídrico a 4 semanas: alerta útil.** La logística anticipó los 4 inicios de episodio del periodo de selección con 82 % de precisión. En 2025–2026 no hubo episodios y la logística no dio falsas alarmas; LightGBM sí, en 5 % de las semanas.
- **Precio alto: mejora moderada sobre la persistencia.** F2 de 0.80 frente a 0.75, y anticipa cerca de la mitad de los inicios. En 2025–2026 solo hubo 2 semanas con precio alto, demasiado pocas para evaluar.
- **Saltos ≥ 25 %: hay señal, pero con mucho ruido.** La PR-AUC (0.50–0.53) duplica la prevalencia (0.22), y la logística detecta 69 % de los saltos y 15 de 25 inicios. El costo es alertar en 38 % de las semanas, con 41 % de precisión. LightGBM detecta más (89 %) pero alerta en 62 % de las semanas, lo que en la práctica no sirve.
- **La alerta de salto no mejora la cota de E7.** Usarla como régimen Mondrian para Ridge + conformal deja la cobertura en semanas volátiles en 63–66 % y no cambia el pinball de forma significativa (columnas `Ridge+mondrian_alerta_salto*` en `results/E7_cotas.parquet`). Ridge ya usa la misma información; lo que falta para anticipar los saltos son datos nuevos.
- **Variables asociadas** (|SHAP| medio de LightGBM en selección, `results/alertas_shap_seleccion.csv`):
  - **Estrés hídrico:** nivel del embalse y estación del año.
  - **Precio alto:** nivel de la oferta no térmica, si ya se está en precio alto, nivel del precio y aportes respecto a la media.
  - **Salto:** tendencia dentro de la semana (`ultimo_dia_rel`) y brecha entre la oferta no térmica y el precio. Es decir, el precio salta cuando las ofertas hidráulicas ya están muy por encima del precio vigente.

**Alerta actual** (`results/alerta_actual.csv`, semana base 2026-10-19): sin alerta de precio alto ni de estrés hídrico a 4 semanas (embalse en 77 %). Solo LightGBM marca salto, pero lo hace en la mayoría de las semanas; la logística no alerta (puntaje 0.33, umbral 0.45). Cada fila incluye las cinco variables con mayor contribución.

## Dashboard

`python dashboard/generar.py` produce `dashboard/index.html`, un archivo autocontenido (solo carga Chart.js y las fuentes desde CDN) con:

- pronóstico Ridge de la semana siguiente, cota al 90 % (y su variante por volatilidad) y condición del sistema;
- precio real frente al pronóstico fuera de muestra con la banda hasta la cota, con rangos de 1 año, 3 años o desde 2018 y una tabla de las últimas 12 semanas;
- las tres alertas con su puntaje, umbral, variables que más pesan esta semana, historial y desempeño frente a la persistencia;
- hidrología (embalse y aportes de 4 semanas), frontera de las cotas de E7 y tablas de comparación de modelos y cotas.

Para actualizarlo cada semana:

```bash
python -c "import sys; sys.path.insert(0,'src'); import xm_client as x; x.descargar_todo()"
python -c "import sys; sys.path.insert(0,'src'); import data_pipeline as dp; dp.tabla_semanal(recalcular=True, corregida=True)"
python src/experimentos.py e7
python src/experimentos.py alertas
python dashboard/generar.py
```

El pronóstico vigente se reentrena con toda la historia en cada generación; las tablas de evaluación salen de `results/`.

## E8: datos nuevos y versión del precio

`python src/experimentos.py e8` (precio vigente) y `python src/experimentos.py e8 tx1` (precio al emitir).

**Series nuevas** (en `xm_client.SERIES`, todas con historia 2010–2026):

| Serie XM | Variable semanal | Qué mide |
|---|---|---|
| `DispoDeclarada` (Recurso) | `margen_reserva`, `margen_cambio` | Disponibilidad declarada con la oferta sobre la demanda, menos 1, y su cambio semanal |
| `DispoReal` (Recurso) + `CapEfecNeta` | `indisponibilidad`, `indisp_termica` | 1 − disponibilidad real / capacidad efectiva: mantenimientos y salidas, total y térmica |
| `PrecEsca` (Sistema) | `precio_vs_escasez`, `oferta_nt_vs_escasez` | Distancia en log del precio y de la oferta no térmica al precio de escasez |
| `PrecBolsNaciTX1` (Sistema) | — | Versión preliminar del precio, la única disponible el lunes de emisión |

Descartadas: `MaxPrecOferNal` (coincide con el precio de bolsa hora a hora) y los precios de escasez de activación, marginal y superior (solo existen desde 2023).

**Resultados (MAE, COP/kWh; tabla en `results/E8_resumen.csv`):**

| Modelo | 2018–21 | 2022–24 | 2025–26 | Dif. vs Ridge E1 en 2022–24 (IC 95 %) |
|---|---|---|---|---|
| Ingenuo | 28.3 | 116.5 | 67.8 | |
| Ridge E1 | 22.6 | 91.6 | 62.4 | referencia |
| Ridge E1 + indisponibilidad | 22.5 | 91.0 | 62.3 | −0.6 (−1.6 a 0.5) |
| Ridge E1 + escasez | 22.3 | 91.5 | 62.5 | −0.2 (−0.4 a 0.1) |
| Ridge E1 + disponibilidad | 22.7 | 91.8 | 62.1 | +0.2 (−0.3 a 0.8) |
| Ridge E1 + todos los nuevos | 22.5 | 91.1 | 62.2 | −0.5 (−1.4 a 0.7) |
| Ridge solo precio + nuevos | 22.3 | 101.7 | 59.0 | +10.1 (4.5 a 17.5) |
| LightGBM E1 + nuevos, por defecto | 22.4 | 94.4 | 66.9 | +2.8 (−2.6 a 10.3) |

- **Los datos nuevos no mejoran el pronóstico de forma significativa.** El mejor aporte, el de la indisponibilidad del parque, es de 0.6 COP/kWh y su IC incluye 0. Sin las exógenas de E1, los nuevos datos suben la mejora del modelo de solo precio de 11.4 % a 12.8 %; es decir, su información se superpone con la hidrología y las ofertas que ya están en el modelo.
- **Tampoco mejoran las alertas.** La PR-AUC de salto queda en 0.52 frente a 0.53 y la de precio alto en 0.86 frente a 0.84 (`results/alertas_e8_resumen.csv`).
- **La versión del precio no invalida los resultados.** TX1 difiere del precio vigente en −1.8 % en promedio semanal (hasta 45 % en una semana de 2024). Rehaciendo todo con TX1 para la semana base (`semanal_tx1.parquet`), el MAE de Ridge E1 en 2018–2026 pasa de 54.3 a 54.9, y el del ingenuo de 66.6 a 68.3, así que la mejora relativa sube de 18.4 % a 19.6 %. La cota conserva 90.2 % de cobertura y su pinball pasa de 15.74 a 15.79. Las métricas reportadas son, como mucho, 1 % optimistas en MAE.

**Decisión de E8:** Ridge E1 sigue como modelo principal y las series nuevas quedan en la caché por si un modelo diario o de dos etapas las aprovecha. La señal que falta para anticipar los saltos probablemente está a escala diaria u horaria, por ejemplo en las ofertas y el despacho del primer día de la semana objetivo, no en agregados semanales.

## E9: latencia de publicación, información diaria y modelo en dos etapas

`python src/experimentos.py e9` (semana base completa) y `python src/experimentos.py e9 viernes` (semana base hasta el viernes).

### Latencia real de la API

Consultado el martes 3 de noviembre de 2026 a las 15:17:

| Serie | Último día publicado | Rezago |
|---|---|---|
| Precio, TX1, demanda, ofertas, generación, combustible, precio de escasez | sábado 31 de octubre | ~3 días |
| Capacidad efectiva | domingo 1 de noviembre | 2 días |
| Aportes, embalse | lunes 2 de noviembre | 1 día |
| Disponibilidad declarada y real, generación programada | martes 3 de noviembre | ninguno (se conoce antes del día) |

Si el pronóstico se emite el lunes con lo que publica la API, de la semana base solo se conoce hasta el viernes. Sin embargo, todo lo anterior a E9 supuso la semana completa, incluido el precio del domingo, que es la variable más importante. Con el mismo Ridge E1 (MAE 2018–2026):

| Información de la semana base hasta | Ingenuo | Ridge E1 | Mejora |
|---|---|---|---|
| domingo (supuesto anterior) | 66.6 | 54.3 | 18.4 % |
| sábado | 70.2 | 59.9 | 14.7 % |
| viernes | 73.2 | 62.8 | 14.2 % |
| jueves | 76.1 | 67.9 | 10.8 % |

El rezago puede ser solo de la API o del fin de semana; el rezago operativo real y la hora de emisión deben confirmarse con XM. Las tablas con corte están en `data/processed/semanal_corte*.parquet`, y una prueba verifica que el corte no usa el fin de semana.

### Variables nuevas

- **Dinámica diaria dentro de la semana base:** `pendiente_diaria` (pendiente del log del precio diario) y `ultimos2_rel` (promedio de los dos últimos días conocidos sobre el promedio de la semana).
- **Despacho programado del lunes de la semana objetivo** (`GeneProgDesp`, publicado el día anterior): `termica_prog_rel` (térmica programada del lunes sobre la térmica real diaria media de la semana base) y `part_termica_prog`. Es la única información de la propia semana objetivo que existe al emitir.

### Modelo en dos etapas (`models.DosEtapas`)

1. Una regresión logística multinomial clasifica la semana objetivo en baja (≤ −20 %), normal o subida (≥ +25 %). Su penalización, C = 0.01, se eligió por log-loss solo con semanas anteriores a 2018.
2. Un Ridge por régimen estima la magnitud del cambio.

Se probaron tres formas de combinar las etapas: `media` (promedio del precio ponderado por las probabilidades), `duro` (régimen más probable) y `apilado` (Ridge con las probabilidades como variables, calculadas fuera de muestra).

La primera corrida no terminó: `LogisticRegressionCV` en cada bloque, más 24 hilos por proceso, la hacía cientos de veces más lenta. Con C fijo, un hilo por proceso y registro de avance, cada escenario tarda ~2 minutos.

### Resultados (MAE, COP/kWh; `results/E9_corte6_resumen.csv` y `results/E9_corte4_resumen.csv`)

| Modelo | Semana completa: 2022–24 | Semana completa: 2018–26 | Hasta viernes: 2022–24 | Hasta viernes: 2018–26 | Dif. vs Ridge E1, hasta viernes, 2018–26 (IC 95 %) |
|---|---|---|---|---|---|
| Ingenuo | 116.5 | 66.6 | 126.9 | 73.2 | |
| Ridge E1 | 91.6 | 54.3 | 104.8 | 62.8 | referencia |
| **Ridge E1 + despacho programado** | 90.6 | 54.0 | **100.3** | **61.2** | **−1.7 (−3.6 a −0.3)** |
| Ridge E1 + diario + programado | 91.8 | 54.2 | 100.5 | 61.3 | |
| Dos etapas, apilado (E1 + E9) | 91.1 | 54.0 | 98.6 | 60.5 | −2.4 (−5.8 a 0.2) |
| Dos etapas, media (E1 + E9) | 95.2 | 55.6 | 101.8 | 61.3 | −1.5 (−5.8 a 1.7) |
| Dos etapas, duro (E1) | 103.8 | 59.7 | 108.2 | 65.7 | |

Conclusiones:

- **Con la semana completa nada mejora a Ridge E1 de forma significativa.** El precio del domingo ya contiene la información que aportan las variables nuevas.
- **En el escenario realista, hasta el viernes, el despacho programado del lunes sí aporta.** Ridge E1 + programado baja el MAE de 62.8 a 61.2 en 2018–2026 y de 104.8 a 100.3 en 2022–2024, ambas diferencias significativas. Recupera parte de lo que se pierde por no conocer el fin de semana, y la cota conformal sobre este modelo pasa de 88 % a 89 % de cobertura y de pinball 16.1 a 15.8.
- **Las dos etapas no superan con significancia a Ridge.** La versión apilada logra el menor MAE en el escenario realista (60.5, mejora de 17.4 % sobre el ingenuo), pero su IC incluye 0. La versión `media` casi elimina el sesgo a subestimar: −0.9 COP/kWh frente a −15 de Ridge. Eso importa para una garantía, donde quedarse corto es lo costoso, pero su MAE no mejora. La versión `duro` es la peor, porque elegir un solo régimen amplifica los errores de clasificación.
- **Periodo final (exploratorio), hasta el viernes:** todos los modelos mejoran poco al ingenuo (2–7 %). La versión `media` es la mejor (7.0 %).

**Decisión de E9:** el modelo principal depende de cuándo se emite.
- **Con la semana base completa** (emisión el martes o miércoles, o si XM confirma rezago de 1 día): se mantiene Ridge E1.
- **Con emisión el lunes y datos hasta el viernes:** Ridge E1 + despacho programado, y el modelo en dos etapas apilado como candidato para validación prospectiva.
- **Si la regla de la garantía castiga más subestimar:** conviene evaluar la versión `media` de dos etapas por su sesgo casi nulo.

El dashboard sigue mostrando el escenario de semana completa hasta que se confirme la latencia con XM.
