# XM_Proyecto · Precio para la garantía TIE

**En palabras simples:** Colombia le vende electricidad a Ecuador. Antes de cada semana, Ecuador deja un depósito (la *garantía*) para asegurar el pago. Para calcularlo, XM tiene que adivinar el precio de una semana que empieza dentro de 8 días, y hoy supone que será igual al de hace tres semanas. Este proyecto intenta adivinarlo mejor, y lo compara siempre con esa regla.

Modelo para anticipar el precio que entra en la **garantía de las transacciones internacionales de electricidad (TIE)** con Ecuador, con una **cota superior de riesgo** (caso XM–UNAL).

La regla de la garantía (Resolución CREG 004 de 2003, art. 23) fija el problema: el **viernes** de la semana s, el ASIC calcula el monto de la semana **s+2** (de sábado a viernes) con los precios de la semana **s-1**. Esa regla es, en la práctica, un pronóstico ingenuo a tres semanas.

**El precio de esa fórmula, para la exportación, no es el precio de bolsa.** Es lo que se cobra por exportar (USD) entre la energía exportada, menos el CEE. Con datos públicos de XM cuadra con su ejemplo: 24.32 centUSD/kWh menos el CEE ≈ 22.75, para la semana base del 18 al 24 de enero de 2025 (E19). El detalle está en [docs/SUPUESTOS.md](docs/SUPUESTOS.md).

| En una mirada (semanas objetivo 2018–2026) | |
|---|---|
| **Precio de exportación** (el de la garantía, E19) | Regla de XM 5.31 centUSD/kWh; modelo elegido 4.83 (**−9 %**, p = 0.08); en la prueba final 2025–26, −13.9 % (p = 0.06). Solo 117 semanas con exportación: la evidencia es débil |
| Precio de bolsa (base del mercado, E16 y E24) | Regla 115 COP/kWh; modelo registrado 94 (**−19 %**, p < 0.001), con el costo marginal programado de miércoles a viernes de la semana en curso; en el último año 113 frente a 127, sin significancia (p = 0.18) |
| Cotas al 90 % | Cubren alrededor de 90 %, pero son anchas |
| Pronóstico a una semana (complemento) | 54 COP/kWh, 19 % menos que repetir el precio anterior |

**La app** ([app/streamlit_app.py](app/streamlit_app.py)) está escrita para cualquier lector, con un glosario. Tiene 6 páginas:

| Página | Qué responde |
|---|---|
| Inicio | ¿Qué problema se resuelve y qué tan bien? |
| Precio de exportación | ¿Qué tan bien se adivina el precio que usa el depósito? |
| Precio de bolsa | ¿Y el precio general del mercado? ¿Cómo le va en las crisis? ¿Ve venir los saltos? |
| Pronóstico de esta semana | ¿Qué se registró el último viernes y por qué? |
| Extra: la semana siguiente | El primer planteamiento, con 13 modelos comparados |
| Cómo funciona | Los pasos, el glosario y los supuestos |

> Prototipo académico; no es una publicación oficial de XM. La evaluación es simulada y se usó para diseñar el modelo, así que sus cifras son optimistas. La evidencia independiente es el [registro TIE](registro/), que empieza el 20 de noviembre de 2026. Ver las auditorías: [5 de noviembre](docs/AUDITORIA.md), [10 de noviembre](docs/AUDITORIA_2026-11-10.md), 15 de noviembre ([general](docs/AUDITORIA_2026-11-15.md), [por partes](docs/AUDITORIA_2026-11-15_por_partes.md) y [exportación](docs/AUDITORIA_2026-11-15_exportacion.md)) y [16 de noviembre, app](docs/AUDITORIA_2026-11-16_app.md). **No usarlo para fijar garantías sin esa validación.**

---

## El núcleo: dos pronósticos cada viernes

Cada viernes de la semana s se pronostica la semana s+2 (sábado a viernes). Los dos pronósticos se comparan con la regla de XM, que repite el valor de la semana s-1.

