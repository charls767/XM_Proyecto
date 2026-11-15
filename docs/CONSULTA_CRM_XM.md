# Consulta al CRM de XM: garantía TIE

Borrador listo para enviar por el CRM de XM. Son seis preguntas cerradas, ordenadas por impacto en el proyecto. Las respuestas se anotan en [PREGUNTAS_XM.md](PREGUNTAS_XM.md) y, si cambian algo, en [SUPUESTOS.md](SUPUESTOS.md).

---

**Asunto:** Consulta sobre el cálculo de la garantía semanal de las TIE (Resolución CREG 004 de 2003, art. 23)

Buen día.

Somos un equipo de la Universidad Nacional de Colombia que trabaja en un proyecto académico con XM sobre el pronóstico del precio de bolsa para la garantía de las transacciones internacionales de electricidad. Para alinear el modelo con el procedimiento vigente, agradecemos su ayuda con las siguientes preguntas.

Según el material de formación de XM (Reafirmación 2025, sesión 2), entendemos que cada viernes de la semana s el ASIC calcula el monto de la semana s+2 (sábado a viernes) como Σ MXT<sub>h</sub> × (PM<sub>s-1,h</sub> − CEE<sub>s-1</sub>), y que después lo corrige con el ajuste 1 (precios reales de los primeros cinco días) y el ajuste 2 (segunda liquidación, TX2).

1. **¿Qué precio es PM<sub>s-1,h</sub>?** ¿Es el precio de bolsa nacional horario, o el precio de la liquidación TIE ("Precio Medio Total", en centUSD/kWh)? Si es este último, ¿cómo se calcula a partir del precio de bolsa?
2. **¿Se aplica la misma fórmula a las exportaciones hacia Ecuador?** Es decir, la garantía que deposita CENACE por la energía que Colombia exporta.
3. **¿Cambió este cálculo con la Resolución CREG 101 127 de 2026?** Mientras esté vigente el período de riesgo de desabastecimiento, ¿la garantía de exportación usa el máximo entre el precio de bolsa TIE, el precio de la planta más cara con arranque y parada, y el costo marginal del importador?
4. **¿Cómo se define MXT<sub>h</sub> en la práctica?** ¿Es constante en las 168 horas o varía por hora? ¿Dónde se puede consultar su historial?
5. **¿Qué tasa de cambio se usa y en qué fecha?** Por ejemplo, la TRM del día de cálculo o la del vencimiento.
6. **¿Hay series públicas (SiMEM o API de XM) con las transferencias horarias TIE y los montos de garantía calculados?** Las usaríamos para medir el error en el monto y no solo en el precio.

Agradecemos de antemano su respuesta.

Universidad Nacional de Colombia, caso XM–UNAL

---

## Por qué importa cada pregunta

| Pregunta | Qué cambia en el proyecto si la respuesta es distinta a lo supuesto |
|---|---|
| 1 | El objetivo del modelo: hoy se pronostica el precio de bolsa nacional en COP, promedio horario simple |
| 2 | Si el modelo sirve para el caso de exportación, que es el de interés |
| 3 | La utilidad del registro mientras rija la norma (hasta el 31 de mayo de 2027) |
| 4 | La ponderación horaria: hoy se supone MXT constante. Con solo horas de punta, la mejora del modelo bajaría de 14.8 % a 12.5 % (auditoría del 15 de noviembre por partes) |
| 5 | El error en USD: el modelo no cubre la variación de la tasa de cambio en tres semanas |
| 6 | Pasar de medir el error en precio a medirlo en monto de garantía |
