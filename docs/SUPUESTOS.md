# Supuestos de operación

XM respondió que qué se pronostica y para qué lo define el proyecto. Después, el material de formación de XM sobre garantías (sesión 2 de Reafirmación 2025, "Garantías y mecanismos de cubrimiento del mercado") mostró la regla de la garantía TIE de la Resolución CREG 004 de 2003, artículo 23. Los supuestos siguen esa regla. Que siga vigente, y que se aplique igual a la exportación, no está confirmado: es una **limitación** del proyecto. Donde la regla no alcanza, se elige lo más cercano a cómo funciona hoy el mercado.

## La regla (según el material de formación de XM de 2025; vigencia no confirmada)

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
| **Objetivos** | Tres, todos reconstruidos a partir de series oficiales (ver `config.OBJETIVOS` y [VARIABLES_XM.md](VARIABLES_XM.md)). **Principal:** precio de las compras TIE en bolsa (`CompBolsaTIEMoneda` / `CompBolsaTIEEner`, COP/kWh, E26), que hoy no se puede emitir porque XM no publica compras TIE desde el 1-ago-2026. **Referencia:** precio de bolsa nacional promedio horario (`PrecBolsNaci`, COP/kWh, E16). **Complementario:** precio promedio realizado de exportación (`ExportMonedaUSD` / `ExpoEner`, centUSD/kWh, E19) | XM no publica el precio oficial de la garantía. El precio realizado de exportación se parece a lo que muestra el ejemplo de XM, pero no coincide: 24.33 centUSD/kWh menos el CEE oficial (2.06) da 22.27, frente a 22.75 (semana base del 18 al 24 de enero de 2025). Por eso no se presenta como el precio de la garantía. Las compras TIE en bolsa son el componente económico de las obligaciones TIE en la bolsa colombiana |
| **Horizonte** | De la semana s-1 a la semana s+2: tres semanas | Lo fija la regla. |
| **Emisión** | Viernes de la semana s | Día de cálculo del ASIC. |
| **Información disponible** | Semanas completas hasta s-1; el precio de sábado a martes de la semana s; el costo marginal del despacho programado de miércoles a viernes de s (E24); para el candidato en paralelo, también la hidrología de sábado a jueves de s | Rezago observado en la API: unos 3 días para el precio y 1 para la hidrología. El costo marginal programado de cada día se publica la víspera, tarde en la noche. Por eso se emite el viernes después de las 20:00. Las exportaciones (energía y moneda) se publican con el mismo rezago que el precio: el 15 de noviembre de 2026 las tres series llegaban al 12 de noviembre, igual que el precio. |
| **Referencia a superar** | La regla del material de XM: repetir el precio de s-1 | Es la estimación que describe el material de formación de XM. Que el ASIC la use hoy es un supuesto. |
| **Calificación** | Con TX2 | Es la versión del ajuste 2. Las métricas usan el precio vigente; con TX1 cambian ~1 %. |
| **Asimetría** | Quedarse corto cuesta más que pasarse; se reporta una cota del 90 % | Un faltante deja exposición hasta los ajustes; un exceso solo inmoviliza recursos 2 a 3 semanas. Según E22, la cota del 90 % conviene si quedarse corto cuesta unas 10 veces más que inmovilizar; con 3 a 5 veces conviene la del 80 %. El costo relativo lo debe fijar XM. |
| **Costo marginal programado** | Se usa el de miércoles a viernes de la semana s (E24), no el de la semana objetivo | El de cada día se publica la víspera, así que el viernes de cálculo ya está el de la semana s. El de s+2 todavía no existe: faltan 8 días para que empiece. |
| **Pronóstico a una semana** | Se mantiene como referencia (lunes a domingo, ponderado por demanda) | Fue el primer planteamiento; se registró el 5 y el 12 de noviembre de 2026 y ya no emite. Sus filas se siguen calificando. |
| **Régimen actual** | El período de riesgo de desabastecimiento (desde el 7 de septiembre de 2026, reglas hasta el 31 de mayo de 2027) se trata como excepción | Hay pocas semanas de ese régimen. |
| **Uso del resultado** | Pronósticos de precios relacionados con la garantía; no el monto oficial | El monto también depende de la máxima transferencia (sin serie pública), el CEE (serie oficial mensual) y la tasa de cambio. `src/garantia.py` solo hace una aproximación con supuestos. |

