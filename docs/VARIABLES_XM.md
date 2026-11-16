# Variables de XM y objetivos del proyecto

**Fecha:** 16 de noviembre de 2026 · **Fuente:** catálogo oficial de la API de XM (`ListadoMetricas`, 193 métricas, consultado el 16-nov-2026) y consultas directas a la API.

Convenciones: **H** hecho comprobado · **XM** variable oficial de XM · **S** supuesto del proyecto · **R** variable reconstruida · **Hip** hipótesis · **P** pregunta pendiente para XM.

## 1. Los tres objetivos

XM no publica una métrica con el precio de la garantía TIE ni con su monto (H: no hay ninguna en el catálogo). Por eso los objetivos del proyecto son variables reconstruidas (R) a partir de series oficiales (XM). Están definidos en `src/config.py` (`OBJETIVOS`) y `tests/test_objetivos.py` impide que el código, la app o la documentación principal presenten el precio realizado de exportación como el oficial.

Regla temporal común: semana TIE de sábado a viernes; cálculo el viernes de la semana s; objetivo la semana s+2; referencia (regla de XM) la semana s-1.

| Categoría | Variable (columna) | Unidad | Fuente | Frecuencia | Tipo | Estado de validación |
|---|---|---|---|---|---|---|
| **Principal** | Precio de las compras TIE en bolsa (`precio_compra_tie_cop_kwh`) | COP/kWh | `CompBolsaTIEMoneda` / `CompBolsaTIEEner` | Horaria → semanal | R | Componente económico de las obligaciones TIE en la bolsa colombiana; su relación exacta con la garantía es P. Backtest simulado E26 (113 semanas): −10.9 % frente a la regla, p = 0.044, evidencia débil. Casi sin compras de febrero a julio de 2026 y sin datos desde el 1-ago-2026 |
| **Referencia** | Precio de bolsa nacional, promedio horario simple (`precio`) | COP/kWh | `PrecBolsNaci` (alternativa oficial diaria: `PPPrecBolsNaci`) | Horaria → semanal | R | Backtest simulado E16/E24 (461 semanas); registro desde el 20-nov-2026 |
| **Complementario** | Precio promedio realizado de exportación (`precio_expo`; en COP, `precio_expo_cop`) | centUSD/kWh | `ExportMonedaUSD` / `ExpoEner` (en COP: `ExpoMoneda` / `ExpoEner`) | Horaria → semanal | R | Backtest simulado E19 (117 semanas con exportación), no significativo al 5 %; registro desde el 20-nov-2026 |

## 2. Catálogo oficial frente al uso del proyecto

| Id (XM) | Nombre oficial | Unidad (catálogo) | Frecuencia | Agregación | Descripción oficial (catálogo) | Uso en el código | Relación con el objetivo de garantía |
|---|---|---|---|---|---|---|---|
| `ExpoEner` | Exportaciones Energía | kWh | Horaria | Sistema, Enlace | "Transferencias de Energia desde Colombia hacia otros paises" | `xm_client` (`expo_energia`); denominador del objetivo complementario; energía real en E22 | Energía transferida (XM). No es el MXT de la fórmula |
| `ExpoMoneda` | Exportaciones Moneda | COP | Horaria | Sistema, Enlace | La misma frase | `expo_cop`; `precio_expo_cop`, `spread` y la tasa implícita `trm` | Lo liquidado en COP por exportar (XM). Su composición no está documentada (P) |
| `ExportMonedaUSD` | Exportaciones Moneda USD por Sistema | **"COP" en el catálogo; los datos están en USD** (H) | Horaria | Sistema | La misma frase | `expo_usd`; numerador del objetivo complementario | Precio realizado (R), no el de la garantía |
| `CompBolsaTIEEner` | Compras Bolsa TIE Energía | kWh | Horaria | Sistema, Agente | "Energía comprada en la Bolsa de Energía para atender la demanda TIE" | `tie_compra_energia`; denominador del objetivo principal | Componente de las obligaciones TIE en bolsa (XM) |
| `CompBolsaTIEMoneda` | Compras Bolsa TIE Moneda | COP | Horaria | Sistema, Agente | La misma frase | `tie_compra_cop`; numerador del objetivo principal | Ídem |
| `VentBolsaTIEEner` | Ventas Bolsa TIE Energía | kWh | Horaria | Sistema, Agente | **La misma descripción que la de compras** | `tie_venta_energia`; se descarga, ya no se usa en la tabla | **Idéntica a `CompBolsaTIEEner`** en las 82,437 horas comunes de 2010 a julio de 2026 (diferencia máxima 0.01 kWh) (H) |
| `VentBolsaTIEMoneda` | Ventas Bolsa TIE Moneda | COP | Horaria | Sistema, Agente | La misma de compras | `tie_venta_cop`; ídem | Idéntica a `CompBolsaTIEMoneda` (diferencia máxima 1.14 COP en una hora) (H) |
| `PrecBolsNaci` | Precio Bolsa Nacional por Sistema | COP/kWh | Horaria | Sistema | "Precio de oferta de la última planta flexible para atender la demanda comercial nacional, más delta de incremento…" | `precio`; objetivo de referencia y variables de los modelos | Referencia del mercado (XM); no es el precio de la garantía de exportación (Hip, E19) |
| `PPPrecBolsNaci` | Precio Bolsa Nacional Ponderado por Sistema | COP/kWh | **Diaria** | Sistema | "Precio de transacción en bolsa para el mercado nacional, calculado con base en el Costo Marginal (MPO) Nacional y el Delta…" | No se usa | Alternativa oficial al promedio horario simple del proyecto |
| `CEE` | CEE por Sistema | COP/kWh | **Mensual** | Sistema | "Costo Equivalente de Energía del Cargo por Capacidad… señal de referencia para los agentes generadores" | `xm_client.cee_mensual()`; columnas `cee_cop_kwh`, `cee_centusd_kwh` y `precio_expo_neto_cee` | Término que la fórmula resta (XM). El proyecto antes suponía que no tenía serie pública: **sí la tiene** (H) |
| `SnTIEMerito` / `SnTIEFueraMerito` | Saldo Neto TIE Mérito / Fuera Mérito | COP | Horaria | Sistema | "Valores netos deficitarios o superavitarios resultantes del ajuste final de TIE… Resolución 004 de 2003" | No se usan | Saldos del ajuste final, no la garantía. Sin datos en enero de 2025; las sumas consultadas salieron vacías (H) |

