# Supuestos de operación

XM respondió que qué se pronostica y para qué lo define el proyecto. Después, el material de formación de XM sobre garantías (sesión 2 de Reafirmación 2025, "Garantías y mecanismos de cubrimiento del mercado") mostró la regla de la garantía TIE de la Resolución CREG 004 de 2003, artículo 23. Los supuestos siguen esa regla. Donde la regla no alcanza, se elige lo más cercano a cómo funciona hoy el mercado.

## La regla (según el material de XM)

- **Semana TIE:** de sábado a viernes.
- **Cálculo:** cada viernes de la semana s, el ASIC proyecta el monto de la semana **s+2**.
- **Proyección:** MSG = Σ (168 horas) MXT<sub>h</sub> × (PM<sub>s-1,h</sub> − CEE<sub>s-1</sub>). MXT es la máxima transferencia horaria del enlace y PM el precio horario de bolsa de la semana **s-1**.
- **Precio de escasez:** si el precio supera el de escasez, el monto se divide en dos partes (MSG con el precio de escasez y MSG<sub>OEF</sub> con la diferencia). La suma sigue dependiendo del precio de bolsa.
- **Ajuste 1:** con las transferencias reales y los precios reales de los primeros 5 días de s+2.
- **Ajuste 2:** el viernes de s+3, con los precios de la segunda liquidación (**TX2**).
- **Moneda:** el monto va en USD con la tasa de cambio, y el país importador lo consigna. Para exportaciones a Ecuador, deposita CENACE.

## Supuestos del proyecto

| Tema | Supuesto | Por qué |
|---|---|---|
| **Variable** | **Precio de exportación** de la semana TIE (sábado a viernes), en centUSD/kWh: `ExportMonedaUSD` / `ExpoEner` (E19). Como complemento, el precio de bolsa promedio por hora (E16) | El "Precio Medio Total" de la garantía es lo cobrado por exportar entre la energía exportada. Para la semana base del 18 al 24 de enero de 2025 da 24.32 centUSD/kWh, y XM proyectó 22.75 después de restar el CEE. El precio de bolsa (nacional o TIE) queda 30 % por debajo y su cambio a tres semanas solo tiene una correlación de 0.27 con el de exportación. El CEE es conocido al calcular, así que se pronostica el precio total. |
| **Horizonte** | De la semana s-1 a la semana s+2: tres semanas | Lo fija la regla. |
| **Emisión** | Viernes de la semana s | Día de cálculo del ASIC. |
| **Información disponible** | Semanas completas hasta s-1; el precio de sábado a martes de la semana s; para el candidato en paralelo, también la hidrología de sábado a jueves de s | Rezago observado en la API: unos 3 días para el precio y 1 para la hidrología. Por eso se emite el viernes después de las 20:00. Se supone que las exportaciones (energía y moneda) se publican con el mismo rezago que el precio. No se pudo comprobar, porque desde septiembre de 2026 casi no hay exportaciones. |
| **Referencia a superar** | La regla vigente: repetir el precio de s-1 | Es la estimación que usa hoy el ASIC. |
| **Calificación** | Con TX2 | Es la versión del ajuste 2. Las métricas usan el precio vigente; con TX1 cambian ~1 %. |
| **Asimetría** | Quedarse corto cuesta más que pasarse; se reporta una cota del 90 % | Un faltante deja exposición hasta los ajustes; un exceso solo inmoviliza recursos 2 a 3 semanas. |
| **Costo marginal programado** | No aplica a la garantía | El viernes de cálculo faltan 8 días para que empiece s+2. Se reporta aparte, para un pronóstico con la semana ya iniciada. |
| **Pronóstico a una semana** | Se mantiene como referencia (lunes a domingo, ponderado por demanda) | Fue el primer planteamiento; se registró el 5 y el 12 de noviembre de 2026 y ya no emite. Sus filas se siguen calificando. |
| **Régimen actual** | El período de riesgo de desabastecimiento (desde el 7 de septiembre de 2026, reglas hasta el 31 de mayo de 2027) se trata como excepción | Hay pocas semanas de ese régimen. |
| **Uso del resultado** | Insumo para el precio de la garantía, no el monto | El monto también depende de la máxima transferencia, el CEE y la tasa de cambio. |

## Riesgo conocido: el período de riesgo de desabastecimiento

Mientras rija la CREG 101 127 de 2026 (hasta el 31 de mayo de 2027), los cargos de exportación consideran el **máximo** entre:
- el precio de bolsa TIE;
- el precio de la planta más cara con arranque y parada;
- el costo marginal del importador.

Ver la tabla inicial de [PREGUNTAS_XM.md](PREGUNTAS_XM.md).

En ese régimen, el precio que entra en la garantía de exportación puede no ser el precio de bolsa que pronostica este proyecto. El backtest de 2018 a agosto de 2026 no se ve afectado. Lo que depende de esta respuesta es la utilidad del registro mientras rija la norma; además, desde el 7 de septiembre de 2026 no hay exportaciones.

## Qué falta confirmar

- Si la CREG 101 127 de 2026 cambió este artículo, y qué precio entra en la garantía mientras rija. El material es de 2025.
- Si para exportaciones la fórmula es la misma. El material muestra el mismo formato de cálculo para exportación, pero no la fórmula.
- Qué componentes tiene lo cobrado por exportar (`ExpoMoneda`) además del precio de bolsa TIE. Desde 2023 suele estar muy por encima de él, y en el período de riesgo llega a ser varias veces mayor (por ejemplo, 2,978 frente a 389 COP/kWh la semana del 31 de octubre de 2026). Los datos públicos ya indican que el precio de la fórmula es el de exportación y no el nacional (E19); falta la confirmación formal de XM.
- Solo hay precio de exportación en las semanas en que se exportó: si en la semana s-1 no hubo exportaciones, la emisión no pronostica el precio de exportación y lo anota.
