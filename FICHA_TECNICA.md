# Ficha técnica: pronóstico semanal del precio de bolsa (PAE-XM)

**Versión:** `ridge14-conformal104-v1` · **Responsable:** Carlos Acevedo (caso XM–UNAL) · **Actualizada:** noviembre de 2026

## Para qué sirve

Estima el precio de bolsa promedio de la **semana siguiente**, ponderado por demanda, y una **cota superior** que el precio real no debería superar en 9 de cada 10 semanas. Es un insumo para estimar la garantía de los intercambios de energía con Ecuador.

**No sirve para:** pronosticar más de una semana adelante, pronosticar precios horarios, calcular la garantía completa (falta la regla de XM) ni anticipar saltos bruscos de precio.

## Qué hace

| Pieza | Cómo funciona |
|---|---|
| Pronóstico | Regresión Ridge sobre el cambio del precio (log P<sub>s+1</sub>/P<sub>s</sub>) con 14 variables: precio y su dinámica dentro de la semana, embalse, aportes, precios de oferta térmicos y no térmicos, y época del año. |
| Cota 90 % | El pronóstico más un margen igual al error que solo se superó en el 10 % de las últimas 104 semanas (calibración conformal). |
| Explicación | Como el modelo es lineal, el cambio pronosticado se reparte exactamente entre las variables. |
| Alertas | Tres regresiones logísticas: precio alto, salto ≥ 25 % y embalse bajo 45 % en 4 semanas. |
| Controles | Antes de emitir: datos completos y al día, valores en rango físico, variables dentro de lo visto en la historia, y desempeño de las últimas 26 semanas. |

## Datos

API pública de XM (vía `pydataxm`): precio de bolsa, demanda comercial, aportes, embalse, capacidad efectiva, precios de oferta y generación por recurso, de 2010 a hoy. Rezagos de publicación observados en la API: unos 3 días para el precio y las ofertas, 1 día para la hidrología. La demanda de los días más recientes puede venir incompleta; esos días se estiman con la generación, el tablero lo avisa y la semana no se califica hasta que esté completa.

## Qué tan bien funciona (evaluación simulada 2018–2026)

Cada semana se pronosticó solo con lo que se sabía antes, reentrenando cada 4 semanas.

| Métrica | Valor | Referencia |
|---|---|---|
| Error medio | 54.1 COP/kWh | Repetir el precio anterior: 66.6 (el modelo mejora 18.7 %) |
| Error típico | 15 % del precio | |
| Sesgo | −12.5 COP/kWh | Tiende a quedarse corto |
| Cobertura de la cota | 90.2 % | Meta 90 % |
| Exceso de la cota | 37 % | Cuánto supera la cota al precio cuando cubre |
| Cobertura en las semanas de mayor cambio | 70 % | Meta 85 %: **no se cumple** |

Por periodo, la mejora frente al ingenuo fue de 23 % en 2018–2021, 21 % en 2022–2024 (años de estrés) y 7–8 % en 2025–2026. En los tres episodios de estrés evaluados (El Niño 2015–16, sequía 2023–24 y octubre de 2024) erró menos que el ingenuo, pero se quedó corto.

## Cuándo no confiar en él

- **Semanas de salto.** Los cambios bruscos de precio no se anticipan. La cota cubre solo 7 de cada 10 de esas semanas.
- **Estado "vigilancia" o "respaldo"** en el tablero. Hay datos atrasados, variables fuera de lo visto o el modelo no le gana al ingenuo recientemente.
- **Regímenes nuevos.** Cambios regulatorios o de mercado que no estén en la historia de 2010–2026.
- **Información incompleta.** Si al emitir solo se conoce la semana base hasta el viernes, el error sube a ~61–63 COP/kWh. En ese escenario conviene el modelo con el despacho programado del lunes (experimento E9).

## Limitaciones conocidas

- La evaluación 2018–2026 es simulada y 2025–2026 se usó al diseñar el modelo. La evidencia independiente es el registro de pronósticos (`registro/pronosticos.csv`), que empezó el 5 de noviembre de 2026.
- No se probaron fuentes externas a XM y NOAA, como pronósticos de aportes o mantenimientos programados.
- Las métricas usan el precio vigente; con la versión TX1 son ~1 % peores.
- Un ensamble de Ridge, LightGBM y SARIMAX erró ~2 % menos en 2018–2026, sin significancia en el periodo de selección. Se prefirió Ridge por simplicidad y explicación exacta (E5/E6).
- Un ensamble de Ridge y LEAR diario erró ~3 % menos, con significancia en 2022–2024 si se conoce la semana completa. Se añadió tras ver resultados, así que se registra en paralelo cada semana. Con 26 semanas calificadas, reemplaza al oficial si erra menos y la cobertura de su cota no baja de 85 % (E11).

## Pendiente con XM

1. Hora de emisión y rezago real de publicación.
2. A qué hora se publica el despacho programado.
3. Regla de la garantía y costo de quedarse corto frente a pasarse.
4. Estimación que usan hoy los agentes, para compararla.

## Mantenimiento

- **Cada lunes:** `correr_semanal.bat`.
- **Revisar:** si el estado sale en vigilancia dos semanas seguidas, o si la cobertura de las últimas 26 semanas baja de 80 %.
- **Cambiar de modelo:** solo con evidencia del registro y una nueva versión en `src/config.py`, sin borrar las filas registradas con la anterior.
