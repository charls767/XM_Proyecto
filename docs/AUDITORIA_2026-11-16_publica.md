# Auditoría con información pública (16 de noviembre de 2026)

**Alcance:** el proyecto desde el commit `58ea5b9` (E26), ya integrado en `main` con el PR #13 (merge `167e9c6`). Solo se usan el código, la API pública de XM, documentos suministrados y resoluciones CREG. **No se contactó a XM.** Las correcciones están en la rama `auditoria-publica`.

Convenciones: **H** hecho comprobado · **S** supuesto del proyecto · **Hip** hipótesis · **L** limitación · **P** pregunta abierta.

## 1. Estructura de objetivos

| Categoría | Variable | Unidad | Fuente | Estado |
|---|---|---|---|---|
| Principal | Precio de las compras TIE en bolsa | COP/kWh | `CompBolsaTIEMoneda` / `CompBolsaTIEEner` | Reconstruido; E26; no se puede emitir desde el 1-ago-2026 |
| Referencia | Precio de bolsa nacional, promedio horario | COP/kWh | `PrecBolsNaci` | Reconstruido; E16/E24 |
| Complementario | Precio promedio realizado de exportación | centUSD/kWh | `ExportMonedaUSD` / `ExpoEner` | Reconstruido; E19; equivalencia con la garantía: Hip |

**(H)** Ninguno se marca como oficial (`config.OBJETIVOS`, `oficial = False`). `tests/test_objetivos.py` revisa el código, la app, el informe PDF y siete documentos para que no presenten el precio realizado de exportación como el precio oficial de la garantía.

## 2. E26 reproducido

- **Objetivo:** Σ `CompBolsaTIEMoneda` / Σ `CompBolsaTIEEner` de la semana s+2 (sábado a viernes), en COP/kWh. Es una variable pública reconstruida, y el modelo es una aproximación estadística a ella.
- **Muestra:** 113 semanas objetivo, del 20-oct-2018 al 17-ene-2026, con al menos 1 GWh comprado en s-1 y en s+2. Evaluación: backtest simulado con ventana expansiva y reentrenamiento cada 4 semanas.
- **Horizonte:** 21 días entre la semana base y la objetivo en todas las filas; emisión el viernes; semana base que empieza en sábado (H).
- **Reproducción:** vuelto a correr en una copia limpia de `58ea5b9`; diferencia 0 en `E26_resumen.csv` y `E26_ancho.parquet` (H).
- **Resultado:** el elegido erra 142.2 frente a 159.6 COP/kWh de la regla (−10.9 %, p = 0.044). **La conclusión de evidencia débil se mantiene:** 113 semanas, 9 variantes y un p que no resiste una corrección por búsqueda.

## 3. Precio de exportación

**(H)** Para la semana base del 18 al 24 de enero de 2025, `ExportMonedaUSD` / `ExpoEner` = 24.325 centUSD/kWh. Con el CEE oficial (88.758 COP/kWh ≈ 2.06 centUSD/kWh) queda 22.27, frente a los 22.75 del ejemplo de XM.

**(Hip)** Que este precio sea el de la garantía de exportación no está confirmado. Se presenta como precio promedio realizado.

## 4. Variables

[VARIABLES_XM.md](VARIABLES_XM.md) documenta, para `ExpoMoneda`, `ExpoEner`, `ExportMonedaUSD`, `CompBolsaTIE*`, `VentBolsaTIE*`, `PrecBolsNaci`, `PPPrecBolsNaci`, `CEE` y `SnTIE*`: unidad, frecuencia, agregación, descripción oficial y uso en el proyecto. Viene del catálogo `ListadoMetricas`, consultado el 16-nov-2026.

## 5. Disponibilidad de datos

- **(H)** La API devuelve 0 filas de `CompBolsaTIEEner` y `CompBolsaTIEMoneda` del 1-ago al 16-nov-2026. De febrero a julio de 2026 las compras fueron de 1 GWh o menos al mes.
- **(H)** Exportaciones (`ExpoEner`, caché al 12-nov-2026):
  - de 6 a 50 GWh por semana del 1-ago al 11-sep-2026;
  - desde el 12-sep, **mínimas o intermitentes**: de 0.14 a 1.08 GWh por semana, con 6.87 GWh la semana del 31-oct y 5.28 GWh del 7 al 12-nov.
