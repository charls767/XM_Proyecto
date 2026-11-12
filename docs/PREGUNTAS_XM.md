# Preguntas para validar el proyecto con XM

Guía para la reunión con XM. Cada pregunta trae tres partes:

- **Hoy suponemos:** lo que el proyecto da por cierto sin confirmarlo, y el archivo donde está.
- **Pregunta:** lo que hay que preguntar, en una frase que se pueda leer tal cual en la reunión.
- **Si la respuesta es distinta:** qué hay que cambiar en el proyecto.

Antes de las preguntas hay un resumen de [lo que ya responden las fuentes públicas](#lo-que-ya-responden-las-fuentes-públicas). Sirve para no preguntar lo que ya está escrito y para pedirle a XM que confirme o corrija. Las preguntas van por orden de impacto. Las del bloque A pueden dejar el caso de uso en pausa. Las de B y C pueden cambiar la variable que se pronostica. Las de D a G ajustan datos y detalles. Al final hay una [hoja de respuestas](#hoja-de-respuestas) para anotar durante la reunión.

**Lectura normativa sin validar:** lo citado sobre la CREG 101 127 y la Resolución 40308 viene de una revisión rápida de los textos públicos y, en el caso de la 40308, del proyecto de resolución, no de su versión final. Sirve para formular las preguntas, no como interpretación oficial.

## Contexto que hay que llevar claro

| Hecho público | Por qué le importa al proyecto |
|---|---|
| El 7 de septiembre de 2026 empezó el período de riesgo de desabastecimiento (Circular CREG 343 del 5 de septiembre) y las exportaciones por TIE a Ecuador quedaron en cero ([Portafolio](https://www.portafolio.co/energia/colombia-termina-suministro-de-energia-a-ecuador-exportaciones-por-mas-de-530-000-millones-quedaron-frenadas-503959)). Según la prensa se reanudaron, con poco volumen, el 16 de octubre ([Xinhua](https://english.news.cn/20261017/1222a41a7f3a4087a9be1cbe040acac5/c.html), [El Comercio](https://www.elcomercio.com/actualidad/negocios/esta-es-la-energia-que-colombia-entrega-a-ecuador/)) y de nuevo el 6 de noviembre, con unos 247 MW ([Diario Los Andes](https://diariolosandes.com.ec/colombia-retomo-las-exportaciones-electricas-a-ecuador/)) | Los intercambios van y vienen: la garantía puede aplicar unas semanas y otras no |
| La [CREG 101 127 de 2026](https://gestornormativo.creg.gov.co/gestor/entorno/docs/originales/Resoluci%C3%B3n_CREG_101_127_2026/) suspende el estatuto de 2014 hasta una resolución definitiva o hasta el 31 de mayo de 2027. Regula las ofertas hidráulicas con una curva y limita las ofertas en el despacho ideal | El modelo aprendió de la historia 2010–2026, que se formó con otras reglas |
| Para los cargos de exportación, esa norma toma el máximo entre el Precio de Bolsa TIE, el precio de la planta más cara más arranque y parada, y el costo marginal del importador | Quizá la garantía no dependa del precio que pronosticamos |
| La Resolución 40308 de 2026 habilitó contratos bilaterales entre agentes privados ([proyecto](https://www.expreso.ec/uploads/files/2026/06/23/Exportaciones_Ecuador_Contratos_OAJ.pdf)): las diferencias deben ser "respaldadas, prepagadas y recaudadas" por las partes | Pudo cambiar cuánto se expone cada parte y quién cubre el riesgo |

**En nuestros datos:** la semana del 7 de septiembre el precio cayó de 932 a 593 COP/kWh y la oferta no térmica de 452 a 280 COP/kWh. En las 8 semanas siguientes el modelo erró en promedio 60 COP/kWh y el ingenuo 93. Son pocas semanas, y la coincidencia no prueba que la causa sea el cambio de reglas.

## Lo que ya responden las fuentes públicas

Búsqueda del 12 de noviembre de 2026 en normas de la CREG, páginas de XM, prensa y el código de la librería `pydataxm` 0.3.19. Desde el entorno de trabajo no se pudo abrir el texto completo de las normas (el Gestor Normativo de la CREG y las APIs de XM y SIMEM estaban bloqueados por la red), así que lo de esta tabla viene de los extractos que muestra el buscador. **Todo debe confirmarse con XM o con el texto vigente de la norma.**

| ID | Lo que encontramos | Fuente | Confianza | Qué queda por preguntar |
|---|---|---|---|---|
| **B2** | **Las exportaciones se liquidan al Precio de Bolsa TIE, no al precio de bolsa nacional.** El Precio de Bolsa TIE es el precio de oferta más alto, en cada hora, de los recursos sin inflexibilidad que cubren la demanda internacional en el despacho ideal | CREG 160 de 2009 | Media: norma de 2009, puede estar modificada | Si esa definición sigue vigente con la CREG 101 127, y si la garantía usa ese mismo precio |
| B2, C4 | SIMEM publica un conjunto de datos de precio de bolsa horario con los precios nacional, internacional y TIE (identificador `EC6945`), consultable con `pydataxm` | Proyectos públicos en GitHub | Media | Cuál de esos precios usar y desde qué fecha tiene historial |
| B1, B3 | El mecanismo de la norma es un **pago anticipado**, no una garantía bancaria: se calcula sobre el monto esperado de las TIE de corto plazo, y sin él no puede haber TIE | CREG 004 de 2003, art. 23 | Media | La fórmula vigente y quién paga en una exportación |
| B4, C2, C3, D1 | **El ASIC informa el pago anticipado el viernes, a más tardar a las 15:00, para la semana s+2.** Para ese cálculo las semanas van **de sábado a viernes**. Se ajusta el viernes de la semana s+2 con los seis primeros días reales, y otra vez el viernes de s+3 | CREG 004 de 2003, modificada | Media: es la regla para importaciones; para exportaciones no se confirmó | Si aplica igual a las exportaciones. **Si aplica, cambian la semana del modelo (sábado a viernes), el horizonte (dos semanas, no una) y la hora de emisión (viernes antes de las 15:00)** |
| B1 | Hay un proyecto de la CREG (701 065 de 2024) que modifica el art. 23 de la CREG 004 de 2003 y fija montos semanales de garantía por enlace | CREG, proyecto 701 065 de 2024 | Baja: no se confirmó si quedó en firme | Cuál es la versión vigente del art. 23 |
| B1 | La CREG 101 127 de 2026 (27 de agosto) exige que las exportaciones salgan sobre todo de generación térmica. La hidráulica, la eólica y la solar solo se exportan como excedente, después de cubrir la demanda nacional | Prensa ecuatoriana y colombiana | Media | Cómo cambia eso el precio de exportación y la garantía |
| E1 | El período de riesgo empezó el 7 de septiembre de 2026 por la Circular CREG 343 del 5 de septiembre. No tiene fecha de fin fija: termina cuando se recuperen los embalses o cuando la CREG lo decida. XM espera que lo más crítico sea entre diciembre de 2026 y marzo de 2027 | Prensa, citando a la CREG y a XM | Media | Las fechas de los períodos de riesgo anteriores, desde 2010 |
| **D4** | **Las ofertas de precio son confidenciales hasta su publicación, y esta se puede hacer desde el primer día hábil del mes siguiente.** Una norma anterior (CREG 094 de 2001) las publicaba el mismo día del despacho | CREG 006 de 2009 | Media: no se confirmó si se modificó después | En la API vemos `PrecOferDesp` con ~3 días de rezago. Hay que preguntar desde qué fecha se publican así. **Si en años pasados solo salían al mes siguiente, la evaluación usó ofertas que no se conocían al emitir** |
| C1, F3 | La demanda comercial es la demanda real del comercializador más las pérdidas de las redes regionales y locales y del Sistema de Transmisión Nacional | Glosario de XM | Alta | Si incluye o no las exportaciones |
| D3 | El despacho programado es la programación del día siguiente. Los operadores de red entregan su pronóstico de demanda antes de las 07:30 del día anterior. Los archivos están en el portal de XM, en Generación > Informes despacho | Páginas de XM | Media | A qué hora se publica el despacho programado |
| D5, D6 | El precio tiene varias versiones de liquidación, en orden: TX1, TX2, TXR, TXF y después TX3 y siguientes. TXF no es la definitiva | Proyectos públicos en GitHub | Media | Qué versión usar para calificar |
| D5, D6 | `pydataxm` 0.3.19 tiene un módulo para SIMEM (`pydatasimem.py`) que maneja versiones: lee un calendario de versiones por mes (conjunto `24914F`, con `Version`, `FechaPublicacion` y `esMaximaVersion`) y permite pedir una variable en una versión dada (`VariableSIMEM(..., version=...)`). Cuando un mes solo tiene TXR, la librería supone que TX2 salió un día antes y TX1 dos días antes | Código de la librería | Alta, sobre lo que hace el código | Si con SIMEM se pueden reconstruir los datos tal como estaban publicados. Eso resolvería en parte D6 |
| F1 | Las unidades 1 y 2 de Ituango entraron en operación comercial el 1 de diciembre de 2022. XM reescala años anteriores con "la media histórica actual" | XM | Media, para el salto de 2022 | Si el salto de `AporEnerMediHist` se debe a eso |
| D2 | No se encontró un rezago oficial por serie. Otro proyecto público también observa ~3 días para el precio | — | — | Se mantiene la pregunta |
| F7, F8 | No se encontró la definición oficial de `PorcVoluUtilDiar` ni de la convención horaria de `Hour01`. Un proyecto de terceros usa un desfase configurable para convertir las horas | — | — | Se mantienen las preguntas |

Fuentes: [Resolución CREG 160 de 2009](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_creg_0160_2009.htm), [Resolución CREG 004 de 2003](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_creg_0004_2003.htm), [Resolución CREG 116 de 2012](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_creg_0116_2012.htm), [Resolución CREG 006 de 2009](https://normas.cra.gov.co/gestor/docs/resolucion_creg_0006_2009.htm), [Proyecto CREG 701 065 de 2024](https://gestornormativo.creg.gov.co/gestor/entorno/docs/originales/Proyecto_Resoluci%C3%B3n_CREG_701_065_2024/), [Glosario de XM](https://www.xm.com.co/herramientas/glosario-xm), [Despacho de generación, XM](https://www.xm.com.co/generacion/despacho), [Estándar de información del despacho, XM](https://www.xm.com.co/sites/default/files/documents/XM-CND-2025-055%20Estandar%20de%20informacion%20del%20despacho.pdf), [Ituango en operación comercial, XM](https://www.xm.com.co/noticias/5412-proyecto-hidroelectrico-ituango-entra-en-operacion-comercial), [Informe CND de abril de 2025](https://img.lalr.co/cms/2025/04/08133137/XM-CNO-2025-04-03-1.pdf), [El Heraldo, período crítico](https://www.elheraldo.co/colombia/2026/10/15/entre-diciembre-y-marzo-sera-el-periodo-mas-critico-del-fenomeno-de-el-nino-advierte-xm/), [El Diario, límite a las ventas](https://www.eldiario.ec/ecuador/colombia-limita-la-venta-de-electricidad-a-ecuador-por-riesgo-de-desabastecimiento-07102026/), [Resolución MinEnergía 40308 de 2026](https://img.lalr.co/cms/2026/07/22124329/resolucion-40308-2026_36694.pdf), [API_XM](https://github.com/EquipoAnaliticaXM/API_XM), [VatioPlan](https://github.com/julianordonez2005/VatioPlan), [Forecast-Energy-StockChange-Colombia](https://github.com/POLUX89/Forecast-Energy-StockChange-Colombia).

---

## A. ¿El caso de uso sigue vigente?

**A1. Vigencia**
- **Hoy suponemos:** existe una garantía de los intercambios con Ecuador que se calcula cada semana (`README.md`).
- **Pregunta:** con las exportaciones intermitentes desde septiembre, ¿se está calculando la garantía en las semanas en que hay intercambio? ¿En qué condiciones se suspende y se reactiva?
- **Si la respuesta es distinta:** el caso de uso queda en pausa hasta que se reanuden los intercambios, o hay que redefinirlo.

**A2. Usuario y decisión**
- **Hoy suponemos:** el usuario es quien fija la garantía, pero no sabemos quién es.
- **Pregunta:** ¿quién usaría el pronóstico (XM como ASIC, el agente exportador, un generador) y qué decisión concreta toma con él?
- **Si la respuesta es distinta:** cambian el formato de entrega, el tablero y la definición de "útil".

**A3. Rival real**
- **Hoy suponemos:** la referencia es el ingenuo, es decir, repetir el precio de la semana anterior (`src/evaluation.py`).
- **Pregunta:** ¿qué estimación se usa hoy, quién la hace y nos pueden compartir su historial frente al precio real?
- **Si la respuesta es distinta:** el modelo hay que compararlo con esa estimación. Si ella erra menos, el modelo no aporta.

**A4. Costo de los errores**
- **Hoy suponemos:** estimar mal inmoviliza recursos de más o deja garantías cortas, pero no tenemos casos que lo respalden.
- **Pregunta:** ¿ha habido episodios con recursos inmovilizados de más o garantías insuficientes? ¿Con qué montos?
- **Si la respuesta es distinta:** sin casos, el beneficio del proyecto queda sin demostrar.

## B. La regla de la garantía

**B1. Fórmula y norma**
- **Hoy suponemos:** garantía ≈ cantidad × precio pronosticado, sin factores adicionales.
- **Pregunta:** ¿cuál es la fórmula exacta (cantidad, precio, factores, plazos) y qué norma la rige hoy? ¿Cambia con el régimen TIE, con contratos bilaterales o en período de riesgo?
- **Si la respuesta es distinta:** hay que agregar la fórmula al tablero y evaluar el error en pesos, no solo en COP/kWh.

**B2. Precio que entra en el cálculo** ⚠️ *la pregunta técnica más importante*
- **Hoy suponemos:** el precio de bolsa nacional `PrecBolsNaci` (`src/xm_client.py`).
- **Pregunta:** ¿qué precio entra en la garantía: el precio de bolsa nacional, el Precio de Bolsa TIE o el máximo del Anexo 3 de la CREG 101 127?
- **Si la respuesta es distinta:** la variable que pronostica el modelo es la equivocada y hay que rehacer el objetivo y la evaluación.
- **Ya encontramos:** la CREG 160 de 2009 liquida las exportaciones al Precio de Bolsa TIE. Llevar esa definición y pedir que la confirmen.

**B3. Instrumento**
- **Hoy suponemos:** un monto en COP.
- **Pregunta:** ¿es una garantía o un prepago? ¿Qué instrumento se usa, en qué moneda y con qué tasa de cambio?
- **Si la respuesta es distinta:** si es en dólares, hay que sumar el riesgo cambiario.

**B4. Periodo y momento de constitución**
- **Hoy suponemos:** cubre una semana de lunes a domingo.
- **Pregunta:** ¿qué periodo cubre la garantía y qué día, y a qué hora, debe quedar constituida?
- **Ya encontramos:** en la CREG 004 de 2003, el ASIC informa el viernes antes de las 15:00 el pago anticipado de la semana s+2, con semanas de sábado a viernes. Preguntar si aplica a las exportaciones.
- **Si la respuesta es distinta:** cambian la semana del modelo (C2) y la hora de emisión (D1).

**B5. Costo de equivocarse en cada dirección**
- **Hoy suponemos:** una cota al 90 %, elegida por nosotros, y ninguna corrección del sesgo a quedarse corto (`src/config.py`, `NIVEL_COTA = 0.9`).
- **Pregunta:** ¿qué pasa si la garantía se queda corta (limitación, incumplimiento, multas)? ¿Cuánto cuesta inmovilizar de más?
- **Si la respuesta es distinta:** de la relación entre ambos costos salen tres cosas: el nivel de la cota, si se corrige el sesgo (factor de Duan) y cuál de las dos variantes de cota usar.

**B6. Error aceptable**
- **Hoy suponemos:** no hay umbral. El error típico es de ~15 %.
- **Pregunta:** ¿qué error sería aceptable, en % o en COP/kWh, en semanas normales y en semanas de estrés?
- **Si la respuesta es distinta:** con ese umbral se puede decir si el modelo sirve.

## C. Qué se debe pronosticar

**C1. Ponderación**
- **Hoy suponemos:** precio semanal ponderado por la demanda comercial nacional, hora a hora (`src/data_pipeline.py`, `precio_ponderado`).
- **Pregunta:** si la exposición depende de las horas en que se exporta, ¿hay que ponderar por la energía exportada y no por la demanda nacional?
- **Si la respuesta es distinta:** cambia la definición del objetivo y hay que rehacer la evaluación.

**C2. Semana**
- **Hoy suponemos:** de lunes a domingo.
- **Pregunta:** ¿la semana relevante es de lunes a domingo, o sigue otro ciclo de liquidación?
- **Si la respuesta es distinta:** hay que reconstruir la tabla semanal con el ciclo correcto.

**C3. Horizonte**
- **Hoy suponemos:** una semana adelante.
- **Pregunta:** ¿basta con una semana de antelación, o la decisión necesita más?
- **Si la respuesta es distinta:** con un horizonte mayor, el error crecería y habría que reentrenar.

**C4. Serie de precio**
- **Hoy suponemos:** `PrecBolsNaci` para entrenar y calificar. `PrecBolsNaciTX1` solo se usó para medir el efecto de las revisiones.
- **Pregunta:** ¿qué diferencia hay entre `PrecBolsNaci`, `PrecBolsNaciTX1`, `PrecTransBolsa` y `PPPrecBolsNaci`, y cuál corresponde a este fin?
- **Si la respuesta es distinta:** cambia la serie objetivo.

## D. Cuándo está disponible cada dato

**D1. Hora de la decisión**
- **Hoy suponemos:** se emite el miércoles, cuando la semana base ya está completa, aunque la semana pronosticada ya empezó (`README.md`).
- **Pregunta:** ¿qué día y a qué hora debe estar listo el pronóstico?
- **Si la respuesta es distinta:** se cambia el modelo según la tabla:

| Si la decisión es… | Dato disponible | Modelo | Error 2018–26 (MAE) |
|---|---|---|---|
| Lunes temprano | Semana base hasta el viernes | Ridge 14 + despacho programado | 61 COP/kWh |
| Miércoles o después | Semana base completa, pero la semana objetivo ya empezó | Ridge 14 | 54 COP/kWh |

**D2. Rezago oficial de publicación**
- **Hoy suponemos:** lo observado en la API (`data/processed/diccionario_datos.csv`): unos 3 días para precio, demanda, ofertas y generación, y 1 día para aportes y embalse. Capacidad efectiva y consumo de combustible no se han medido.
- **Pregunta:** ¿cuál es el rezago oficial de cada serie en la API? ¿Es el mismo en Sinergox o en los archivos para agentes?
- **Si la respuesta es distinta:** si otro canal publica antes, se podría emitir más temprano con la semana completa.

**D3. Despacho programado**
- **Hoy suponemos:** el de un día se publica la víspera, así que el del lunes está listo el domingo (`src/data_pipeline.py`, `despacho_programado`).
- **Pregunta:** ¿a qué hora se publica el despacho programado (`GeneProgDesp`)? ¿Estaría listo para emitir el lunes temprano?
- **Si la respuesta es distinta:** si no está a tiempo, no sirve la opción del lunes.

**D4. Ofertas de precio**
- **Hoy suponemos:** las ofertas (`PrecOferDesp`) se conocen con el mismo rezago que el precio.
- **Pregunta:** la CREG 006 de 2009 permite publicar las ofertas desde el mes siguiente, pero en la API aparecen con ~3 días de rezago. ¿Desde qué fecha se publican así? ¿Cómo se publicaban antes?
- **Si la respuesta es distinta:** son 3 de las 14 variables del modelo. Si se publican más tarde, hay fuga de información en la evaluación.

**D5. Versiones del precio y cuándo queda firme**
- **Hoy suponemos:** un pronóstico se califica cuando la demanda de su semana está completa, con la versión del precio vigente ese día, y no se recalifica después (`src/semanal.py`, `calificar`). En 2024 la diferencia semanal entre TX1 y la versión vigente llegó a 45 %.
- **Pregunta:** ¿qué versiones tiene el precio (TX1, TX2…), cuándo se publica cada una y en qué fecha queda firme?
- **Si la respuesta es distinta:** hay que calificar con la versión firme, o esperar a que salga.

**D6. Datos tal como se publicaron**
- **Hoy suponemos:** la evaluación usa los valores ya revisados. Solo desde el 5 de noviembre de 2026 hay copias de lo publicado en cada emisión (`registro/snapshots/`).
- **Pregunta:** ¿se pueden obtener las series tal como estaban publicadas en cada fecha pasada, sobre todo hidrología y ofertas? ¿El calendario de versiones de SIMEM (`24914F`) sirve para eso?
- **Si la respuesta es distinta:** si se pueden obtener, se rehace la evaluación sin el sesgo de las revisiones.

## E. Cambios de régimen

**E1. Fechas del período de riesgo**
- **Hoy suponemos:** el modelo no distingue los períodos de riesgo.
- **Pregunta:** ¿en qué fechas exactas empezó y terminó cada período de riesgo de desabastecimiento desde 2010?
- **Si la respuesta es distinta:** con esas fechas se mide el modelo dentro y fuera de esos períodos.

**E2. Formación del precio hoy**
- **Hoy suponemos:** las ofertas hidráulicas reflejan la expectativa de los agentes.
- **Pregunta:** si una curva regulada fija las ofertas hidráulicas, ¿siguen siendo informativas para anticipar el precio?
- **Si la respuesta es distinta:** puede que esas variables dejen de significar lo mismo y haya que quitarlas o reentrenar solo con datos posteriores a septiembre de 2026.

**E3. Otros cambios regulatorios**
- **Hoy suponemos:** la historia 2010–2026 se trata como un único régimen.
- **Pregunta:** ¿qué otros cambios regulatorios desde 2010 alteraron el precio de bolsa? ¿Hay alguno previsto?
- **Si la respuesta es distinta:** se marcan quiebres en la historia y se evalúa entrenar con menos años.

## F. Cómo calculamos cada dato

**F1. Salto de `AporEnerMediHist` en 2022**
- **Hoy suponemos:** la media histórica de aportes es comparable en toda la serie.
- **Pregunta:** ¿por qué `AporEnerMediHist` salta cerca de 30 % a finales de 2022? ¿Cambió el método, entraron ríos nuevos como los de Ituango, o se recalcula la serie hacia atrás?
- **Si la respuesta es distinta:** dos variables de aportes (`aportes_pct_media` y `aportes_pct_media_4s`) cambian de escala en 2022 y habría que ajustarlas.

**F2. Demanda incompleta en los días recientes**
- **Hoy suponemos:** si la demanda de un día es menor que el 80 % de la generación, está incompleta. Se escala hasta la generación y esa semana no se califica (`src/data_pipeline.py`, `completar_demanda`). Por ejemplo, el 1 y el 2 de noviembre de 2026 había 60 GWh de demanda frente a ~220 GWh generados, con las 24 horas presentes.
- **Pregunta:** ¿es normal que la demanda (`DemaCome`) de los últimos días venga incompleta? ¿En cuántos días se completa?
- **Si la respuesta es distinta:** cambian la regla de corrección y el plazo para calificar.

**F3. Relación entre demanda y generación**
- **Hoy suponemos:** la demanda comercial es de 1,00 a 1,05 veces la generación, y por eso la generación sirve para completar la demanda.
- **Pregunta:** ¿`DemaCome` incluye las exportaciones y las pérdidas? ¿Qué diferencia esperable hay entre demanda comercial y generación total?
- **Si la respuesta es distinta:** hay que ajustar el factor de corrección.

**F4. Precio de oferta**
- **Hoy suponemos:** se promedia `PrecOferDesp` por hora y se pondera por la capacidad efectiva neta (`CapEfecNeta`) de cada recurso (`oferta_y_utilizacion`).
- **Pregunta:** ¿es correcta esa forma de calcular el precio de oferta del parque, o sería mejor ponderar por la disponibilidad declarada?
- **Si la respuesta es distinta:** se recalculan las 3 variables de oferta.

**F5. Qué plantas son térmicas**
- **Hoy suponemos:** son térmicas las de tipo `TERMICA` o `COGENERADOR` en el listado de recursos de hoy. Las plantas retiradas cuentan como térmicas si reportaron consumo de combustible (`clasificar_recursos`, `data/processed/clasificacion_recursos.csv`).
- **Pregunta:** ¿hay un listado histórico de recursos con su tipo? ¿Está bien contar los cogeneradores como térmicos?
- **Si la respuesta es distinta:** se reclasifica y se recalcula la oferta térmica.

**F6. Duplicados en `CapEfecNeta`**
- **Hoy suponemos:** las filas repetidas en enero de 2010 y 2011 (TBQ3, TBQ4, TGJ1, TYP1, TMB1) son duplicados y se eliminan.
- **Pregunta:** ¿esas filas repetidas de `CapEfecNeta` son duplicados, o representan algo distinto?
- **Si la respuesta es distinta:** el efecto medido es despreciable (MAE de 54,30 a 54,34), así que solo es para documentarlo.

**F7. Nivel del embalse**
- **Hoy suponemos:** `PorcVoluUtilDiar` del Sistema es el volumen útil agregado del SIN, y se toma su valor del domingo.
- **Pregunta:** ¿`PorcVoluUtilDiar` para el Sistema es el indicador correcto del embalse agregado? ¿Corresponde al cierre del día?
- **Si la respuesta es distinta:** se ajustan las dos variables de embalse y la alerta de embalse bajo 45 %.

**F8. Convención horaria**
- **Hoy suponemos:** `Hour01` es la hora de 00:00 a 01:00 y `Hour24` la de 23:00 a 24:00, en hora de Colombia (`src/xm_client.py`, `a_horario`).
- **Pregunta:** ¿`Hour01` corresponde al período de 00:00 a 01:00, en hora local?
- **Si la respuesta es distinta:** cambian el último día de la semana y el pico horario.

## G. Información que no tenemos

**G1. Datos que anticipen saltos de precio**
- **Hoy suponemos:** solo hay datos públicos de la API de XM y el ONI de NOAA. Con ellos la cota cubre ~70 % de las semanas de salto, frente a una meta de 85 %.
- **Pregunta:** ¿existen el pronóstico de aportes, los mantenimientos programados, las indisponibilidades previstas o el planeamiento operativo? ¿Son públicos y tienen historial?
- **Si la respuesta es distinta:** es la vía más clara para mejorar en las semanas de salto.

## H. Validación y siguiente paso

**H1. Evidencia necesaria**
- **Hoy suponemos:** 26 semanas de pronósticos congelados (desde el 5 de noviembre de 2026) para decidir sobre el modelo candidato.
- **Pregunta:** ¿cuántas semanas de pronósticos registrados necesitarían para confiar en el modelo?
- **Si la respuesta es distinta:** cambia la fecha de la decisión.

**H2. Revisión por XM**
- **Pregunta:** ¿quién de XM revisaría los resultados y con qué frecuencia? ¿Pueden contrastar nuestras series con Sinergox, como pide la propuesta?

**H3. Publicación**
- **Pregunta:** ¿hay restricciones para publicar? El repositorio y el tablero usan el nombre del caso XM–UNAL. ¿Cómo debe presentarse?

---

## Si el tiempo alcanza para pocas

1. ¿Se calcula la garantía en las semanas con intercambio, ahora que las exportaciones son intermitentes? (A1)
2. ¿Qué precio entra en la garantía y con qué fórmula? (B1 y B2)
3. ¿Qué estimación usan hoy y qué tan buena es? (A3)
4. ¿Cuánto cuesta equivocarse en cada dirección? (B5)
5. ¿Qué día y a qué hora debe estar el pronóstico, y cuál es el rezago oficial? (D1 y D2)
6. ¿Siguen siendo informativas las ofertas con las reglas del período de riesgo? (E2)

## Hoja de respuestas

Para anotar en la reunión. La columna **Archivo** indica qué revisar después de la respuesta.

| ID | Dato por confirmar | Supuesto actual | Archivo | Respuesta de XM |
|---|---|---|---|---|
| A1 | Vigencia de la garantía | Se calcula cada semana | `README.md` | |
| A3 | Estimación actual | Ingenuo | `src/evaluation.py` | |
| B1 | Fórmula de la garantía | Cantidad × precio | — | |
| B2 | Precio de la garantía | `PrecBolsNaci` | `src/xm_client.py` | |
| B4 | Periodo y momento de constitución | Lunes a domingo | `src/data_pipeline.py` | |
| B5 | Costo de quedarse corto frente a pasarse | Cota al 90 % | `src/config.py` | |
| B6 | Error aceptable | Sin umbral | `src/config.py` | |
| C1 | Ponderación | Demanda nacional | `src/data_pipeline.py` | |
| C4 | Serie de precio | `PrecBolsNaci` | `src/xm_client.py` | |
| D1 | Hora de la decisión | Miércoles | `README.md`, `correr_semanal.bat` | |
| D2 | Rezago oficial por serie | ~3 días (precio, demanda, ofertas, generación); 1 día (hidrología) | `src/data_pipeline.py` (`DICCIONARIO`) | |
| D3 | Hora del despacho programado | La víspera | `src/data_pipeline.py` | |
| D4 | Publicación de ofertas | Mismo rezago que el precio | `src/data_pipeline.py` | |
| D5 | Versión firme del precio | Vigente al calificar | `src/semanal.py` | |
| D6 | Datos tal como se publicaron | No disponibles | `registro/snapshots/` | |
| E1 | Fechas del período de riesgo | No se usan | — | |
| E2 | Utilidad de las ofertas hidráulicas | Informativas | `src/config.py` | |
| F1 | Salto de `AporEnerMediHist` | Serie comparable | `src/data_pipeline.py` | |
| F2 | Plazo para que la demanda se complete | Se escala si < 80 % de la generación | `src/data_pipeline.py` | |
| F3 | Demanda frente a generación | 1,00–1,05 | `src/data_pipeline.py` | |
| F4 | Ponderación de la oferta | Capacidad efectiva neta | `src/data_pipeline.py` | |
| F5 | Clasificación térmica | Listado actual + combustible | `data/processed/clasificacion_recursos.csv` | |
| F6 | Duplicados de `CapEfecNeta` | Duplicados | `src/data_pipeline.py` | |
| F7 | Indicador de embalse | `PorcVoluUtilDiar`, cierre del domingo | `src/data_pipeline.py` | |
| F8 | Convención horaria | `Hour01` = 00:00–01:00 | `src/xm_client.py` | |
| G1 | Datos que anticipen saltos | No existen | — | |
| H1 | Semanas de validación | 26 | `src/config.py` | |

## Qué conviene llevar

- La [ficha técnica](../FICHA_TECNICA.md), de una página.
- El tablero, abierto en el panel de métricas.
- La [auditoría](AUDITORIA.md), por si preguntan qué tan confiables son las cifras.
- Una aclaración: es un prototipo académico, sin validar para fijar garantías.