| | **Objetivo principal:** precio de exportación (el de la garantía, según E19) | **Objetivo secundario:** precio de bolsa (base del mercado) |
|---|---|---|
| **Qué es** | `ExportMonedaUSD` / `ExpoEner`, en centUSD/kWh (E19) | Promedio horario simple del precio de bolsa nacional, en COP/kWh (E16) |
| **Modelo** | Mitad un Huber sobre el cambio del precio de exportación y mitad la regla de XM (`expo-huber-mitad-regla-...`) | Ridge sobre el cambio de s-1 a s+2, con corrección de sesgo de Duan (`tie-ridge11-parcial-cmg-duan-...`) |
| **Variables** | Las 11 nacionales sin ofertas y el sábado a martes de s, más 9 de exportación: nivel, diferencia con el precio nacional, momento, energía exportada, tasa de cambio y días parciales | 11 de la semana s-1 (precio, embalse, aportes y época), el precio de sábado a martes de s y el costo marginal programado de miércoles a viernes de s (E24) |
| **Cota del 90 %** | Conformal calibrada por régimen regulatorio de exportación (E20) | Conformal con los errores de las últimas 104 semanas ya calificadas |
| **Resultado 2018–2026** | 4.83 frente a 5.31 de la regla (−9 %, p = 0.08); 117 semanas con exportación | 93.7 frente a 115.3 de la regla (−19 %, p < 0.001); último año 113 frente a 127 (p = 0.18) |
| **Cuándo no hay pronóstico** | Si en la semana s-1 no se exportó (menos de 1 GWh). Desde el 7-sep-2026 no hay exportaciones | Si la semana s-1 no está completa. Si faltan los días de s, usa un respaldo sin ellos |

- **Por qué estos modelos:** a tres semanas, las ganancias medidas vinieron de **información disponible el viernes** (los días de la semana en curso, el costo marginal), no de modelos más complejos. LightGBM, bosques, redes, procesos gaussianos y ensambles con pesos aprendidos no superaron a los elegidos (E23, E25). La corrección de sesgo adaptativa empeoró (E17).
- **Candidato en paralelo (bolsa):** suma la hidrología de sábado a jueves y el precio del martes. Erra 92.1 frente a 93.7, sin ganar en todos los periodos. Lo decide el registro con 26 semanas.
- **Vigilancia:** la emisión revisa ambos modelos con las últimas 52 semanas calificadas (error frente a la regla, cobertura de la cota y sesgo). Si alguno falla, el estado pasa a *vigilancia*.
- **Monto de la garantía:** `src/garantia.py` lo reconstruye con supuestos (MXT constante de 74.25 GWh/semana; el CEE no cambia faltantes ni excesos), y `python src/experimentos.py e22` reproduce E22. No es el cálculo oficial de XM.
- **Supuestos y riesgos:** [docs/SUPUESTOS.md](docs/SUPUESTOS.md). El principal pendiente es qué contiene el precio de exportación bajo las reglas especiales del período de riesgo. Las preguntas están listas para el CRM de XM en [docs/CONSULTA_CRM_XM.md](docs/CONSULTA_CRM_XM.md).

---

Las secciones siguientes explican el **pronóstico a una semana** (lunes a domingo, ponderado por demanda), que fue el primer planteamiento y hoy es un complemento. El modelo de bolsa TIE usa la misma familia (Ridge sobre el cambio del precio) y 11 de esas variables.

---

## Cómo entender el modelo

### 1. Qué pronostica

El **precio de bolsa semanal ponderado por demanda** de la semana siguiente, en COP/kWh. La semana va de lunes a domingo:

$$P_s = \frac{\sum_{h \in s} P_h \, D_h}{\sum_{h \in s} D_h}$$

donde P<sub>h</sub> es el precio de bolsa y D<sub>h</sub> la demanda comercial de cada una de las 168 horas. Las horas de más consumo pesan más.

### 2. La idea central: pronosticar el cambio, no el nivel

La mejor pista sobre el precio de la próxima semana es el precio de esta semana. Por eso la referencia es el **pronóstico ingenuo** (*"la próxima semana costará lo mismo que esta"*), y el modelo solo estima **cuánto se va a mover el precio** a partir de esa base:

```
pronóstico = precio de esta semana × (1 + cambio estimado)
```

El cambio lo estima una **regresión Ridge**: una suma ponderada de 14 variables, con una penalización que evita que el modelo se ajuste demasiado a la historia. Al ser una suma, cada pronóstico se descompone **exactamente** en cuánto aportó cada variable.

### 3. Las 14 variables y hacia dónde empujan

Cada variable entra comparada con su valor típico. La tabla dice qué pasa con el pronóstico cuando la variable está **por encima de lo normal**, y cuánto pesa.

