# Auditoría metodológica y de MLOps

**Fecha:** 5 de noviembre de 2026 · **Alcance:** código, datos, evaluación y operación del modelo en `ridge14-conformal104-v1` · **Reproducir:** `python src/auditoria.py` → `results/auditoria/`

## Encargo

> Actúa como auditor principal de machine learning y MLOps en entornos críticos. Busca fallas ocultas en el modelo, con evidencia medida y no solo lectura de código.
>
> - **Problema:** regresión de serie temporal semanal.
> - **Objetivo:** anticipar el precio de bolsa ponderado por demanda del MEM colombiano, con una cota al 90 %, como insumo para la garantía de los intercambios con Ecuador.
> - **Librerías:** scikit-learn, pandas, statsmodels, LightGBM, XGBoost, pydataxm.
> - **Pilares:** fuga de información (incluidas latencia de publicación y revisiones de datos), validación temporal y sesgo de búsqueda, métricas y subgrupos, MLOps y reproducibilidad, explicabilidad y estrés.

## Veredicto

**Prototipo sólido y honesto en su mecánica, pero con menos evidencia de la que sus cifras aparentan.** No se encontró fuga de información grave. La cota cumple lo que promete. Pero no hay un periodo de prueba limpio, la mejora de 2025–2026 frente al ingenuo no es significativa, y el modelo aporta poco justo cuando el embalse está bajo. **No debe usarse para fijar garantías sin validación prospectiva y sin la regla de XM.**

---

## Diagnóstico de riesgo

### Crítico

**1. No hay periodo de prueba limpio, y la búsqueda infla los resultados.**
Se compararon 67 modelos en las mismas semanas; 2022–2024 se usó para decidir una y otra vez, y 2025–2026 también se vio. Corrigiendo por esa búsqueda con el reality check de White:

| Pregunta | p |
|---|---|
| ¿El mejor de los 67 modelos supera a Ridge 14 en 2022–2024? | **0.52** |
| ¿El mejor de E11 (10 modelos) lo supera? | 0.25 |
| Ensamble Ridge 14 + LEAR, prueba aislada (Diebold-Mariano robusto) | 0.008 |
| Ensamble, con Bonferroni dentro de E11 / en todo el proyecto | 0.08 / 0.52 |

**Esto corrige una afirmación anterior del proyecto:** decir que el ensamble "mejora con significancia" solo es cierto si se ignora que se probaron muchos modelos y que se agregó tras ver los resultados. Hay una mejora prometedora, no una demostrada. El 18,7 % de mejora también es optimista, porque Ridge 14 se eligió mirando esas mismas semanas.

**2. La antelación real es negativa.**
Por el rezago de publicación de unos 3 días, la semana base queda completa el miércoles, cuando la semana objetivo ya lleva 2 días corriendo. La cifra principal (MAE 54) supone conocer la semana completa, pero no es un pronóstico "con una semana de antelación", que es lo que pide la propuesta. Con emisión el lunes y datos hasta el viernes, el error real es **61–63 COP/kWh**.

**3. En 2025–2026 la ventaja frente al ingenuo no es significativa.**

| | Mejora de MAE | p (HAC) |
|---|---|---|
| Ridge 14, semana completa | 5.5 COP/kWh | 0.18 |
| Ridge 14 + programado, hasta el viernes | 2.1 COP/kWh | 0.68 |

El periodo más reciente es el que mejor predice el futuro, y en él no se puede afirmar que el modelo le gane a repetir el precio.

### Alto

**4. El promedio esconde los regímenes que más importan** (`results/auditoria/subgrupos.csv`, 2018–2026):

| Régimen | Semanas | Mejora frente al ingenuo | Sesgo (COP/kWh) | Cobertura |
|---|---|---|---|---|
| **Embalse bajo 45 %** | 44 | **3.5 %** | −17 | 91 % |
| Embalse entre 60 y 75 % | 157 | 25 % | −12 | 87 % |
| ENOS neutral | 185 | 10 % | −19 | 91 % |
| El Niño | 131 | 20 % | −17 | 88 % |
| La Niña | 144 | 33 % | −1 | 91 % |
| **Semanas en que el precio sube** | 225 | **9 %** | **−58** | **81 %** |
| Semanas en que el precio baja | 235 | 28 % | +31 | 99 % |

El 47 % del error absoluto está en el 10 % peor de las semanas. Para una garantía esto es lo central: el modelo protege menos cuando el precio sube, que es cuando quedarse corto duele.

**5. Sesgo sistemático a quedarse corto: −12.5 COP/kWh (p = 0.002).**
Tiene una causa matemática: Ridge ajusta el logaritmo, y exp(ŷ) estima la mediana, no la media. El factor de Duan, calculado solo con errores pasados, lleva el sesgo a +1.1, a cambio de subir el MAE de 54.05 a 54.45. **No se aplicó:** cambia el modelo oficial y su conveniencia depende de la regla de la garantía.

**6. Los datos históricos no son los que existían en su momento.**
El backtest usa los valores de hoy, ya revisados. Se midió el efecto solo para el precio (TX1: ~1 % de MAE). Hidrología, ofertas y disponibilidad no tienen versiones anteriores. Además, la clasificación térmica usa el listado de plantas de hoy (fuera del listado: 2.6 % de la generación en 2010, 0 % en 2026), y `AporEnerMediHist` salta cerca de 30 % a finales de 2022, algo que hay que aclarar con XM. Las versiones reales solo existen desde el 5 de noviembre de 2026, en `registro/snapshots/`.

### Medio

