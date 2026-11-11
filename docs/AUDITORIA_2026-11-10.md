# Segunda auditoría: modelos y aplicación

**Fecha:** 10 de noviembre de 2026 · **Alcance:** todo `src/`, `dashboard/`, `tests/`, `registro/`, resultados E0–E13 y la emisión del 5 de noviembre · **Complementa:** [AUDITORIA.md](AUDITORIA.md) (5 de noviembre), cuyos hallazgos no se repiten aquí.

## Veredicto

La mecánica sigue siendo sólida: las 59 pruebas pasan, no encontré fugas nuevas en el backtest y la especificación de Ridge 14 resiste las variantes razonables. **Los problemas nuevos están en el presente y en la operación, no en el diseño:**

1. **En el último año el modelo se queda corto de forma significativa y casi no le gana al ingenuo,** y el monitoreo no lo detecta porque no vigila el sesgo.
2. **Con la emisión del miércoles, el modelo oficial ignora información que ya está publicada a esa hora** (el costo marginal programado de la semana objetivo), que reduce el error a la mitad.
3. **Lo que se emite no es exactamente lo que se evaluó:** faltan días de ofertas al emitir, la calificación usa precios preliminares y la emisión no se puede reproducir desde el snapshot.

Todas las cifras de abajo se midieron sobre la caché local, sin consultar la API. Los guiones están al final.

---

## Hallazgos

### Alto

**A1. Sesgo reciente significativo, sin control que lo detecte.**

| Ventana (hasta la semana base 2026-10-19) | MAE Ridge 14 | MAE ingenuo | Sesgo Ridge 14 | p del sesgo (HAC) | p DM frente al ingenuo | Cobertura de la cota |
|---|---|---|---|---|---|---|
| Últimas 26 semanas | 102.2 | 104.4 | **−53.7** | **0.03** | 0.83 | 92 % |
| Últimas 52 semanas | 75.0 | 81.3 | **−31.6** | **0.03** | 0.33 | 90 % |
| Últimas 104 semanas | | | −4.8 | 0.72 | 0.10 | 92 % |

- **Todos los modelos del proyecto comparten el sesgo:** en 52 semanas, SARIMAX −32.9, Ridge 19 −27.4, LEAR directo −38.6. El ingenuo tiene −7.7. Es un problema de la familia de modelos, no de Ridge 14.
- **Causa probable:** 2026 es un año de precios altos (promedio 502 COP/kWh frente a 245 en 2025). Las variables de reversión a la media (nivel del precio con coeficiente negativo) empujan hacia abajo durante una subida sostenida. En 2026 el aporte medio del nivel del precio es −2.8 %, y en 2023–2024 fue −3.6 % y −3.9 %, años con sesgos de −19 y −38 COP/kWh. Es una hipótesis compatible con los datos, no una prueba.
- **El monitoreo no lo ve.** `monitoreo.estado` solo revisa que la razón de MAE pase de 1.0 (hoy es 0.96) y que la cobertura no baje de 80 % (hoy 92 %). El tablero muestra el sesgo con semáforo, pero no cambia el estado. En la corrida en seco de hoy, el estado es *vigilancia* solo por la demanda incompleta.
- **Por qué importa para la garantía:** cuando el precio sube, el pronóstico puntual se queda corto por varias decenas de COP/kWh. La cota cubre, pero solo porque hoy es muy ancha (ver M5).

**Recomendación:** añadir a `monitoreo.estado` un control de sesgo (p HAC < 0.05 en 26 semanas, o |sesgo| > 5 % del precio medio) que pase a *vigilancia*. Registrar en paralelo una corrección de sesgo adaptativa, como el factor de Duan de la primera auditoría o una media móvil del error log de las últimas 26 semanas, y decidirla con el registro.

**A2. La hora de emisión y el modelo no coinciden.**

El proceso emite el miércoles, cuando la semana objetivo ya empezó. A esa hora XM ya publicó el costo marginal programado (`CostMargDesp`) del lunes al miércoles: la caché tiene datos hasta hoy, 10 de noviembre. E12 muestra lo que cuesta no usarlo:

| Modelo (2018–2026) | MAE | MAE últimas 26 semanas |
|---|---|---|
| Ridge 14 (oficial) | 53.9 | 95.4 |
| Regla sin parámetros: ingenuo × cambio del CMg de 3 días | 36.0 | 65.3 |
| Ridge con solo 2 variables de CMg (3 días) | **33.2** | **48.5** |
| Ridge 14 + CMg de 3 días | 33.4 | 49.1 |

