# Quinta auditoría: precio de exportación y emisión TIE

**Fecha:** 15 de noviembre de 2026, 21:30 · **Alcance:** `main` en 46e531b (PR #4 a #6): E17 a E22, el precio de exportación en `data_pipeline.tabla_expo()`, `semanal_tie.pronosticar_expo()`, la cota por régimen y la página de exportación de la app. · **Complementa:** [AUDITORIA_2026-11-15.md](AUDITORIA_2026-11-15.md) y [AUDITORIA_2026-11-15_por_partes.md](AUDITORIA_2026-11-15_por_partes.md), cuyos hallazgos no se repiten.

## Veredicto

**El análisis del precio de exportación se reproduce y no usa información futura.** Hay dos fallas en la emisión que harían que la primera emisión real (viernes 20 de noviembre) pronostique el precio de exportación con datos viejos o incompletos, sin avisar. Hay que corregirlas antes del viernes.

La evidencia de que el modelo de exportación supera a la regla es débil: 117 semanas, un modelo elegido entre 20 configuraciones, y p = 0.08 en todo el periodo.

Cifras medidas sobre la caché local y la API de XM consultada hoy.

## Estado de los hallazgos (actualizado el mismo día)

| # | Estado | Qué se hizo |
|---|---|---|
| A1 | **Corregido** | `semanal_tie.emitir()` descarga las cinco series de exportación (`dp.SERIES_EXPO_TODAS`) cuando actualiza datos, y anota su última fecha en `datos_hasta` |
| A2 | **Corregido** | `_semanal_expo()` recibe la última fecha publicada. Un periodo que pasa de ella no tiene precio ni energía; un día sin fila antes de ella sigue contando como sin exportación. Se aplica a la semana base, a sábado-martes y a las ventas TIE. Test nuevo. La emisión anota si falta el precio de exportación por datos no publicados o porque no se exportó |
| M1 | **Corregido** | SUPUESTOS, PREGUNTAS_XM y la app dicen ahora que desde el 7 de septiembre las exportaciones son mínimas o intermitentes, con las cifras |
| M2 | **Corregido** | La página de exportación y la ficha lo presentan como candidato, con el p, el número de semanas y el ejemplo del 13 de noviembre |
| M3 | Abierto | Medir un umbral de 5 GWh o ponderar por energía |
| M4 | Abierto | Pasar a `src/` los guiones de E18, E20, E21 y E22 |
| B1, B2 | Abiertos | Sin cambios |
| B3 (nuevo) | **Corregido** | La ficha registraba la versión `expo-huber-mitad-regla-conformal104-v1`; la del código es `...-regimen-v1` |

Con las correcciones, E19 da exactamente los mismos resultados (diferencia 0 en sus 15 configuraciones) y pasan 83 tests.

---

## Hallazgos

### Alto

**A1. La emisión no actualiza las series de exportación.** `semanal_tie.emitir()` descarga solo `semanal.SERIES_MODELO`: precio, demanda, hidrología, ofertas, generación y combustible. `dp.tabla_expo()` lee `expo_energia`, `expo_usd`, `expo_cop` y `tie_venta_*` de la caché sin consultar la API. Hoy esa caché está al día solo porque otra sesión la descargó a mano.
- **Consecuencia:** el viernes 20, sin una descarga manual, el precio de exportación de la semana base (7 a 13 de noviembre) saldría de la caché del 15 de noviembre, que llega hasta el 12.
- **Corrección:** descargar esas cinco series en la emisión cuando `actualizar=True`, y anotar su última fecha en `datos_hasta`.

**A2. Una semana de exportación incompleta se calcula como si estuviera completa.** `_semanal_expo()` rellena con 0 los días que faltan y divide lo cobrado entre la energía de los días que sí hay. No distingue un día sin exportaciones de un día que aún no se publicó.
- **Prueba:** con la caché actual (hasta el 12 de noviembre), la semana del 7 al 13 de noviembre da 80.26 centUSD/kWh con 5.3 GWh, en vez de no dar precio.
- **Consecuencia:** combinado con A1, el viernes 20 se registraría un precio base calculado con 6 de 7 días, sin aviso.
- **Corrección:** exigir que la serie tenga los 7 días publicados (con o sin energía) para dar precio a la semana. Lo mismo para los 4 días de sábado a martes.

### Medio

**M1. Los documentos dicen que no hay exportaciones desde el 7 de septiembre de 2026, pero los datos muestran que sí.**

| Semana TIE | Energía exportada | Precio de exportación |
|---|---|---|
| 10 al 16 de octubre | 1.08 GWh | 49.99 centUSD/kWh |
| 31 de octubre al 6 de noviembre | 6.87 GWh | 92.44 centUSD/kWh |
| 7 al 12 de noviembre (parcial) | 5.28 GWh | 80.26 centUSD/kWh |

Lo dicen [PREGUNTAS_XM.md:11](PREGUNTAS_XM.md), [SUPUESTOS.md:53](SUPUESTOS.md) y la página Episodios de estrés de la app. Lo correcto sería "exportaciones mínimas o intermitentes desde el 7 de septiembre".

**M2. La evidencia del modelo de exportación es débil.**
- Solo hay 117 semanas evaluables en 2018–2026: las que tienen al menos 1 GWh exportado en s-1 y en s+2.
- El modelo ("Mitad Huber + mitad regla") se eligió por el MAE del periodo de selección entre 20 configuraciones.
- Frente a la regla: p = 0.08 en todo el periodo y p = 0.056 en la prueba final. Ninguno es significativo al 5 %, y no hay corrección por búsqueda.
- Hoy el modelo se aleja mucho de la regla: en la prueba en seco del 13 de noviembre da 65.8 centUSD/kWh frente a 92.4 de la regla (−29 %). Lo hace en el período de riesgo, del que hay muy pocas semanas de entrenamiento.
- **Recomendación:** presentarlo como candidato, no como resultado, y que la app lo diga así. La regla de las 26 semanas del registro es la que debe decidir.

**M3. Las semanas con poca energía exportada dan precios muy ruidosos.** El umbral es 1 GWh por semana: 78 de las 457 semanas con precio tienen entre 1 y 5 GWh. Con tan poca energía, unas pocas horas mueven el precio (por ejemplo, 49.99 con 1.08 GWh). Conviene medir si un umbral de 5 GWh, o ponderar por energía, cambia la comparación con la regla.

**M4. Cuatro experimentos no se pueden reproducir desde el repositorio.** E18, parte de E20, E21 y E22 están marcados "(scratch)" en [EXPERIMENTOS.md](EXPERIMENTOS.md): sus guiones no están en `src/`. Sus conclusiones (por ejemplo, que la cota del 80 % conviene si quedarse corto cuesta de 3 a 5 veces más) no se pueden volver a calcular.

### Bajo

**B1.** El índice de [EXPERIMENTOS.md](EXPERIMENTOS.md) lista E22, E21, E20, E19 en orden inverso.

**B2.** El `main` local está atrasado frente a `origin/main`: `git pull` en `main` antes de trabajar ahí.

---

## Verificado sin problemas

| Revisión | Resultado |
|---|---|
| Tests | 82 pasan y 1 se omite, incluidas las 8 páginas de la app |
| Reproducción de E19 | Los mismos MAE, semanas y cobertura en las 15 configuraciones |
| Rezago de las series de exportación | La API tiene `ExpoEner`, `ExportMonedaUSD` y `ExpoMoneda` hasta el 12 de noviembre, igual que el precio. **El supuesto pendiente de SUPUESTOS.md queda comprobado** |
| Información futura en E19 | Mismo esquema que E16: embargo de 2 semanas y cota con rezago 3. Las variables de exportación usan solo s-1, s-2 y sábado a martes de s |
| Cota por régimen | `conformal_regimen` con `rezago=1` por defecto: no cambia E7. Con `rezago=3` solo usa errores ya calificados |
| Emisión en seco (13-nov) | Funciona: precio nacional 397.5 COP/kWh, candidato 391.7, exportación 65.8 centUSD/kWh (regla 92.4) |
| Registros | El registro a una semana está íntegro; el TIE sigue vacío hasta el viernes 20 |

## Qué corregir antes del viernes 20

1. A1 y A2: descargar las series de exportación en la emisión y exigir semanas completas.
2. M1: corregir la frase sobre las exportaciones.
3. M2: presentar el precio de exportación como candidato en la app y la ficha.