| # | Hallazgo | Evidencia | Estado |
|---|---|---|---|
| 7 | **Fuga en el escenario hasta el viernes:** se entrenaba con una semana cuyo objetivo aún no se conocía | MAE de 62.79 a 62.85, y de 61.24 a 61.36; efecto pequeño | Corregido |
| 8 | **Diebold-Mariano con varianza simple**, aunque las pérdidas se agrupan | Estadístico del ensamble en selección: de −3.04 a −2.70 | Corregido |
| 9 | **Caché frágil:** un mes vacío por una caída de la API quedaba congelado, y las revisiones de XM dejaban de actualizarse a los 7 días | Sin casos hoy; riesgo latente | Corregido |
| 10 | **Registro inmutable solo de palabra:** un CSV editable | Por diseño | Corregido: huella SHA-256 encadenada |
| 11 | **Sin integración continua ni trazabilidad de corridas** | Por diseño | Corregido |
| 12 | **Alertas con muestras mínimas:** "4 de 4 inicios" tiene IC 95 % de 51 % a 100 %, y los umbrales se fijaron viendo toda la historia | Wilson | Documentado |
| 13 | **LEAR con AIC sobre objetivos solapados:** el AIC supone errores independientes, lo que puede dejar variables de más | Sin medir | Pendiente |

### Bajo

- La operación reentrena cada semana y el backtest cada 4. Es conservador, no optimista.
- La cota se calibra con errores del backtest, no de emisiones reales, hasta que el registro acumule historia.
- SARIMAX vuelve a filtrar toda la historia cada semana (~25 min). Es lento, pero no incorrecto.

## Lo que sí resistió la auditoría

| Pilar | Verificación | Resultado |
|---|---|---|
| Fuga en transformaciones | Escalado y selección dentro de cada ajuste; pruebas que alteran el futuro | Sin fuga |
| Validación temporal | Walk-forward, sin mezclar futuro y pasado | Correcta |
| Cota | Kupiec p = 0.88; fallas independientes p = 0.76; cobertura 90.2 % (IC 87–93 %) | **Pasa**; las fallas no se agrupan |
| Hiperparámetros de Ridge | Alfa interior (8–19, límites 0.01–1000). LOO frente a CV temporal: 54.05 y 54.88 | No es un problema |
| Métricas de clasificación | F2 y PR-AUC en lugar de exactitud; recall en inicios | Adecuadas |
| Explicabilidad | Descomposición exacta en Ridge; SHAP en alertas | Adecuada |
| Dirección del cambio | Acierta 73 % de las semanas | Señal real |
| Semillas | Fijadas en los modelos y el bootstrap | Reproducible |
| Datos | Sin meses cerrados vacíos; la caché coincide con la API hoy | Correcto |

---

## Recomendaciones técnicas

| Prioridad | Acción | Cómo |
|---|---|---|
| 1 | **Tratar 2018–2026 como desarrollo.** La única prueba válida es el registro | Regla ya escrita: 26 semanas calificadas |
| 2 | **Definir con XM la hora de decisión** y reportar la métrica de ese escenario como cifra principal | Si es antes del lunes, Ridge 14 + programado |
| 3 | **Decidir el ajuste de sesgo** según el costo de quedarse corto | Factor de Duan: ŷ · media(exp(residuos pasados)) |
| 4 | **Modelar el costo asimétrico** cuando exista la regla | Pérdida pinball al cuantil que dé la razón de costos, en lugar de 90 % fijo |
| 5 | **Rediseñar para embalse bajo** con más episodios | Probar ponderar esas semanas; aumentar datos con 2015–16 |
| 6 | **Probar BIC o CV temporal por bloques** en LEAR | `LassoLarsIC(criterion="bic")` o `LassoCV` con `TimeSeriesSplit` |
| 7 | **Comprometer el registro en git cada semana** para anclar sus huellas | `git add registro && git commit` después de emitir |

**No se recomienda:** MLflow o Weights & Biases (una persona con corridas semanales; `results/corridas.jsonl` basta), ni redes profundas: el problema es de evidencia e información, no de capacidad del modelo.

---

## Código corregido

Las correcciones están integradas en el proyecto, con pruebas:

| Archivo | Cambio | Por qué |
|---|---|---|
| `src/backtesting.py` | `embargo` en el walk-forward | Con corte antes del domingo, la fila anterior no tiene objetivo conocido |
| `src/calibration.py` | `rezago` en `conformal` | Lo mismo para los errores que calibran la cota |
| `src/evaluation.py` | `dm_hac`, `reality_check`, `pruebas_cobertura`, `subgrupos` | Significancia robusta, corrección por búsqueda y régimen |
| `src/xm_client.py` | Refresco de 90 días; mes vacío no vale como caché; listado renovado | Revisiones de XM y caídas de la API |
| `src/semanal.py` | Huella encadenada; se niega a emitir si el registro fue alterado | Registro verificable |
| `src/monitoreo.py` | Aviso de embalse bajo | Ahí el modelo casi no aporta |
| `src/trazabilidad.py` | `results/corridas.jsonl`: commit, huella de datos, versiones | Saber con qué salió cada resultado |
| `src/auditoria.py` | Reproduce este informe | Auditoría regenerable |
| `.github/workflows/pruebas.yml` | Pruebas en cada push | Evitar regresiones |

**Una lección del propio proceso:** implementé primero la prueba SPA de Hansen, y su prueba unitaria falló. Una simulación con 150 repeticiones mostró que rechazaba 11 % al nivel de 5 %, así que la descarté y usé el reality check, que rechaza 6 %.

Para los detalles de los experimentos, ver la [bitácora](EXPERIMENTOS.md).