Con el CMg disponible, **las 14 variables ya no aportan nada** (33.4 frente a 33.2). Emitir el miércoles con Ridge 14 es la peor combinación: no tiene la antelación de una emisión el lunes ni usa la información del miércoles.

**Recomendación:** que XM decida la hora de emisión. Si es el domingo o el lunes, el modelo es Ridge 14 + programado (E9). Si es el miércoles, el modelo es el de CMg, y hay que confirmar que la historia de `CostMargDesp` en la API es la versión ex ante y no una revisada. Para eso, guardar cada semana el CMg tal como se publicó, como ya hace `results/E12_cmg_publicado_2026-11-10.csv`, y compararlo luego con la historia de la API.

**A3. La ventaja del candidato se invirtió en el periodo reciente.**

| | MAE 26 semanas | Sesgo 26 semanas | MAE 52 semanas |
|---|---|---|---|
| Ridge 14 (oficial) | 101.4 | −52.9 | 74.7 |
| Ensamble Ridge 14 + LEAR (candidato) | 104.5 | −61.8 | 76.0 |
| LEAR directo | 110.7 | −70.6 | 79.0 |

La regla fijada de antemano (26 semanas del registro) sigue siendo la forma correcta de decidir. Pero el candidato llega con peor desempeño simulado en el régimen actual y con más sesgo, y no conviene esperar que gane.

### Medio

**M1. Desfase entre lo emitido y lo evaluado en las ofertas.** El snapshot del 5 de noviembre registra `oferta` hasta el **31 de octubre**: faltaba el domingo de la semana base. El precio sí llegaba al 2 de noviembre. El backtest siempre usa los 7 días. Medí el efecto entrenando con semanas completas y prediciendo con ofertas parciales (460 semanas, 2018–2026):

| Ofertas disponibles al emitir | MAE | Cambio de la predicción, media absoluta | p95 |
|---|---|---|---|
| Lunes a domingo (backtest) | 54.05 | | |
| Lunes a sábado (emisión real) | 54.22 | 0.15 % | 0.44 % |
| Lunes a viernes | 54.40 | 0.30 % | 0.88 % |

El efecto es pequeño, pero ningún control lo detecta: «Variables completas» solo revisa que no falte el dato, no que cubra la semana. Lo mismo pasa en LEAR, porque `tabla_diaria` aplica `ffill()` a toda la tabla y los últimos días heredan la oferta del último día publicado.
**Recomendación:** un control por serie, `datos_hasta[serie] >= semana_base + 6 días`, con aviso si falla, y calcular en el backtest las ofertas con el mismo rezago que tienen en operación.

**M2. Se califica con el precio preliminar y nunca se vuelve a calificar.** `calificar` llena `real` la primera vez que la semana está completa. XM revisa durante semanas y el backtest usa el precio revisado. La comparación entre el registro y el backtest mezcla versiones.
**Recomendación:** guardar `real_preliminar` y `real_firme`, y llenar la segunda cuando el mes salga de la ventana de refresco de 90 días.

**M3. El monitoreo usa el backtest, no el registro.** `desempeno_reciente` mide pronósticos simulados, reentrenados cada 4 semanas sobre datos ya revisados, no los emitidos. Es razonable mientras el registro tenga una sola fila, pero debe cambiar cuando acumule historia.
**Recomendación:** con 8 o más semanas calificadas, monitorear con el registro y dejar el backtest como referencia.

**M4. El ONI no se actualiza en la operación.** `data_pipeline.oni()` solo descarga el archivo si no existe. Hoy llega a JAS-2026 y está al día, pero en un mes quedará vencido sin aviso, y `merge_asof` seguirá usando el último valor. Afecta a las alertas, que usan `oni`, `oni_rezago`, `fase_enos` y `oni_cambio_3m`. El contexto lo hace más importante: según el archivo, el ONI de JAS-2026 es **+2.16**, un El Niño fuerte en curso. ENOS salió del modelo porque no aportaba en selección (en las últimas 26 semanas, Ridge 19 con ENOS: 100.9 frente a 102.2; no es concluyente).
**Recomendación:** renovar `oni.txt` cada mes, con el mismo patrón del listado de recursos, y añadir un control de antigüedad.