| Grupo | Variable | Si está por encima de lo normal, el pronóstico… | Peso |
|---|---|---|---|
| Precio | Precio del último día frente al promedio de la semana | **sube**: la tendencia de los últimos días tiende a continuar | alto |
| Precio | Cambio frente a la semana anterior | baja: tras una subida fuerte el precio tiende a devolverse | medio |
| Precio | Variación diaria del precio | sube: una semana agitada anticipa precios más altos | medio |
| Precio | Nivel del precio | baja: los precios muy altos tienden a bajar | medio |
| Precio | Pico horario frente al promedio | casi no cambia | bajo |
| Hidrología | Cambio semanal del embalse | **baja**: si el embalse se está llenando, hay más agua barata | alto |
| Hidrología | Nivel del embalse | baja | medio |
| Hidrología | Aportes de 4 semanas frente a la media | sube (ver nota) | medio |
| Hidrología | Aportes de la semana frente a la media | casi no cambia | bajo |
| Ofertas | Precio de oferta térmico | sube: la generación de respaldo es más cara | medio |
| Ofertas | Oferta no térmica (hidráulica) frente al precio | sube: si las hidráulicas ofertan por encima del precio actual, el precio tiende a subir hacia ellas | medio |
| Ofertas | Precio de oferta no térmico | baja levemente | bajo |
| Calendario | Época del año (dos variables) | sube de junio a noviembre (más en septiembre) y baja de enero a mayo (más en marzo) | alto |

**Nota:** los efectos son *parciales*, es decir, lo que aporta cada variable cuando las demás están en su valor. Por ejemplo, los aportes de 4 semanas suben el pronóstico porque su efecto bajista ya lo recogen el nivel y el cambio del embalse. No deben leerse como relaciones causales. Los signos se mantuvieron en 13 reentrenamientos anuales (`results/estabilidad_coef_14.csv`).

### 4. Ejemplo: el pronóstico de esta semana

Semana base del 26 de octubre al 1 de noviembre de 2026: precio de **528,5 COP/kWh**. Pronóstico registrado para la semana del 2 de noviembre: **400,6 COP/kWh (−24,2 %)**. *(Esa emisión usó la demanda incompleta que la API publicó el 1 de noviembre; con la corrección posterior, la base sería 509,4 y el pronóstico 403,5. El registro conserva lo emitido.)*

| Variable | Aporte al cambio |
|---|---|
| El domingo 1 de noviembre cerró muy por debajo del promedio de la semana | −25,3 % |
| Precio de oferta térmico | +6,5 % |
| Oferta hidráulica frente al precio | −5,2 % |
| Aportes de 4 semanas | −4,6 % |
| Época del año (noviembre) | +4,6 % |
| Variación diaria del precio | +4,0 % |
| Las demás variables y la tendencia promedio | −3,0 % |
| **Cambio total** | **−24,2 %** |

Lectura: el modelo espera que siga la caída con la que cerró la semana, en parte compensada por ofertas térmicas caras y por la época del año. Los aportes se combinan multiplicando, (1 + a)(1 + b)…, por eso no suman exactamente en porcentaje.

### 5. La cota superior al 90 %

```
cota = pronóstico × (1 + margen)
```

El **margen** es el error que el modelo solo superó en el 10 % de las últimas 104 semanas (calibración conformal). Se recalcula cada semana con los errores ya observados, así que se ensancha sola cuando el modelo empieza a fallar más.

- **Cómo leerla:** *"en 9 de cada 10 semanas de la evaluación, el precio real quedó por debajo de este valor"*. Para esta semana es 563,8 COP/kWh.
- **Su costo:** cuando cubre, la cota queda en promedio 37 % por encima del precio real. Esos son recursos que se inmovilizan de más.
- **Variante por volatilidad:** escala el margen con lo agitado que viene el precio. Cubre mejor las semanas de salto (78 % frente a 70 %), a cambio de más exceso. Elegir entre ambas depende de la regla de la garantía.

### 6. Cómo leer el panel de métricas

| Métrica | Qué mide | Meta | Desde 2018 |
|---|---|---|---|
| Mejora frente al ingenuo | Cuánto menos se equivoca que repetir el precio anterior | ≥ 10 % | 18,7 % ✓ |
| Error típico | Distancia promedio entre pronóstico y real, en % | referencia | 14,8 % |
| Sesgo | Si tiende a quedarse corto (−) o pasarse (+) | \|sesgo\| ≤ 5 % del precio | −12,5 COP/kWh (−3,8 %) ✓ |
| Cobertura de la cota | % de semanas con el precio bajo la cota | ≈ 90 % | 90,2 % ✓ |
| Exceso de la cota | Cuánto sobra la cota cuando cubre | ≤ 40 % | 37 % ✓ |
| Cobertura en semanas de salto | Cobertura en el 20 % de semanas con mayor cambio | ≥ 85 % | 70 % ✗ |

