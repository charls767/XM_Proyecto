# Preguntas para validar el proyecto con XM

Guía para la reunión con XM. Las preguntas van en orden de impacto: las primeras pueden cambiar qué hay que pronosticar, las últimas solo ajustan detalles.

**Lectura normativa sin validar:** lo citado sobre la CREG 101 127 y la Resolución 40308 viene de una revisión rápida de los textos públicos, y en el segundo caso del proyecto de resolución, no de su versión final. Sirve para formular las preguntas, no como interpretación oficial.

## Lo que cambió y hay que entender primero

| Hecho público | Por qué le importa al proyecto |
|---|---|
| Desde el 7 de septiembre de 2026 no hay exportaciones por TIE a Ecuador; se activó el período de riesgo de desabastecimiento ([Portafolio](https://www.portafolio.co/energia/colombia-termina-suministro-de-energia-a-ecuador-exportaciones-por-mas-de-530-000-millones-quedaron-frenadas-503959)) | Sin intercambios, ¿hoy hay garantía que estimar? |
| La [CREG 101 127 de 2026](https://gestornormativo.creg.gov.co/gestor/entorno/docs/originales/Resoluci%C3%B3n_CREG_101_127_2026/) suspende el estatuto de 2014 hasta una resolución definitiva o el 31 de mayo de 2027. Regula las ofertas hidráulicas con una curva y limita las ofertas en el despacho ideal | La historia 2010–2026 del modelo se formó con otras reglas |
| Esa norma considera, para los cargos de exportación, el máximo entre el Precio de Bolsa TIE, el precio de la planta más cara más arranque y parada, y el costo marginal del importador | Tal vez la garantía no dependa del precio que pronosticamos |
| La Resolución 40308 de 2026 habilitó contratos bilaterales entre agentes privados ([proyecto](https://www.expreso.ec/uploads/files/2026/06/23/Exportaciones_Ecuador_Contratos_OAJ.pdf): las diferencias deben ser "respaldadas, prepagadas y recaudadas" por las partes) | La exposición, y quién la cubre, pudo cambiar |

**En nuestros datos:** la semana del 7 de septiembre el precio cayó de 932 a 593 COP/kWh y la oferta no térmica de 452 a 280 COP/kWh. En las 8 semanas desde entonces el modelo erró 60 COP/kWh, frente a 93 del ingenuo. Son pocas semanas, y la coincidencia no prueba que la causa sea el cambio de reglas.

## Primera respuesta recibida (noviembre de 2026)

Una persona de XM respondió 7 puntos. Es una guía, no la respuesta definitiva. La correspondencia con las preguntas de abajo es nuestra lectura.

| Tema | Respuesta | Preguntas | Qué hacemos |
|---|---|---|---|
| Qué se pronostica y para qué | Lo debe definir el proyecto | 1, 2, 3, 14 | Escribirlo como supuesto explícito del proyecto |
| Versiones del precio | TX1 y TX2: preliminares, cada día para los dos días anteriores. TXR y TXF: "finales", cada mes. TX3 en adelante: ajustes a facturas | 13, 18, 19, 24 | Calificar provisional con TX2 y definitivo con TXF (ver [auditoría](AUDITORIA.md), hallazgo 6) |
| Necesidad, costos y uso | No lo sabe; es decisión del proyecto o consulta al CRM de XM | 3, 4, 9, 10 | Supuesto del proyecto; consultar al CRM |
| Regla de la garantía | Consultar al CRM de XM | 5, 6, 7, 8 | Enviar al CRM |
| Disponibilidad de datos | Revisar las versiones TX y consultar al CRM | 16, 17, 32 | Enviar al CRM |
| Implicaciones regulatorias | Depende del proyecto; las implicaciones, al CRM | 20, 21, 22 | Enviar al CRM |
| Otras fuentes | SiMEM y el portal de XM son las fuentes públicas; lo demás, por el CRM | 28 | Explorar SiMEM |

**Qué sigue:**
- **El CRM de XM** es el canal formal para lo normativo. Prioridad: 6, 5, 9 y 21.
- **SiMEM** es una fuente que no hemos explorado. Buscar ahí mantenimientos, indisponibilidades y pronóstico de aportes (pregunta 28).
- **La demanda incompleta (24)** puede deberse a que los días recientes aún son preliminares. Es hipótesis.

---

## A. La necesidad real (lo primero)

**1. ¿Sigue vigente la necesidad con exportaciones en cero?** ¿Se está calculando alguna garantía hoy? ¿Bajo qué condiciones volvería a aplicar?
*Si la respuesta es no:* el caso de uso queda en pausa hasta que se reanuden, o se redefine.

**2. ¿Quién usaría este pronóstico y qué decisión concreta toma con él?** ¿XM como ASIC, el agente exportador o un generador?
*Define* el usuario, el formato y qué significa que sea útil.

**3. ¿Qué estimación se usa hoy, quién la hace y qué tan buena es?** ¿Se puede obtener su historial frente al valor real?
*Por qué:* comparamos contra "repetir el precio anterior", que quizá no es el rival real. Si la estimación actual ya es mejor, el modelo no aporta.

**4. ¿Qué problema concreto ha causado estimar mal?** ¿Hay episodios con recursos inmovilizados de más o garantías insuficientes, y con qué montos?
*Por qué:* la propuesta plantea ese costo, pero aún no tiene evidencia que lo respalde.

## B. La regla de la garantía

**5. ¿Cuál es la fórmula exacta y qué norma la rige hoy?** Cantidad × precio × factor, plazos, y si cambia con el régimen TIE, con contratos bilaterales o en período de riesgo.

**6. ¿Qué precio entra en el cálculo?** ¿Precio de bolsa nacional, Precio de Bolsa TIE o el máximo que indica el Anexo 3 de la CREG 101 127?
*Si no es el nacional:* la variable objetivo del modelo está equivocada. **Es la pregunta técnica más importante.**

**7. ¿Es garantía o prepago?** ¿Qué instrumento se usa, en qué moneda y con qué tasa de cambio?

**8. ¿Qué periodo cubre y cuándo se fija?** ¿Semanal? ¿Qué día y a qué hora debe estar constituida?

**9. ¿Cuánto cuesta equivocarse en cada dirección?** ¿Qué pasa si se queda corta (limitación, incumplimiento, multas)? ¿Cuánto cuesta inmovilizar de más?
*Decide:* el nivel de la cota (90 % es un supuesto nuestro), si se corrige el sesgo a quedarse corto y entre las dos variantes de cota.

**10. ¿Qué tolerancia de error sería aceptable?** En % o en COP/kWh, y en semanas de estrés.
*Por qué:* hoy el error típico es ~15 %, y sin un umbral no se puede decir si alcanza.

## C. Qué se debe pronosticar

**11. ¿La ponderación por demanda es la correcta?** Si la exposición depende de las horas en que se exporta, ¿debería ponderarse por la energía exportada?
*Por qué:* nuestra fórmula pondera por demanda nacional.

**12. ¿Cuál es la semana relevante?** ¿De lunes a domingo, u otro ciclo de liquidación?

**13. ¿Qué diferencia hay entre `PrecBolsNaci`, `PrecBolsNaciTX1`, `PrecTransBolsa` y `PPPrecBolsNaci`?** ¿Cuál usar para este fin?

**14. ¿Cuál es el horizonte útil?** ¿Una semana basta, o la decisión necesita más antelación?

## D. Cuándo está disponible cada dato

**15. ¿A qué hora y día debe estar el pronóstico?**
*Decide el modelo:*

| Si la decisión es… | Dato disponible | Modelo | Error 2018–26 (MAE) |
|---|---|---|---|
| Lunes temprano | Semana base hasta el viernes | Ridge 14 + despacho programado | 61 COP/kWh |
| Miércoles o después | Semana base completa, pero la semana objetivo ya empezó | Ridge 14 | 54 COP/kWh |

**16. ¿Cuál es el rezago oficial de cada serie?** Vemos unos 3 días en precio, demanda y ofertas por la API. ¿Es igual en otros canales, como Sinergox o archivos para agentes?

**17. ¿A qué hora se publica el despacho programado?** ¿Estaría listo para una emisión el lunes temprano? ¿Y las ofertas de precio, desde cuándo son públicas?

**18. ¿Qué versiones tiene el precio (TX1, TX2…) y cuándo queda firme?** Vimos diferencias semanales entre TX1 y la vigente de hasta 45 % en 2024.
*Define* cuándo calificar un pronóstico, y con qué versión.

**19. ¿Se pueden obtener los datos como estaban publicados en su momento?** Nuestra evaluación usa valores ya revisados.

## E. Cambios de régimen

**20. ¿Qué fechas exactas de activación y fin tuvo el período de riesgo?** ¿Cuántas veces se ha activado desde 2010?
*Permite* medir el modelo dentro y fuera de esos períodos.

**21. ¿Cómo cambia la formación del precio de bolsa en este período?** En su lectura, ¿las ofertas hidráulicas siguen siendo informativas si las fija una curva regulada?
*Por qué:* las ofertas son 3 de las 14 variables del modelo, y con esas reglas pueden dejar de significar lo mismo.

**22. ¿Qué otros cambios regulatorios desde 2010 alteraron el precio de bolsa?** ¿Hay alguno previsto?
*Permite* marcar quiebres estructurales, y saber si conviene entrenar con menos historia.

## F. Dudas sobre los datos

**23. ¿Por qué `AporEnerMediHist` salta cerca de 30 % a finales de 2022?** ¿Cambió el método, o entraron nuevos ríos como los de Ituango? ¿La serie se recalcula hacia atrás?

**24. ¿Es normal que la demanda reciente venga incompleta?** El 1 y 2 de noviembre de 2026 había 60 GWh frente a ~220 GWh generados, con las 24 horas presentes. ¿En cuántos días se completa?

**25. ¿Es correcto calcular el precio de oferta como lo hacemos?** Promediamos `PrecOferDesp` por hora y lo ponderamos por capacidad efectiva neta. ¿Sería mejor ponderar por disponibilidad declarada?

**26. ¿Existe un listado histórico de recursos?** Clasificamos térmico o no térmico con el listado de hoy, y por consumo de combustible para plantas retiradas.

**27. ¿Por qué `CapEfecNeta` repite filas en enero de 2010 y 2011?** Lo tratamos como duplicado. ¿Lo es?

## G. Información que no tenemos

**28. ¿Hay datos que anticipen saltos de precio?** Pronóstico de aportes, mantenimientos programados, indisponibilidades previstas o planeamiento operativo: ¿existen, son públicos y tienen historial?
*Por qué:* nuestra auditoría sugiere que el límite está en la información. La cota cubre solo ~70 % en las semanas de salto.

**32. ¿Cuándo se publica el costo marginal del despacho programado (`CostMargDesp`) y se revisa después?** En nuestra prueba (E12) es la variable que más mejora el pronóstico si se emite con la semana ya empezada. El martes 10 de noviembre de 2026 a las 21:19 todavía no estaba el del miércoles. ¿A qué hora queda publicado cada día? ¿Lo que muestra la API para días pasados es lo publicado entonces? ¿Por qué el precio de bolsa se separó más de él desde 2024?

## H. Validación y siguiente paso

**29. ¿Qué evidencia necesitarían para confiar en el modelo?** Tenemos pronósticos congelados desde el 5 de noviembre de 2026. ¿Cuántas semanas pedirían?

**30. ¿Quién de XM revisaría los resultados y con qué frecuencia?** ¿Pueden contrastar nuestras series con Sinergox, como pide la propuesta?

**31. ¿Hay restricciones para publicar?** El repositorio y el tablero usan el nombre del caso XM–UNAL. ¿Cómo debe presentarse?

---

## Si el tiempo alcanza para pocas

1. ¿Sigue vigente la necesidad con exportaciones en cero? (1)
2. ¿Qué precio entra en la garantía y con qué fórmula? (5 y 6)
3. ¿Qué estimación usan hoy y qué tan buena es? (3)
4. ¿Cuánto cuesta equivocarse en cada dirección? (9)
5. ¿A qué hora debe estar el pronóstico? (15)
6. ¿Qué cambió en la formación del precio con el período de riesgo? (21)

## Qué conviene llevar

- La [ficha técnica](../FICHA_TECNICA.md), de una página.
- El tablero, en la sección del panel de métricas.
- La [auditoría](AUDITORIA.md), por si preguntan qué tan confiables son las cifras.
- Una aclaración: es un prototipo académico, sin validar para fijar garantías.
