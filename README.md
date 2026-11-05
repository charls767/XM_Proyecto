# XM_Proyecto · Pronóstico semanal del precio de bolsa

Modelo para anticipar, con una semana de antelación, el **precio de bolsa promedio del Mercado de Energía Mayorista (MEM) colombiano**, junto con una **cota superior de riesgo** y **alertas tempranas**. Es un insumo para estimar la garantía de los intercambios de energía con Ecuador (caso XM–UNAL).

Cada semana el proceso descarga los datos de XM, revisa su calidad, emite el pronóstico con su explicación, lo guarda en un registro que no se puede modificar y actualiza un tablero.

| En una mirada (evaluación 2018–2026) | |
|---|---|
| Error medio del pronóstico | 54 COP/kWh, **19 % menos** que repetir el precio de la semana anterior |
| Error típico | ~15 % del precio |
| Cota al 90 % | El precio real quedó por debajo en **90 %** de las semanas |
| Límite conocido | En las semanas de saltos bruscos la cota cubre solo ~70 % |

> Prototipo académico; no es una publicación oficial de XM. La evaluación 2018–2026 es simulada; la evidencia independiente es el [registro de pronósticos](registro/pronosticos.csv), que empezó el 5 de noviembre de 2026.

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

En el tablero cada métrica tiene un semáforo con texto (*Cumple*, *Vigilar*, *No cumple*) y se puede ver para las últimas 26 semanas, el último año, el estrés de 2022–2024 o desde 2018.

### 7. Los tres estados

| Estado | Cuándo | Qué hacer |
|---|---|---|
| **Normal** | Datos completos y el modelo rinde como en su evaluación | Usar el pronóstico y la cota |
| **Vigilancia** | Datos atrasados, variables fuera de todo lo visto, el modelo no le gana al ingenuo en las últimas 26 semanas o la cota cubre menos de 80 % | Usarlo con cautela; considerar la cota por volatilidad |
| **Respaldo** | Falta un dato del modelo | Se emite el ingenuo con una cota calibrada sobre sus propios errores |

### 8. Cuándo no confiar en él

- En **saltos bruscos de precio**, que no se anticipan.
- En **regímenes nunca vistos**, por cambios regulatorios o condiciones fuera del rango 2010–2026.
- Si al emitir solo se conoce la semana hasta el viernes: el error sube ~16 % (ver la [bitácora, E9](docs/EXPERIMENTOS.md)).

La [ficha técnica](FICHA_TECNICA.md) resume todo esto en una página.

### 9. Qué se probó además

Se compararon LightGBM, XGBoost, SARIMAX, ElasticNet, un modelo en dos etapas y LEAR diario. El mejor candidato es un ensamble de Ridge 14 con LEAR: erra 3 % menos (52,6 frente a 54,1 COP/kWh), con mejora significativa en 2022–2024, pero se añadió tras ver los resultados y aún debe validarse con pronósticos reales. Detalle en la [bitácora](docs/EXPERIMENTOS.md).

### Modelo candidato en paralelo

Desde la próxima emisión, `src/semanal.py` también calcula y registra el ensamble **Ridge 14 + LEAR directo** (`candidato_*` en `registro/pronosticos.csv`), con su propia cota. No cambia el pronóstico oficial, y una falla suya no detiene la emisión. Las filas anteriores no se llenan hacia atrás, para que la comparación sea independiente.

**Regla fijada de antemano:** a las 12 semanas calificadas se hace una primera lectura, solo informativa. A las 26, el candidato reemplaza al oficial si su error medio es menor y la cobertura de su cota no baja de 85 %. El tablero muestra el avance.

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

### Emisión semanal (cada miércoles)

```bash
correr_semanal.bat
```

El script actualiza los datos, emite y registra el pronóstico, califica los anteriores y regenera el tablero. Para programarlo: Programador de tareas de Windows → Crear tarea básica → Semanal, miércoles en la tarde → Iniciar un programa → `correr_semanal.bat`.

**Por qué el miércoles:** la API publica el precio con unos 3 días de rezago, así que el domingo queda disponible hacia el miércoles. Si se corre antes, la semana no está completa y no se emite nada nuevo. Por eso, hoy el pronóstico sale cuando la semana objetivo ya empezó, aunque no usa ningún dato de ella. Si XM confirma una emisión más temprana, el modelo adecuado es Ridge 14 + despacho programado (ver [E9](docs/EXPERIMENTOS.md)).

### Ver el tablero

```bash
python -m http.server 8000 --directory dashboard
```

Luego abre http://localhost:8000. También funciona abriendo `dashboard/index.html` directamente en el navegador.

### Reproducir la evaluación

```bash
python src/experimentos.py e10
```

Cada comando (`e1`, `e2`, `e3e4`, `e5e6`, `e7`, `e8`, `e9`, `e10`, `e11`, `cortes`, `tuning`, `alertas`) regenera sus archivos en `results/`. La [bitácora de experimentos](docs/EXPERIMENTOS.md) explica cada uno.

---

## Estructura

```
├── README.md                 este documento
├── FICHA_TECNICA.md          el modelo en una página
├── docs/EXPERIMENTOS.md      bitácora de experimentos E1–E11, con tablas y decisiones
├── correr_semanal.bat        emisión semanal completa
├── requirements.txt          dependencias fijas (Python 3.11)
├── src/
│   ├── config.py             modelo en operación, cota y umbrales del monitoreo
│   ├── semanal.py            emisión: datos, controles, pronóstico, explicación, registro, calificación
│   ├── monitoreo.py          controles de calidad, rango histórico, desempeño reciente y estado
│   ├── xm_client.py          descarga desde XM con pydataxm (o consulta directa) y caché mensual
│   ├── data_pipeline.py      tabla semanal y variantes usadas en los experimentos
│   ├── feature_engineering.py variables del modelo
│   ├── models.py             Ridge y modelos comparados (árboles, cuantílicos, dos etapas, SARIMAX)
│   ├── lear.py               LEAR diario agregado a la semana (candidato, E11)
│   ├── calibration.py        cotas conformales
│   ├── alertas.py            alertas tempranas y su explicación
│   ├── backtesting.py        evaluación walk-forward
│   ├── evaluation.py         métricas y pruebas estadísticas
│   ├── experimentos.py       comandos de cada experimento
│   ├── tuning.py             hiperparámetros con datos anteriores a 2018
│   └── graficas.py           frontera de las cotas (E7)
├── dashboard/                plantilla, generador e index.html del tablero
├── registro/                 pronósticos emitidos (inmutables) y snapshots de cada emisión
├── results/                  resultados de los experimentos
├── data/                     caché de la API de XM, ONI de NOAA y tablas semanales
├── tests/                    reproducción, no fuga de información, calibración, alertas y operación
└── referencia/pae_original/  primera versión del modelo y su notebook
```

## Fuentes

- API pública de XM (`servapibi.xm.com.co`), consultada con `pydataxm`.
- Índice ONI de NOAA CPC (fase de El Niño–Oscilación del Sur, usado en los experimentos).
