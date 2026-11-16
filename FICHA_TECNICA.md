# Ficha técnica: precio para la garantía TIE (PAE-XM)

**Versiones registradas (desde el 20-nov-2026):** precio de exportación `expo-huber-mitad-regla-conformal104-regimen-v1` (candidato, ver abajo) y precio de bolsa `tie-ridge11-parcial-duan-conformal104-v1` · **Responsable:** Carlos Acevedo (caso XM–UNAL) · **Actualizada:** 15 de noviembre de 2026

## Para qué sirve

Estima, el viernes de la semana s, el precio de la semana TIE s+2 (sábado a viernes) que entra en la garantía de las transacciones internacionales con Ecuador (CREG 004 de 2003, art. 23). Lo compara siempre con la regla de XM, que repite el de la semana s-1. Incluye una **cota superior** que el precio real no debería superar en 9 de cada 10 semanas.

**Precio de exportación (el de la garantía, E19).** Es lo cobrado por exportar (USD) entre la energía exportada, menos el CEE; cuadra con el ejemplo de XM.

| Precio de exportación (117 semanas con exportación, 2018–2026) | |
|---|---|
| Regla de XM | 5.31 centUSD/kWh de error medio |
| Modelo (mitad Huber, mitad regla) | 4.83 (−9 %, p = 0.08); prueba final 2025–26: 6.05 frente a 7.03 (−13.9 %, p = 0.06) |
| Limitación | Pocas semanas y saltos de régimen: la evidencia es débil. Sin exportaciones en s-1, o si la semana s-1 aún no está publicada completa, no hay pronóstico |
| Estado | **Candidato, no resultado:** se eligió entre ~30 variantes y no es significativo al 5 %. Se registra junto a la regla y lo decide el registro |

**Precio de bolsa (base del mercado, E16).**

| Precio de bolsa (461 semanas, 2018–2026, E16) | |
|---|---|
| Regla de XM | 115.3 COP/kWh de error medio |
| Modelo registrado | 98.3 COP/kWh, 14.8 % menos (p < 0.001); sesgo −16 |
| Último año | 120 frente a 127, sin significancia (p = 0.40) |
| Cota 90 % | Cubre 90.5 %; cuando cubre, excede al precio real en 85 % |

**Modelo:** Ridge sobre log(P<sub>s+2</sub>/P<sub>s-1</sub>) con 11 variables de s-1 (sin ofertas, que a tres semanas no aportan) más el precio de sábado a martes de s, con corrección de sesgo de Duan. Respaldo sin los días de s; vigilancia si en 52 semanas erra más que la regla, la cota cubre menos de 80 % o el sesgo es significativo. Detalle en [docs/SUPUESTOS.md](docs/SUPUESTOS.md) y [E16](docs/EXPERIMENTOS.md).

**No sirve para:** calcular el monto completo (también dependen la máxima transferencia, el CEE y la tasa de cambio), pronosticar precios horarios ni anticipar saltos bruscos.

## El pronóstico a una semana (complemento)

El resto de esta ficha describe el primer planteamiento: el precio de la **semana siguiente** (lunes a domingo, ponderado por demanda), versión `ridge14-conformal104-v1`, registrado del 5 al 12 de noviembre de 2026. Se conserva como comparación.

## Qué hace

| Pieza | Cómo funciona |
|---|---|
| Pronóstico | Regresión Ridge sobre el cambio del precio (log P<sub>s+1</sub>/P<sub>s</sub>) con 14 variables: precio y su dinámica dentro de la semana, embalse, aportes, precios de oferta térmicos y no térmicos, y época del año. |
| Cota 90 % | El pronóstico más un margen igual al error que solo se superó en el 10 % de las últimas 104 semanas (calibración conformal). |
| Explicación | Como el modelo es lineal, el cambio pronosticado se reparte exactamente entre las variables. |
| Alertas | Tres regresiones logísticas: precio alto, salto ≥ 25 % y embalse bajo 45 % en 4 semanas. |
| Controles | Antes de emitir: datos completos y al día, valores en rango físico, variables dentro de lo visto en la historia, y desempeño de las últimas 26 semanas. |

## Datos

API pública de XM (vía `pydataxm`): precio de bolsa, demanda comercial, aportes, embalse, capacidad efectiva, precios de oferta y generación por recurso, de 2010 a hoy. Rezagos de publicación observados en la API: unos 3 días para el precio y las ofertas, 1 día para la hidrología. La demanda de los días más recientes puede venir incompleta; esos días se estiman con la generación y la semana no se califica hasta que esté completa.

## Qué tan bien funciona (evaluación simulada 2018–2026)

Cada semana se pronosticó solo con lo que se sabía antes, reentrenando cada 4 semanas.