**M5. La cota se encareció después de la sequía.** El exceso de la cota sobre el pronóstico pasó de 21–28 % (2018–2022) a **45–47 %** (2024–2026), porque la ventana fija de 104 semanas conserva los errores de 2023–2024. En 2025 cubrió 94 %, más de lo prometido. Hoy las dos cotas difieren en 30 %: 568 la fija y 438 la de volatilidad.
**Recomendación:** escoger la cota con la pinball del periodo final y con la regla de costo de XM. ACI y la cota por volatilidad ya están implementadas (E7). Además, fijar por escrito cuál de las dos se entrega.

**M6. La emisión no se puede reproducir y el registro no está anclado.**
- El snapshot guarda las variables, pero no los coeficientes, el alfa, la media y escala del escalador, el margen conformal ni la huella de la tabla de entrenamiento. Con los datos revisados, el pronóstico de una semana no se puede reconstruir.
- La cadena SHA-256 la puede recalcular cualquiera que edite el CSV, así que solo revela alteraciones si hay un ancla externa. `correr_semanal.bat` no hace commit (era la recomendación 7 de la primera auditoría). Las columnas de calificación no están selladas.

**Recomendación:** ampliar el snapshot con esos datos y hacer `git commit` y un tag del registro al final del `.bat`.

**M7. Las alertas dependen de un archivo de experimentos.** `semanal._alertas` lee los umbrales de `results/alertas_resumen.csv`. Volver a correr `experimentos.py alertas` cambia la operación sin cambiar `VERSION_MODELO`.
**Recomendación:** fijar los umbrales en `config.py` bajo una versión.

**M8. El sesgo histórico está mal enmarcado.** Los −12.5 COP/kWh de 2018–2026 son sobre todo un efecto de escala. En porcentaje, el sesgo anual va de −3.9 % a +4.5 %, con signos mezclados, y la mediana del error log es ≈ 0. Ridge en log estima la mediana, que es lo óptimo para el MAE; por eso Duan sube el MAE. El sesgo que sí preocupa es el direccional y reciente de A1.
**Recomendación:** reportar el sesgo en porcentaje y por régimen, y no presentar el sesgo agregado como defecto.

### Bajo

| # | Hallazgo | Evidencia | Recomendación |
|---|---|---|---|
| B1 | **Deriva de las variables nominales.** El aporte medio del precio de oferta térmico pasó de +0.2 a 1.1 % (2018–2021) a +5.6 a 6.5 % (2025–2026) | Medido por año, entrenando antes de cada año | La versión con variables relativas no mejora (54.24 frente a 54.05, p = 0.77). No cambiar, pero vigilar los aportes por variable |
| B2 | **El reality check de White es conservador** con 67 modelos, muchos débiles; p = 0.52 exagera la falta de evidencia. El SPA descartado rechazaba 11 % en 150 repeticiones (error estándar ≈ 1.8 pp), lo que apunta más a un error de implementación que a una propiedad del SPA | `evaluation.reality_check` | Usar `arch.bootstrap.SPA` o el Model Confidence Set. Unificar el criterio: E12 se corrigió solo dentro de sus 9 modelos y E11 dentro de 67 (en E12 no cambia la conclusión) |
| B3 | **El tablero vuelve a calcular la emisión** (`emitir(guardar=False)`) en lugar de leer el registro, y puede mostrar cifras distintas de las registradas | `nota_registro` existe para tapar eso | Mostrar el registro y el snapshot como fuente de verdad |
| B4 | **El `.bat` no deja bitácora ni avisa si falla**; el Programador de tareas falla en silencio | `correr_semanal.bat` | Redirigir la salida a `registro/logs/` y enviar un aviso si falla |
| B5 | **La integración continua no prueba la emisión de punta a punta**, aunque en seco tarda 5.5 s | `.github/workflows/pruebas.yml` | Añadir `emitir(actualizar=False, guardar=False)` como prueba de humo |
| B6 | **Avisos de obsolescencia de scikit-learn 1.10** en `LogisticRegressionCV` (`l1_ratios`, atributos heredados) | Corrida en seco | Fijar los parámetros explícitos antes de actualizar |
| B7 | **Las tablas derivadas no se invalidan nunca** (`tabla_semanal_corte`, `tabla_e9`, etc. leen el parquet si existe) | Hoy todas son de la misma fecha | Guardar la huella de los datos de origen en cada tabla y verificarla en `auditoria.py` |
| B8 | **La caché compara solo días**: una respuesta parcial por recurso, con todos los días pero menos plantas, sobrescribe | `xm_client._guardar` | Comparar también filas y suma por día |
| B9 | **La etiqueta de estrés hídrico usa `shift(-4)` por fila**, no por fecha | `alertas.eventos` | Desplazar por fecha (`shift(freq="4W")`) |

