# Auditoría de la app: claridad y propósito

**Fecha:** 16 de noviembre de 2026 · **Alcance:** `app/streamlit_app.py`, los datos que lee (`results/app/`), `src/resultados_app.py`, el README y el tablero viejo. · **Criterio:** cada elemento tiene que tener un propósito claro y entenderse sin saber estadística.

## Qué se encontró

| # | Problema | Ejemplo | Qué se hizo |
|---|---|---|---|
| 1 | **Demasiadas páginas, con historias mezcladas** | 8 páginas. La portada contaba tres historias (exportación, bolsa y semana siguiente). "Episodios" y "Movimientos" tenían un selector para cambiar de historia | 6 páginas, una idea cada una. Crisis y saltos quedaron dentro de *Precio de bolsa* |
| 2 | **Palabras técnicas sin explicar** | s-1, s+2, Ridge, Huber, Duan, MAE, RMSE, CEE, TX2, "p = 0.08" | Lenguaje simple, glosario en *Cómo funciona* y los detalles técnicos en una sección plegable |
| 3 | **Textos que contradecían al modelo actual** | *Garantía TIE* decía que el costo marginal "no sirve aquí", y el modelo registrado lo usa desde E24. La metodología hablaba de "16 experimentos" y de un modelo sin costo marginal | Reescritos. El texto técnico describe el modelo vigente |
| 4 | **Una frase decía lo contrario de sus cifras** | "En el último año la ventaja es menor" junto a 97 frente a 122 | Se calcula con los datos de las últimas 52 semanas y dice si la diferencia es confiable |
| 5 | **Nombres de modelos imposibles de leer** | "Modelo registrado (sábado a martes + costo marginal mié-vie, con corrección de sesgo)" | *Regla actual de XM*, *Nuestro modelo*, *Modelo en prueba*. Las variantes tienen nombres descriptivos |
| 6 | **Valores p sin interpretar** | "p = 0.08" | "¿La mejora es real?": *Sí, es real* (p < 0.05), *Casi seguro* (p < 0.10) o *No se puede asegurar* |
| 7 | **Demasiadas columnas** | MAE, RMSE, error medio, sesgo, mejora y cobertura en todas las tablas | 5 columnas con ayuda al pasar el mouse: error promedio, error típico, cuánto mejor que la referencia, desvío y semanas bajo el techo |
| 8 | **Datos que se cargaban y no se usaban** | `contexto.parquet`, `ultimo.json` (explicación del modelo viejo), copias de `E14_*.csv` | Ya no se generan; `resultados_app.py` borra las copias viejas |
| 9 | **La página "Pronóstico actual" mezclaba dos registros** | La emisión TIE, el registro detenido a una semana y un aviso de respaldo del 12 de noviembre | Muestra el registro TIE y un ejemplo con los datos de hoy. El registro viejo quedó como sección plegable en *Extra* |
| 10 | **Tablero HTML abandonado** | `dashboard/` (plantilla y generador), que ya no se usaba | Eliminado, igual que sus menciones en el README |

## Cómo quedó la app

| Página | Pregunta que responde | Qué tiene |
|---|---|---|
| Inicio | ¿Qué problema se resuelve y qué tan bien? | La historia en 4 pasos, el error de la regla y el de nuestro modelo en los dos precios, y las 4 ideas más importantes |
| Precio de exportación | ¿Qué tan bien se adivina el precio del depósito? | Qué es, por qué es difícil, gráfico, tabla y lo aprendido; las variantes y la comparación con el precio nacional, en secciones plegables |
| Precio de bolsa | ¿Y el precio del mercado? ¿En las crisis? ¿Ve venir los saltos? | Gráfico con techo opcional, tabla, crisis y tabla de saltos con una frase que la explica |
| Pronóstico de esta semana | ¿Qué se registró y por qué? | El último registro (o cuándo empieza), un ejemplo con los datos de hoy y las barras que lo explican |
| Extra: la semana siguiente | ¿Qué tan lejos se llega con 13 modelos? | Tabla con una columna "Qué es" para cada modelo, gráfico y el registro detenido |
| Cómo funciona | ¿Cómo se hace y qué significa cada palabra? | 5 pasos, cómo se evita hacer trampa, glosario, y los detalles técnicos y supuestos en una sección plegable |

## Verificación

- Las 6 páginas abren sin errores: test `tests/test_app.py`, una prueba por página, y revisión en el navegador.
- Las cifras de la portada coinciden con el README: exportación 5.31 frente a 4.83; bolsa 115 frente a 94.
- La suite completa da 82 pasados y 1 omitido.

## Lo que no se cambió

- **Los cálculos y los modelos:** esta auditoría solo cambia cómo se presentan.
- **Los documentos técnicos** (`EXPERIMENTOS.md`, `SUPUESTOS.md` y las auditorías anteriores) siguen siendo técnicos; la app los resume. Las auditorías anteriores mencionan páginas que ya no existen; son registros históricos y no se editan.
