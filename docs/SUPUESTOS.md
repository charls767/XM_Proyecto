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
| **Variable** | Precio de bolsa promedio por hora de la semana TIE (sábado a viernes) | Es el precio de la fórmula. La máxima transferencia se aproxima constante en las 168 horas, así que el promedio es simple. |
| **Horizonte** | De la semana s-1 a la semana s+2: tres semanas | Lo fija la regla. |
| **Emisión** | Viernes de la semana s | Día de cálculo del ASIC. |
| **Información disponible** | Semanas completas hasta s-1, y de sábado a martes de la semana s | Rezago observado de unos 3 días en la API. |
| **Referencia a superar** | La regla vigente: repetir el precio de s-1 | Es la estimación que usa hoy el ASIC. |
| **Calificación** | Con TX2 | Es la versión del ajuste 2. Las métricas usan el precio vigente; con TX1 cambian ~1 %. |
| **Asimetría** | Quedarse corto cuesta más que pasarse; se reporta una cota del 90 % | Un faltante deja exposición hasta los ajustes; un exceso solo inmoviliza recursos 2 a 3 semanas. |
| **Costo marginal programado** | No aplica a la garantía | El viernes de cálculo faltan 8 días para que empiece s+2. Se reporta aparte, para un pronóstico con la semana ya iniciada. |
| **Pronóstico a una semana** | Se mantiene como referencia (lunes a domingo, ponderado por demanda) | Es el modelo registrado desde el 5 de noviembre de 2026 y sirve de comparación. |
| **Régimen actual** | El período de riesgo de desabastecimiento (desde el 7 de septiembre de 2026, reglas hasta el 31 de mayo de 2027) se trata como excepción | Hay pocas semanas de ese régimen. |
| **Uso del resultado** | Insumo para el precio de la garantía, no el monto | El monto también depende de la máxima transferencia, el CEE y la tasa de cambio. |

## Qué falta confirmar

- Si la CREG 101 127 de 2026 cambió este artículo. El material es de 2025.
- Si para exportaciones la fórmula es la misma. El material muestra el mismo formato de cálculo para exportación, pero no la fórmula.
- Si el precio de la fórmula es el nacional o el de la liquidación TIE ("Precio Medio Total" en centUSD/kWh).