En la app, la página *Extra: la semana siguiente* muestra estas métricas para cada periodo de evaluación.

### 7. Los tres estados

| Estado | Cuándo | Qué hacer |
|---|---|---|
| **Normal** | Datos completos y el modelo rinde como en su evaluación | Usar el pronóstico y la cota |
| **Vigilancia** | Datos atrasados, a una serie le faltan 2 o más días de la semana base, variables fuera de todo lo visto, o en las últimas 26 semanas el modelo no le gana al ingenuo, la cota cubre menos de 80 % o el sesgo pasa de 5 % del precio con significancia (p < 0,05) | Usarlo con cautela; considerar la cota por volatilidad |
| **Respaldo** | Falta un dato del modelo | Se emite el ingenuo con una cota calibrada sobre sus propios errores |

### 8. Cuándo no confiar en él

- En **saltos bruscos de precio**, que no se anticipan. En las semanas en que el precio sube se queda corto 58 COP/kWh en promedio (el ingenuo, 69) y la cota cubre 81 %.
- Con el **embalse bajo 45 %**, donde no hay evidencia de que supere al ingenuo (mejora de 3,5 %, con intervalo de −16 % a +21 % en 44 semanas).
- En **regímenes nunca vistos**, por cambios regulatorios o condiciones fuera del rango 2010–2026.
- Si al emitir solo se conoce la semana hasta el viernes: el error sube ~16 % (ver la [bitácora, E9](docs/EXPERIMENTOS.md)).

La [ficha técnica](FICHA_TECNICA.md) resume todo esto en una página.

### 9. Qué se probó además

Se compararon LightGBM, XGBoost, SARIMAX, ARIMA, ElasticNet, un modelo en dos etapas, LEAR diario y variables en frecuencia (STFT y armónicos). El mejor candidato es un ensamble de Ridge 14 con LEAR: erra 3 % menos (52,6 frente a 54,1 COP/kWh), pero al corregir por los 67 modelos probados esa mejora ya no es significativa (p = 0,52 para el mejor de todos), así que aún debe validarse con pronósticos reales. Detalle en la [bitácora](docs/EXPERIMENTOS.md) y la [auditoría](docs/AUDITORIA.md).

### Candidatos del registro a una semana (ya no emite)

Mientras emitió (5 y 12 de noviembre de 2026), `src/semanal.py` también calculaba y registraba el ensamble **Ridge 14 + LEAR directo** (`candidato_*` en `registro/pronosticos.csv`), con su propia cota. No cambia el pronóstico oficial, y una falla suya no detiene la emisión. Las filas anteriores no se llenan hacia atrás, para que la comparación sea independiente.

**Regla fijada de antemano:** a las 12 semanas calificadas se hace una primera lectura, solo informativa. A las 26, el candidato reemplaza al oficial si su error medio es menor y la cobertura de su cota no baja de 85 %. Como ese registro dejó de emitir, la regla se aplica ahora al candidato TIE (ver la emisión semanal).

**Segundo candidato (registro a una semana):** Ridge 14 más el costo marginal del despacho programado (`CostMargDesp`) del lunes y el martes de la semana objetivo (`candidato_cmg_*`, versión `ridge14-cmg2d-conformal104-v1`). XM lo publica antes de cada día, así que con la emisión del miércoles esos dos días ya se conocen. En la evaluación simulada erró 39,3 COP/kWh frente a 53,9 de Ridge 14 (E12). Cada snapshot guarda los valores horarios tal como estaban publicados al emitir, para verificar después que la historia de la API no se revisó. Si el costo marginal no está publicado, no se emite el candidato y la emisión oficial sigue.

Se decide con la misma regla y el mismo calendario, más una condición: **solo puede reemplazar al oficial si XM confirma que la garantía puede fijarse con la semana objetivo ya iniciada** y que los dos días están publicados a la hora de emisión. Si no, su resultado solo cuantifica cuánto vale esperar a esa información.

---

## Cómo usarlo

### Instalación