## Reglas especiales de exportación (régimen regulatorio)

El Ministerio de Minas y Energía ha cambiado varias veces con qué plantas se exporta. Esas medidas se publican en el Diario Oficial antes de aplicarse, así que se conocen el viernes de cálculo. `dp.REGIMENES_EXPORTACION` las marca:

| Periodo (viernes de cálculo) | Regla | Fuente |
|---|---|---|
| 16-oct-2023 a 31-jul-2024 | Exportar solo con plantas térmicas | Res. MME [40619 de 2023](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_minminas_40619_2023.htm), 40718 de 2023, [40115 de 2024](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_minminas_40115_2024.htm) |
| 17-ago-2024 a 15-nov-2024 | Alternativas fijadas por circular (térmicas) y suspensión | Res. MME [40330 de 2024](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_minminas_40330_2024.htm) y 40410 de 2024 |
| Desde el 16-nov-2024 | Cualquier planta (régimen normal) | Res. MME [40494 de 2024](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_minminas_40494_2024.htm) |
| Desde el 31-jul-2026 (por confirmar) | Marco permanente de medidas; exportación con térmicas; período de riesgo | Memoria justificativa MME de junio de 2026 y CREG 101 127 de 2026 |

En esas semanas el precio de exportación es en promedio el doble del nacional (diferencial log 0.70 frente a −0.13). Como variable del modelo no mejoró el error en selección. Se usa para calibrar la cota por separado (E20). El periodo de 2024 se cubre sin el hueco del 1 al 16 de agosto de 2024; la fecha de inicio de 2026 es una aproximación.

## Riesgo conocido: el período de riesgo de desabastecimiento

Mientras rija la CREG 101 127 de 2026 (hasta el 31 de mayo de 2027), los cargos de exportación consideran el **máximo** entre:
- el precio de bolsa TIE;
- el precio de la planta más cara con arranque y parada;
- el costo marginal del importador.

Ver la tabla inicial de [PREGUNTAS_XM.md](PREGUNTAS_XM.md).

En ese régimen, el precio que XM use para la garantía de exportación puede diferir del precio de bolsa (referencia) y del precio realizado de exportación (complementario) que pronostica este proyecto. Además, XM no publica compras ni ventas TIE en bolsa desde el 1 de agosto de 2026, aunque hubo exportaciones (96.11 GWh en agosto): pueden estar ocurriendo por otro mecanismo, por ejemplo contratos bilaterales (hipótesis). El backtest de 2018 a agosto de 2026 no se ve afectado. Lo que depende de esta respuesta es la utilidad del registro mientras rija la norma; además, desde el 7 de septiembre de 2026 las exportaciones son mínimas o intermitentes: según `ExpoEner`, 1.08 GWh la semana del 10 de octubre, 6.87 GWh la del 31 de octubre y 5.28 GWh del 7 al 12 de noviembre, frente a 46 y 50 GWh en las dos últimas semanas de agosto.

## Qué falta confirmar

- Si la CREG 101 127 de 2026 cambió este artículo, y qué precio usa XM para la garantía mientras rija. El material es de 2025.
- Si para exportaciones la fórmula es la misma. El material muestra el mismo formato de cálculo para exportación, pero no la fórmula.
- Qué componentes tiene lo cobrado por exportar (`ExpoMoneda`) además del precio de bolsa TIE. Desde 2023 suele estar muy por encima de él, y en el período de riesgo llega a ser varias veces mayor (por ejemplo, 2,978 frente a 389 COP/kWh la semana del 31 de octubre de 2026). Que el precio de la fórmula sea el realizado de exportación es una **hipótesis** (E19) que los datos públicos no confirman: con el CEE oficial da 22.27 centUSD/kWh frente a 22.75 del ejemplo de XM (ver [VARIABLES_XM.md](VARIABLES_XM.md)).
- Solo hay precio de exportación en las semanas en que se exportó: si en la semana s-1 no hubo exportaciones, la emisión no pronostica el precio de exportación y lo anota.