## 3. Semana de verificación: base del 18 al 24 de enero de 2025

Es la semana base del ejemplo de exportación de XM (cálculo del viernes 31 de enero para la semana del 8 al 14 de febrero). Valores de la API (H):

| Serie o cociente | Valor |
|---|---|
| `ExpoEner` | 64.33 GWh |
| `ExpoMoneda` / `ExpoEner` | 1,048.40 COP/kWh |
| `ExportMonedaUSD` / `ExpoEner` | **24.325 centUSD/kWh** |
| Tasa implícita `ExpoMoneda` / `ExportMonedaUSD` | 4,310.0 COP/USD |
| `CompBolsaTIEMoneda` / `CompBolsaTIEEner` | 713.39 COP/kWh = 16.55 centUSD/kWh |
| `CompBolsaTIEEner` / `ExpoEner` | 1.0143 |
| `PrecBolsNaci`, promedio horario | 678.74 COP/kWh = 15.75 centUSD/kWh |
| `PPPrecBolsNaci`, diario | 644.11 a 738.17 COP/kWh |
| `CEE`, enero de 2025 | 88.758 COP/kWh = **2.06 centUSD/kWh** |
| (`ExpoMoneda` − `CompBolsaTIEMoneda`) / `ExpoEner` | 324.83 COP/kWh por encima del precio de bolsa TIE |

## 4. ¿Es `ExpoMoneda` / `ExpoEner` el precio de la garantía?

**No se puede considerar así.** Es un **precio promedio realizado de exportación** (R):

1. **(H)** El catálogo no tiene ninguna métrica de garantía. Las de exportación solo dicen "transferencias de energía".
2. **(H)** El ejemplo de XM proyectó 22.75 centUSD/kWh ("Precio Medio Total − CEE"). Con la serie realizada y el CEE oficial queda 24.325 − 2.06 = **22.27**, unos 2 % menos. El CEE implícito que suponía el proyecto (1.57 centUSD/kWh) no coincide con el oficial. En cambio, el CEE del ejemplo de importación de XM (2.04 en febrero de 2025) sí coincide con la serie oficial (84.81 COP/kWh), lo que sugiere que XM convierte el CEE oficial a USD.
   - **(Hip)** La diferencia de unos 2 % puede venir de que XM usó la liquidación preliminar (TX1) en la fecha de cálculo, o una tasa de cambio distinta.
3. **(H)** Incluye más que el precio de bolsa TIE: 324.83 COP/kWh adicionales en esa semana. La composición es P.
4. **(H)** Desde el 1-ago-2026 no hay compras ni ventas TIE en bolsa, pero sí exportaciones (96.11 GWh en agosto; 13.82 GWh del 15-oct al 14-nov). **(Hip)** Podrían estar ocurriendo por otro mecanismo (por ejemplo, contratos bilaterales), en el que la garantía de la CREG 004 de 2003 podría no aplicar.

**Consecuencia para el proyecto.** El precio realizado de exportación pasa a ser el objetivo **complementario**. El **principal** es el componente económico de las obligaciones TIE en bolsa (compras TIE), modelado en E26. No se reemplazó ninguna variable de los modelos: solo se agregaron columnas (`precio_compra_tie_cop_kwh`, `cee_cop_kwh`, `cee_centusd_kwh`, `precio_expo_neto_cee`) y la columna `precio_bolsa_tie` se sustituyó por la de compras, que es equivalente.

## 5. Preguntas para XM

Además de las de [CONSULTA_CRM_XM.md](CONSULTA_CRM_XM.md):
- ¿Cuál es la unidad correcta de `ExportMonedaUSD`? El catálogo dice COP; los datos están en USD.
- ¿Por qué las compras y las ventas en bolsa TIE son idénticas, y por qué no hay datos desde el 1-ago-2026?
- ¿Con qué versión de liquidación (TX1, TX2…) y qué tasa de cambio se calcula el precio de la garantía de exportación?
- ¿Qué series publican `SnTIEMerito` y `SnTIEFueraMerito`, y por qué vienen vacías?