Requiere **Python 3.11**: la librería oficial [`pydataxm`](https://github.com/EquipoAnaliticaXM/API_XM) falla en 3.12 o superior por su dependencia `nest_asyncio`.

```bash
python3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q tests
```

### Emisión semanal para la garantía TIE (viernes después de las 20:00)

```bash
correr_semanal.bat
```

Desde el 15 de noviembre de 2026 la emisión sigue la regla de la garantía TIE (CREG 004 de 2003, art. 23; ver [docs/SUPUESTOS.md](docs/SUPUESTOS.md)). El viernes de la semana s, [src/semanal_tie.py](src/semanal_tie.py) pronostica para la semana s+2, de sábado a viernes, los dos precios del núcleo. Cada uno se registra junto a la regla de XM, que repite el valor de s-1.

- **Precio de bolsa:** Ridge con 11 variables de s-1 (sin ofertas, que a tres semanas no aportan) más el precio de sábado a martes de s y el costo marginal programado de miércoles a viernes de s, con corrección de sesgo y cota del 90 % (E16, E24).
- **Precio de exportación:** mitad Huber y mitad regla, con cota por régimen (E19, E20), en las columnas `expo_*` del registro. Antes de pronosticarlo, la emisión actualiza las series de exportación y verifica que la semana s-1 esté completa. Si no se exportó, lo deja anotado en los motivos.
- **Respaldo:** si faltan los días de s o el costo marginal, usa el mismo Ridge sin ellos. Si la semana s-1 no está completa, no emite.
- **Candidato en paralelo:** el mismo modelo más la hidrología de sábado a jueves de s y el precio del martes. Con el costo marginal, en el backtest erra 92.1 frente a 93.7 del registrado, pero no gana en todos los periodos. Se registra a su lado, y con 26 semanas calificadas reemplaza al modelo si erra menos y su cota cubre al menos 85 %.
- **Registro:** `registro/pronosticos_tie.csv`, encadenado con SHA-256, con snapshots en `registro/snapshots_tie/`.

El script también califica las emisiones anteriores (incluidas las del registro a una semana, que ya no emite) y regenera `results/app/`. Al final hace un commit con el tag `registro-tie-AAAA-MM-DD`; no lo empuja. La salida queda en `registro/logs/AAAA-MM-DD.log`.

Para probar sin registrar: `python src/semanal_tie.py --seco --fecha 2026-11-13`.

**Por qué el viernes en la noche:** es el día de cálculo del ASIC. La API publica el precio con unos 3 días de rezago y la hidrología con 1: el precio del martes y la hidrología del jueves aparecen hacia el viernes en la tarde o la noche. El costo marginal programado del viernes se publica la víspera. Si se emite antes, el modelo cae a respaldo y el candidato no se calcula.

El registro a una semana (`registro/pronosticos.csv`, [src/semanal.py](src/semanal.py)) se conserva como evidencia: sus filas no se borran y se siguen calificando.

### Ver la app

```bash
python src/resultados_app.py
```

```bash
streamlit run app/streamlit_app.py
```

El primer comando reúne en `results/app/` los resultados que muestra la app (la emisión semanal también lo hace). La app solo lee esa carpeta, así que no consulta la API de XM al abrirse.

### Informe PDF automático

```bash
python src/informe_pdf.py
```

[src/informe_pdf.py](src/informe_pdf.py) arma un informe de 5 páginas con los resultados de `results/app/` y el registro:

1. Resumen y pronóstico vigente, con su estado.
2. Precio de bolsa: gráfica de los dos últimos años y error por periodo.
3. Precio de exportación.
4. Registro de pronósticos y explicación del pronóstico por variables.
5. Supuestos, límites y cómo leer las gráficas.

`correr_semanal.bat` lo genera en cada corrida, incluso si la emisión falla. Lo guarda en `informes/informe_TIE_AAAA-MM-DD.pdf` (histórico, incluido en el commit de la emisión) y en `results/app/informe_ultimo.pdf`, que se descarga desde la app (páginas Inicio y Pronóstico).

### Estilo de las gráficas: ISA-101

La app y el informe siguen la norma ANSI/ISA-101.01 de interfaces de alto desempeño. La paleta está en [src/isa101.py](src/isa101.py) y el tema de Streamlit en `.streamlit/config.toml`.

- **Fondo y datos normales:** fondo gris neutro, y los datos en condición normal en escala de grises.
- **Trazos:** lo que pasó va en negro grueso, la regla de XM en gris discontinuo y el techo en gris punteado. Nuestro modelo usa el único acento, azul pizarra.
- **Color saturado, solo para lo anormal:**
  - rojo con triángulo: el precio real superó el techo;
  - amarillo: vigilancia, o un resultado peor que la regla;
  - naranja: emisión de respaldo.
- **Identidad sin depender del color:** cada serie se distingue también por el trazo o el símbolo, y los estados llevan símbolo y texto.

### Reproducir la evaluación

```bash
python src/experimentos.py e16
```

Cada comando regenera sus archivos en `results/`:
- **Núcleo TIE:** `e16` (precio de bolsa, incluye E24), `e19` (precio de exportación, incluye la cota por régimen de E20), `e22` (monto de la garantía) y `e17`.
- **Pronóstico a una semana:** `e1`, `e2`, `e3e4`, `e5e6`, `e7`, `e8`, `e9`, `e10`, `e11`, `e12`, `e13`, `e14`, `e15`, `cortes`, `tuning` y `alertas`.
- **Sin comando:** E18, E20 (salvo la cota), E21, E23 y E25 se corrieron con guiones aparte. La bitácora deja sus resultados.

La [bitácora de experimentos](docs/EXPERIMENTOS.md) explica cada uno.

---

## Estructura

```
├── README.md                 este documento
├── FICHA_TECNICA.md          el modelo en una página
├── docs/SUPUESTOS.md         la regla de la garantía TIE y los supuestos del proyecto
├── docs/PREGUNTAS_XM.md      preguntas a XM y lo que ya respondieron
├── docs/EXPERIMENTOS.md      bitácora de experimentos E0–E25, con tablas y decisiones
├── docs/CONSULTA_CRM_XM.md   preguntas regulatorias listas para el CRM de XM
├── docs/AUDITORIA*.md        auditorías del 5, 10, 15 (general, por partes y exportación) y 16 de noviembre (app)
├── correr_semanal.bat        emisión semanal TIE (viernes después de las 20:00)
├── requirements.txt          dependencias fijas (Python 3.11)
├── app/
│   ├── streamlit_app.py      app de resultados (6 páginas, con glosario)
│   └── requirements.txt      dependencias mínimas para Streamlit Cloud
├── src/
│   ├── config.py             modelos en operación (bolsa TIE, candidato y exportación), cota y umbrales del monitoreo
│   ├── semanal_tie.py        emisión TIE: datos, precios de bolsa y exportación de s+2, candidato, registro, calificación, reproducción
│   ├── garantia.py           monto de la garantía de exportación, reconstruido con supuestos (E22)
│   ├── resultados_app.py     reúne en results/app/ lo que muestra la app
│   ├── semanal.py            emisión a una semana (ya no emite; califica y reproduce su registro)
│   ├── monitoreo.py          controles de calidad, rango histórico, desempeño reciente y estado
│   ├── xm_client.py          descarga desde XM con pydataxm (o consulta directa) y caché mensual
│   ├── data_pipeline.py      tablas semanales: a una semana, TIE (bolsa) y exportación, y variantes de los experimentos
│   ├── feature_engineering.py variables del modelo
│   ├── models.py             Ridge y modelos comparados (árboles, cuantílicos, dos etapas, SARIMAX, ARIMA)
│   ├── lear.py               LEAR diario agregado a la semana (candidato, E11)
│   ├── calibration.py        cotas conformales
│   ├── alertas.py            alertas tempranas y su explicación
│   ├── backtesting.py        evaluación walk-forward
│   ├── evaluation.py         métricas y pruebas estadísticas
│   ├── experimentos.py       comandos de cada experimento
│   ├── auditoria.py          regenera las cifras de la auditoría
│   ├── trazabilidad.py       registro de corridas (commit, datos, versiones)
│   ├── tuning.py             hiperparámetros con datos anteriores a 2018
│   └── graficas.py           frontera de las cotas (E7)
├── registro/                 pronósticos emitidos (inmutables) y snapshots: pronosticos_tie.csv y el registro a una semana
├── results/                  resultados de los experimentos
├── data/                     caché de la API de XM, ONI de NOAA y tablas semanales
├── tests/                    reproducción, no fuga de información, calibración, alertas y operación
└── referencia/pae_original/  primera versión del modelo y su notebook
```

## Fuentes

- API pública de XM (`servapibi.xm.com.co`), consultada con `pydataxm`: precio de bolsa, demanda, hidrología, ofertas, costo marginal programado, y exportaciones (`ExportMonedaUSD`, `ExpoEner`).
- Material de formación de XM (Reafirmación 2025, sesión 2) para la regla de la garantía TIE (CREG 004 de 2003, art. 23).
- Índice ONI de NOAA CPC (fase de El Niño–Oscilación del Sur, usado en los experimentos).