## Lo que resistió

| Verificación | Resultado |
|---|---|
| Pruebas | 59 pasan en 3.4 s |
| Reentrenar cada semana, como en operación, frente a cada 4 | MAE 53.93 frente a 54.05: el backtest es conservador, como se afirmaba |
| Pérdida alineada con el MAE en COP: Ridge ponderado por precio | 54.85 (peor) |
| Pérdida robusta: Huber | 53.83 (−0.22, IC −0.74 a 0.30, p = 0.41): no significativo |
| Variables de nivel relativas al último año | 54.24 (p = 0.77): no mejora |
| Reglas de no fuga del walk-forward, LEAR, alertas y conformal | Revisadas línea por línea: correctas |
| Emisión en seco desde la caché | Corre en 5.5 s; estado *vigilancia* por demanda estimada |

Las tres variantes exploratorias suman 3 modelos a la búsqueda del proyecto. Ninguna se recomienda.

## Prioridades

| Prioridad | Acción | Esfuerzo | Estado |
|---|---|---|---|
| 1 | Control de sesgo en `monitoreo.estado` (A1) | Bajo | **Hecho** |
| 2 | Decidir con XM la hora de emisión y, con ella, el modelo: programado si es el lunes, CMg si es el miércoles (A2) | Reunión | Pendiente |
| 3 | Control de cobertura por serie (M1) y ofertas con el rezago real en el backtest | Bajo | **Control hecho**; el backtest con rezago, pendiente |
| 4 | Snapshot reproducible y commit y tag del registro en el `.bat` (M6, B4) | Bajo | **Hecho**; el aviso por correo, pendiente |
| 5 | Calificación preliminar y firme; monitoreo con el registro (M2, M3) | Medio | Pendiente |
| 6 | ONI renovado cada mes; umbrales de alertas en `config.py` (M4, M7) | Bajo | Pendiente |
| 7 | Corrección de sesgo adaptativa registrada en paralelo (A1) | Medio | Pendiente |
| 8 | Prueba de humo en la integración continua (B5) | Bajo | **Hecho**, dentro de las pruebas de operación |

### Lo implementado

- **Sesgo (A1).** `monitoreo.desempeno_reciente` calcula el sesgo en porcentaje y su p con Newey-West. `monitoreo.estado` pasa a *vigilancia* si |sesgo| > 5 % del precio **y** p < 0.05 (`config.SESGO_MAXIMO`, `config.SESGO_P`); exigir las dos condiciones evita alarmas por sesgos pequeños o ruidosos. En la corrida en seco de hoy se activa: −52.9 COP/kWh, −7.6 %, p = 0.04.
- **Series al día (M1).** `monitoreo.cobertura_series` revisa que cada serie de las 14 variables llegue al domingo de la semana base (`config.SERIES_SEMANA_BASE`). Con 1 día faltante queda como *nota*, que se ve en el tablero sin cambiar el estado, porque el efecto medido es 0.15 %; con 2 o más días es *aviso*. Hoy marca la oferta con 1 día menos.
- **Snapshot reproducible (M6).** Cada snapshot guarda pronóstico, cotas, coeficientes, alfa, media y escala del escalador, márgenes log de las dos cotas, desempeño reciente y huellas SHA-256 de la tabla de entrenamiento y de los errores que calibran la cota. `semanal.reproducir(snapshot, precio_base)` reconstruye el pronóstico sin datos.
- **Anclaje y bitácora (M6, B4).** `correr_semanal.bat` escribe la salida en `registro/logs/AAAA-MM-DD.log`, sale con error si la emisión falla y hace commit de `registro/` y `dashboard/index.html` con el tag `registro-AAAA-MM-DD`.
- **Pruebas.** Seis nuevas en `tests/test_operacion.py`: sesgo que alarma y que no, las series en tres casos, y una emisión de punta a punta que se reconstruye desde el snapshot. Total: 65.

## Reproducir

Guiones en el directorio temporal de la sesión (no forman parte del repositorio): `medir1.py` (ofertas parciales, reentreno semanal, sesgo por año, aportes de las variables nominales, cobertura por año) y `medir2.py` (variables relativas, ponderación por precio, Huber). Las ventanas recientes salen de `results/E5E6_ancho.parquet`, `E10_parsimonia_ancho.parquet`, `E11_corte6_ancho.parquet`, `E12_ancho.parquet` y `E13_ancho.parquet`.