| Métrica | Valor | Referencia |
|---|---|---|
| Error medio, semana base completa | 54.1 COP/kWh | Repetir el precio anterior: 66.6 (el modelo mejora 18.7 %) |
| Error medio, datos hasta el viernes | 61–63 COP/kWh | Repetir el precio anterior: 73.2 |
| Error típico | 15 % del precio | |
| Sesgo | −12.5 COP/kWh | Se queda corto, de forma significativa (p = 0.002) |
| Cobertura de la cota | 90.2 % | Meta 90 % |
| Exceso de la cota | 37 % | Cuánto supera la cota al precio cuando cubre |
| Cobertura en las semanas de mayor cambio | 70 % | Meta 85 %: **no se cumple** |

Por periodo, la mejora frente al ingenuo fue de 23 % en 2018–2021, 21 % en 2022–2024 (años de estrés) y 7–8 % en 2025–2026. En los tres episodios de estrés evaluados (El Niño 2015–16, sequía 2023–24 y octubre de 2024) erró menos que el ingenuo, pero se quedó corto. **En 2025–2026 la ventaja frente al ingenuo no es significativa (p = 0.18).**

Por régimen: con el embalse bajo 45 % no hay evidencia de que supere al ingenuo (mejora de 3.5 %, IC 95 % de −16 % a +21 %, 44 semanas), y en las semanas en que el precio sube se queda corto 58 COP/kWh, menos que los 69 del ingenuo, y la cota cubre 81 %. La [auditoría](docs/AUDITORIA.md) tiene el detalle.

## Cuándo no confiar en él

- **Semanas de salto.** Los cambios bruscos de precio no se anticipan. La cota cubre solo 7 de cada 10 de esas semanas.
- **Estado "vigilancia" o "respaldo"** en la emisión. Hay datos atrasados, variables fuera de lo visto o el modelo no le gana al ingenuo recientemente.
- **Regímenes nuevos.** Cambios regulatorios o de mercado que no estén en la historia de 2010–2026.
- **Información incompleta.** Si al emitir solo se conoce la semana base hasta el viernes, el error sube a ~61–63 COP/kWh. En ese escenario conviene el modelo con el despacho programado del lunes (experimento E9).

## Limitaciones conocidas

- La evaluación 2018–2026 es simulada y se usó para elegir entre 67 modelos, así que sus cifras son optimistas. La evidencia independiente es el registro de pronósticos: `registro/pronosticos.csv` para este modelo (5 y 12 de noviembre de 2026) y `registro/pronosticos_tie.csv` para la garantía TIE, desde el 20 de noviembre de 2026.
- No se probaron fuentes externas a XM y NOAA, como pronósticos de aportes o mantenimientos programados.
- Las métricas usan el precio vigente; con la versión TX1 son ~1 % peores.
- Un ensamble de Ridge, LightGBM y SARIMAX erró ~2 % menos en 2018–2026, sin significancia en el periodo de selección. Se prefirió Ridge por simplicidad y explicación exacta (E5/E6).
- Un ensamble de Ridge y LEAR diario erró ~3 % menos con la semana completa, pero al corregir por los modelos probados no es significativo (p = 0.52). Se registra en paralelo cada semana. Con 26 semanas calificadas, reemplaza al oficial si erra menos y la cobertura de su cota no baja de 85 % (E11).
- Desde el 10 de noviembre de 2026 se registra en paralelo un segundo candidato: Ridge 14 más el costo marginal programado del lunes y el martes de la semana objetivo. Erró 39.3 frente a 53.9 COP/kWh en la evaluación simulada (E12), con significancia tras corregir por búsqueda. Sigue la misma regla y, además, solo puede adoptarse si XM confirma que la garantía se fija con la semana objetivo ya iniciada.

## Pendiente con XM

1. Hora de emisión y rezago real de publicación.
2. A qué hora se publica el despacho programado.
3. Regla de la garantía y costo de quedarse corto frente a pasarse.
4. Estimación que usan hoy los agentes, para compararla.

## Mantenimiento

- **Cada viernes después de las 20:00** (día de cálculo de la garantía TIE): `correr_semanal.bat`. Desde el 15 de noviembre de 2026 emite el pronóstico de la semana s+2 para la garantía TIE ([docs/SUPUESTOS.md](docs/SUPUESTOS.md), E16). El registro a una semana se conserva y se sigue calificando.
- **Revisar:** si el estado sale en vigilancia dos semanas seguidas, si la cobertura de las últimas 26 semanas baja de 80 % o si el sesgo de esas semanas pasa de 5 % del precio con significancia (hoy: −7.6 %, p = 0.04).
- **Anclaje:** el `.bat` hace commit y tag `registro-AAAA-MM-DD` de cada emisión; revisar la bitácora en `registro/logs/` si falla.
- **Cambiar de modelo:** solo con evidencia del registro y una nueva versión en `src/config.py`, sin borrar las filas registradas con la anterior.
