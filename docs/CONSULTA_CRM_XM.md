# Consulta al CRM de XM: garantía TIE

Borrador listo para enviar por el CRM de XM. Son seis preguntas cerradas, ordenadas por impacto en el proyecto. Las respuestas se anotan en [PREGUNTAS_XM.md](PREGUNTAS_XM.md) y, si cambian algo, en [SUPUESTOS.md](SUPUESTOS.md).

---

**Asunto:** Consulta sobre el cálculo de la garantía semanal de las TIE (Resolución CREG 004 de 2003, art. 23)

Buen día.

Somos un equipo de la Universidad Nacional de Colombia que trabaja en un proyecto académico con XM sobre el pronóstico del precio de bolsa para la garantía de las transacciones internacionales de electricidad. Para alinear el modelo con el procedimiento vigente, agradecemos su ayuda con las siguientes preguntas.

Según el material de formación de XM (Reafirmación 2025, sesión 2), entendemos que cada viernes de la semana s el ASIC calcula el monto de la semana s+2 (sábado a viernes) como Σ MXT<sub>h</sub> × (PM<sub>s-1,h</sub> − CEE<sub>s-1</sub>), y que después lo corrige con el ajuste 1 (precios reales de los primeros cinco días) y el ajuste 2 (segunda liquidación, TX2).

1. **¿Qué precio es PM<sub>s-1,h</sub> en la exportación, y qué contiene `ExpoMoneda`?**
   - Con las series públicas de la API, lo cobrado por exportar (`ExportMonedaUSD`) entre la energía exportada (`ExpoEner`) da 24.32 centUSD/kWh para la semana del 18 al 24 de enero de 2025. Menos el CEE, cuadra con los 22.75 que muestra su ejemplo de exportación.
   - El inventario de métricas describe `ExpoMoneda` solo como "Transferencias de Energía desde Colombia hacia otros países", en COP.
   - ¿Qué componentes tiene además del valor en bolsa TIE (`VentBolsaTIEMoneda`)?
   - ¿Por qué ese exceso pasó de unos 50 COP/kWh hasta 2018 a 374 en 2024 y 1,361 en 2026? ¿Corresponde a los costos de las plantas térmicas usadas para exportar bajo las resoluciones del MME, liquidados con las CREG 026 y 155 de 2014?
   - Evidencia del proyecto (E21): en las 52 semanas con regla especial, el precio de exportación tiene una correlación de 0.75 con la oferta de las térmicas que generaron, y de 0.42 con el precio de bolsa.
   - El inventario indica unidades "COP" para `ExportMonedaUSD`, pero sus valores parecen estar en USD. ¿Cuál es la unidad correcta?
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
| 1 | Desde E19 el objetivo es el precio de exportación (`ExportMonedaUSD`/`ExpoEner`). Conocer sus componentes permitiría modelar cada uno, en vez de tratarlo como una caja negra con saltos de régimen |
| 2 | Si el modelo sirve para el caso de exportación, que es el de interés |
| 3 | La utilidad del registro mientras rija la norma (hasta el 31 de mayo de 2027) |
| 4 | La ponderación horaria: hoy se supone MXT constante. Con solo horas de punta, la mejora del modelo bajaría de 14.8 % a 12.5 % (auditoría del 15 de noviembre por partes) |
| 5 | El error en USD: el modelo no cubre la variación de la tasa de cambio en tres semanas |
| 6 | Pasar de medir el error en precio a medirlo en monto de garantía |
