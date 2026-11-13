# Supuestos de operación

XM respondió que qué se pronostica y para qué lo define el proyecto, y que lo normativo se consulta por su CRM. Mientras llega esa respuesta, el proyecto trabaja con estos supuestos. Cada uno se eligió por ser el más cercano a cómo funciona hoy el mercado, no el más conveniente para el modelo.

| Tema | Supuesto | Por qué |
|---|---|---|
| **Variable** | Precio de bolsa nacional promedio de la semana siguiente, ponderado por demanda | Es la referencia pública del mercado y entra en los cargos de exportación. Ponderar por demanda refleja el costo medio de la energía transada. |
| **Usuario** | Quien estima la garantía semanal de los intercambios con Ecuador: el ASIC o el agente exportador | Es el caso planteado en la propuesta del proyecto. |
| **Horizonte** | Una semana, de lunes a domingo | Ciclo semanal de las garantías. |
| **Emisión** | Miércoles, con la semana base completa | El precio y las ofertas se publican con unos 3 días de rezago en la API. |
| **Escenarios alternos** | Emisión el lunes con la semana base hasta el viernes (E9), o con la semana objetivo ya iniciada y su costo marginal programado (E12) | Si la garantía se fija antes o después, cambia el modelo conveniente. Se reportan los tres. |
| **Asimetría** | Quedarse corto cuesta más que pasarse; se reporta una cota del 90 % | Una garantía insuficiente expone al mercado; una excesiva solo inmoviliza recursos. |
| **Calificación** | Con el precio vigente; es provisional hasta la liquidación mensual (TXR/TXF) | XM indicó que TX1 y TX2 son preliminares y que las versiones finales salen cada mes. Con TX1 las métricas cambian ~1 %. |
| **Datos faltantes** | Si faltan las ofertas, se registra el ingenuo (estado *respaldo*) y se informa aparte la variante sin ofertas | El registro no se reescribe después; la variante sirve de referencia. |
| **Régimen actual** | El período de riesgo de desabastecimiento (desde el 7 de septiembre de 2026, con reglas vigentes hasta el 31 de mayo de 2027) se trata como excepción | Hay pocas semanas de ese régimen. El modelo se evalúa en 2018–2026 y se muestra aparte cómo le fue desde septiembre. |
| **Uso del resultado** | Insumo para estimar la garantía, no la garantía misma | Falta la fórmula oficial (cantidad × precio × factor). |

## Qué cambiaría con la respuesta de XM

- Si el precio de la garantía no es el de bolsa nacional, cambia la variable objetivo.
- Si la garantía se fija con la semana objetivo ya iniciada, el candidato con costo marginal pasa a ser el principal.
- Si hoy no se calcula garantía porque no hay exportaciones, el proyecto se presenta como pronóstico del precio de bolsa, con la garantía como aplicación.