- **(H, corregido)** Sin compras TIE en la semana base, la emisión no pronostica el objetivo principal y lo anota como **nota**. Sin exportaciones pasa lo mismo con el objetivo complementario: antes quedaba como motivo y ponía la emisión en vigilancia cada semana desde septiembre.

## 6. Problemas encontrados y correcciones

| # | Dónde | Problema | Corrección |
|---|---|---|---|
| 1 | `semanal_tie.emitir` | La ausencia de exportaciones era un motivo de vigilancia: la emisión quedaba en vigilancia por falta de datos | Ahora es una nota informativa; test agregado |
| 2 | README, app (Inicio y glosario) | Presentaban la regla del material de XM como la que "usa hoy" XM | Atribuida al material de formación de 2025, con la vigencia como limitación |
| 3 | SUPUESTOS | La regla se titulaba como vigente; la fila de referencia decía que el ASIC la usa hoy; afirmaba que los datos "ya indican" que el precio de la fórmula es el de exportación | Vigencia como limitación; equivalencia como hipótesis, con la cifra de 22.27 frente a 22.75 |
| 4 | PREGUNTAS_XM | Decía que el precio realizado "cuadra" con el ejemplo de XM | Corregido con el CEE oficial: hipótesis no confirmada |
| 5 | CONSULTA_CRM_XM | Borrador "listo para enviar"; decía que "cuadra"; llamaba objetivo al precio de exportación | Reencabezado como preguntas abiertas que no se envían; cifras y objetivo corregidos |
| 6 | EXPERIMENTOS (índice y título de E19) | "el precio de exportación, el que entra en la garantía" | Retitulado como precio realizado, con una nota de hipótesis |
| 7 | README (tabla del núcleo) | "Desde el 7-sep-2026 las exportaciones son mínimas" | Precisado con las cifras semanales |
| 8 | `tests/test_objetivos.py` | La guardia no revisaba EXPERIMENTOS, PREGUNTAS_XM ni CONSULTA_CRM_XM | Ampliada a esos documentos y a dos frases más ("cuadra con…") |

## 7. Pruebas

- **Dependencias:** `pyarrow`, `scipy`, `streamlit`, `plotly` y `scikit-learn` están declarados en `requirements.txt` con versión fija. `pyarrow`, `scipy`, `streamlit` y `plotly` también en `app/requirements.txt`.
- **Suite:** 119 pasan y 1 se omite. La omitida es `test_operacion.py:115`, porque la última emisión a una semana fue de respaldo.
- **Sin fuga de información:**
  - E16 y E26 entrenan solo con filas cuyo objetivo terminó antes del viernes de emisión (tests de `semanal_tie` y de la tabla TIE).
  - La cota usa errores con rezago 3.
  - La regla viernes de s → s+2 → base s-1 se prueba con el ejemplo de XM (`semanas("2025-02-14")`).
- **Guardia:** el test detecta una frase afirmativa como "el precio realizado de exportación es el precio de la garantía".

## 8. Limitaciones públicas y preguntas abiertas

Sin respuesta de XM y sin intentar obtenerla:
- **(L/P)** La fórmula vigente de la garantía y si la CREG 101 127 de 2026 la cambió durante el período de riesgo.
- **(P)** La relación exacta entre PONE, el precio de bolsa TIE, las compras TIE en bolsa y la garantía.
- **(P)** La composición de `ExpoMoneda`. En enero de 2025 excede en 324.83 COP/kWh al precio de compras TIE.
- **(P)** El mecanismo de exportación desde agosto de 2026, cuando hay exportaciones sin compras TIE en bolsa. Podrían ser contratos bilaterales (Hip).
- **(L)** El MXT no tiene serie pública; el monto de `garantia.py` es solo una aproximación.
- **(L)** La unidad de `ExportMonedaUSD` en el catálogo ("COP") no coincide con los datos (USD).
- **(L)** Ningún modelo está validado para fijar garantías. La evidencia es un backtest simulado; el registro TIE empieza el 20-nov-2026.

## 9. Recomendación sobre el PR #13

El PR #13 ya está integrado en `main` y su integración continua pasó. Su contenido es reproducible y coherente con la información pública. Las correcciones de esta auditoría son de texto, de una nota de disponibilidad y de la guardia, sin cambios en los modelos ni en sus cifras. Se recomienda integrarlas con un PR nuevo desde `auditoria-publica`.
