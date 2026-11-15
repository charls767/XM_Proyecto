# Cuarta auditoría: revisión rigurosa por partes

**Fecha:** 15 de noviembre de 2026 · **Alcance:** rama `app-streamlit`, commit `5aa58e2`, las 13 partes del proyecto · **Método:** solo lectura. Las corridas que escriben archivos se hicieron en una copia exacta del commit (`git archive 5aa58e2`) en el scratchpad. El repositorio no cambió: `git status` vacío antes y después. · **Complementa:** [AUDITORIA.md](AUDITORIA.md), [AUDITORIA_2026-11-10.md](AUDITORIA_2026-11-10.md) y [AUDITORIA_2026-11-15.md](AUDITORIA_2026-11-15.md).

## 1. Veredicto

**Las cifras que se presentan son confiables.**

- E12, E14, E15 y E16 se reproducen con diferencia exactamente 0.
- No hay fugas de información: el embargo y la cota se comprobaron con filas concretas.
- La ventaja del modelo registrado sobre la regla de XM (115.3 → 98.3, p = 4×10⁻⁵) resiste:
  - cambiar los rezagos de Newey-West;
  - la corrección de Holm;
  - cambiar la ponderación del precio.

No encontré nada crítico. Los problemas son de presentación y de operación:
- Un texto de la app atribuye al modelo registrado una cualidad que no tiene.
- La integración continua no ha corrido sobre esta rama.
- El `.bat` no ancla en git la calificación del registro a una semana.
- Hay documentación desfasada.
- Un supuesto regulatorio (que el precio es el nacional) puede no valer en el período de riesgo.

## 2. Tabla resumen

| Id | Parte | Severidad | Hallazgo | Auditoría previa |
|---|---|---|---|---|
| P10-1 | App | Medio | La página Garantía TIE dice que el modelo "casi elimina el sesgo", pero el registrado tiene sesgo −16.1 frente a −2.4 de la regla | Nuevo |
| P11-1 | CI | Medio | La integración continua solo corre en `main` y en PR: ningún commit de `app-streamlit` se ha probado en GitHub | Nuevo |
| P9-1 | Emisión | Medio | El `.bat` califica el registro a una semana, pero no incluye `registro/pronosticos.csv` en el commit: esa calificación queda sin anclar | Nuevo |
| P13-1 | Supuestos | Medio | La CREG 101 127 (vigente en el período de riesgo) usa para exportación el máximo entre el precio de bolsa TIE y otros dos precios; SUPUESTOS no lo menciona al elegir el precio nacional | Nuevo (relacionado con PREGUNTAS 6) |
| P12-1 | Documentos | Medio | El README conserva secciones del tablero y del candidato del registro a una semana; la estructura no lista `semanal_tie.py`, `resultados_app.py`, `app/` ni los documentos nuevos | Residuo de M2 (15-nov) |
| P12-2 | Documentos | Bajo | SUPUESTOS dice que solo se usa sábado a martes de s, pero el candidato usa la hidrología hasta el jueves; además, la fila del pronóstico a una semana lo llama "modelo registrado" | Nuevo |
| P9-2 | Emisión | Bajo | El viernes en la mañana el precio del martes puede no estar publicado: el modelo cae a respaldo y el candidato no se calcula | Nuevo |
| P10-2 | App | Bajo | Las páginas Estrés, Movimientos y Pronóstico actual solo muestran el modelo a una semana; ninguna muestra el pronóstico TIE vigente | Nuevo |
| P11-2 | Tests | Bajo | Los tests de la emisión TIE reescriben `data/processed/semanal_tie.parquet` en el repositorio | Nuevo |
| P11-3 | Tests | Bajo | `test_emision_se_reconstruye_desde_el_snapshot` quedará omitido para siempre: el registro a una semana terminó en respaldo | Nuevo |
| P11-4 | Tests | Bajo | Sin tests para `calificar` del registro TIE, el respaldo, la vigilancia, la falla del candidato, `resultados_app.py` y el `.bat` | Nuevo |
| P8-1 | Trazabilidad | Bajo | La corrida de E16 que dejó los resultados del commit se hizo con cambios sin guardar (`cambios_sin_guardar: true`) | Nuevo |
| P9-3 | Registro | Bajo | Si en el futuro se agrega otra columna sellada, las huellas de las filas anteriores cambiarían; `semanal.py` tiene un mecanismo para eso (`SELLADAS_DESDE_CMG`) y `semanal_tie.py` no | Nuevo |

Estado de la auditoría del 15 de noviembre: A2, M1, B1, B2 y B3 siguen corregidos (verificados abajo). A1 sigue mitigado. M2 quedó corregido a medias (P12-1). M3, M4, B4 y B5 siguen como se aceptaron.

### Estado de las correcciones (mismo día)

| Id | Estado | Qué se hizo |
|---|---|---|
| P10-1 | **Corregido** | La página Garantía TIE calcula la mejora y el sesgo del periodo elegido a partir de los datos y dice que el modelo se queda corto más que la regla |
| P11-1 | **Corregido** | `.github/workflows/pruebas.yml` también corre con cada push a `app-streamlit` |
| P9-1 | **Corregido** | El `.bat` incluye `registro\pronosticos.csv` en el `git add` y en el commit |
| P13-1 | **Corregido** | SUPUESTOS tiene la sección "Riesgo conocido"; la página Garantía TIE muestra el aviso |
| P12-1 | **Corregido** | README: secciones del tablero y de los candidatos a una semana actualizadas; estructura con `semanal_tie.py`, `resultados_app.py`, `app/` y los documentos nuevos. Ficha sin menciones al tablero y con los dos registros |
| P12-2 | **Corregido** | SUPUESTOS: información disponible con la hidrología del candidato; el pronóstico a una semana ya no figura como registrado |
| P9-2 | **Corregido** | README, ficha y `.bat` indican emitir el viernes después de las 20:00 y explican por qué |
| P10-2, P11-2, P11-3, P11-4, P8-1, P9-3 | Abiertos (Bajo) | Sin cambios |

## 3. Hallazgos por parte

### Parte 1. Datos y caché

Sin hallazgos nuevos.

- Las 16 series tienen 203 meses en caché. Solo hay un mes vacío: `oferta/2026-11`, porque XM no ha publicado las ofertas de noviembre (la API devuelve 0 filas el 15-nov).
- `combustible` tiene 255 pares (fecha, recurso) repetidos en los últimos 3 meses. No es un error: son varios combustibles por planta, por ejemplo TGJ1 el 1-sep con dos valores. Solo se usa para clasificar plantas térmicas (`valor > 0`).
- Persiste B8 de la auditoría del 10 de noviembre: la regla de no sobrescribir compara días, no plantas.

### Parte 2. Tablas semanales

Sin hallazgos.

### Parte 3. Variables

Sin hallazgos.

### Parte 4. Modelos

Sin hallazgos.

### Parte 5. Backtest y fugas

Sin hallazgos.

### Parte 6. Calibración

Sin hallazgos nuevos. M4 (cota ancha) sigue aceptado.

### Parte 7. Evaluación estadística

Sin hallazgos. La ventaja del candidato sobre el registrado (p = 0.022) no resistiría una corrección por las 6 variantes entre las que se eligió. Ya está documentado en EXPERIMENTOS.

### Parte 8. Reproducibilidad

**P8-1 (Bajo). Resultados de E16 generados con cambios sin guardar.**
- Evidencia: el último registro de `results/corridas.jsonl` es `{"comando": "e16", "commit": "6a0e2f0", "cambios_sin_guardar": true}`.
- Impacto: ninguno en las cifras. La réplica en la copia limpia de `5aa58e2` da diferencia 0. Lo que se pierde es trazabilidad: el commit anotado no es el del código que produjo el archivo.
- Corrección: correr los experimentos después de hacer commit del código.

### Parte 9. Emisión y registros

**P9-1 (Medio). La calificación del registro a una semana no queda anclada.**
- Evidencia: `src/semanal_tie.py` llama `semanal.calificar(...)`, que modifica `registro/pronosticos.csv`. En cambio, `correr_semanal.bat` (líneas `git add` y `git commit`) solo incluye `registro\pronosticos_tie.csv registro\snapshots_tie results\app`.
- Impacto: después de cada emisión, `pronosticos.csv` queda modificado sin commit. Las huellas no se rompen, porque las columnas de calificación no están selladas, pero la calificación no queda anclada en git.
- Corrección: agregar `registro\pronosticos.csv` al `git add` y al `git commit` del `.bat`.

**P9-2 (Bajo). Depende de la hora del viernes.**
- Evidencia: el jueves 12 a las 20:10, la caché llegaba al precio del lunes 9. El domingo 15 a las 17:47 llegaba al jueves 12. El rezago es de unos 3 días, y el precio del martes sale hacia el viernes en la tarde o la noche. La hidrología del jueves sale el viernes.
- Impacto: emitir el viernes temprano puede dar *respaldo* (sin el sábado a martes) y omitir el candidato ("Candidato sin calcular"). El backtest supone que ambos están disponibles.
- Corrección: indicar en el README "viernes después de las 20:00". Opcionalmente, que el `.bat` avise si `precio` no llega al martes de s.

**P9-3 (Bajo). Agregar columnas selladas cambiaría las huellas anteriores.**
- Evidencia: `semanal_tie.huella` sella la lista fija `SELLADAS`.
- Impacto: hoy ninguno, porque el registro está vacío. Si mañana se sella una columna nueva, todas las filas anteriores fallarían `verificar_registro()`.
- Corrección: copiar el patrón de `semanal.SELLADAS_DESDE_CMG`, que sella las columnas nuevas solo en las filas que las tienen.

### Parte 10. Resultados y app

**P10-1 (Medio). Un texto de la app no aplica al modelo registrado.**
- Evidencia: `app/streamlit_app.py:239` dice: "Un Ridge con esos días y corrección de sesgo reduce ~15 % y casi elimina el sesgo a quedarse corto".
- Medido en 2018–2026:
  - el registrado tiene sesgo **−16.1**;
  - la regla, **−2.4**;
  - la frase solo vale para la variante con ofertas (`Ridge14+parcial_Duan`, −7.5 frente a −23.6 sin Duan);
  - en las últimas 52 semanas el registrado tiene −19.1.
- Impacto: la página atribuye al modelo registrado una mejora de sesgo que no tiene. Se queda más corto que la regla.
- Corrección: decir que el modelo reduce el error ~15 % pero se queda corto en promedio más que la regla (−16 frente a −2), o calcular el sesgo en la página a partir de los datos.

**P10-2 (Bajo). Tres páginas siguen centradas en el modelo a una semana.**
- Evidencia: `estres()`, `movimientos()` y `explicacion()` usan `P` (a una semana) y el registro a una semana. La explicación por variables es del Ridge 14 a una semana, con semana base 26-oct.
- Impacto: la portada presenta la garantía TIE, pero los episodios de estrés, los movimientos grandes y el pronóstico actual hablan de otro modelo.
- Corrección: rotular esas páginas como "pronóstico a una semana" o agregarles la versión TIE (`predicciones_tie.parquet` ya tiene lo necesario para Estrés y Movimientos).

### Parte 11. Tests y CI

**P11-1 (Medio). La integración continua no ha probado esta rama.**
- Evidencia: `.github/workflows/pruebas.yml` se dispara con `push: branches: [main]` y `pull_request`. `gh run list --branch app-streamlit` no devuelve corridas. La última corrida exitosa es del merge del PR #3 (13-nov).
- Impacto: 8 commits sin verificar en un entorno limpio (Linux, con instalación desde `requirements.txt`). En local pasan 79 y se omite 1.
- Corrección: abrir un PR de `app-streamlit` a `main`, o agregar la rama al disparador.

**P11-2 (Bajo).** `test_semanal_tie.test_emision_en_seco...` y `test_tie` llaman a `dp.tabla_tie(recalcular=True)`, directamente o a través de `emitir`, y reescriben `data/processed/semanal_tie.parquet`. Con la misma caché el contenido no cambia, pero un test no debería escribir en archivos versionados. Corrección: `monkeypatch` de `dp.PROCESSED` hacia `tmp_path`.

**P11-3 (Bajo).** `tests/test_operacion.py:115` se omite porque la última emisión a una semana fue de respaldo. Ese registro ya no emite, así que el test no volverá a correr. Corrección: fijar la prueba a la emisión del 5 de noviembre (estado *normal*) en vez de la última.

**P11-4 (Bajo).** No hay tests para:
- `semanal_tie.calificar` (error del candidato, `cubierto`);
- el camino de respaldo;
- la activación de *vigilancia*;
- la falla del candidato;
- `resultados_app.main()`;
- el `.bat`.

### Parte 12. Coherencia entre documentos y código

**P12-1 (Medio). El README conserva secciones del planteamiento anterior.**
- `README.md:105`, `:118` y `:132` remiten al "tablero", que ya no se genera.
- `README.md:130` describe el candidato del registro a una semana, que ya no emite.
- La estructura (`README.md:196-230`):
  - no lista `src/semanal_tie.py`, `src/resultados_app.py`, `app/`, `docs/SUPUESTOS.md`, `docs/PREGUNTAS_XM.md` ni las auditorías del 15 de noviembre;
  - dice "E1–E11" (son E0–E16);
  - mantiene `dashboard/`.
- `FICHA_TECNICA.md:36` y `:59` hablan del "tablero"; `:65` dice que la evidencia independiente es `registro/pronosticos.csv` desde el 5-nov (ahora es el registro TIE desde el 20-nov).

**P12-2 (Bajo). SUPUESTOS no está al día con el candidato.**
- En `docs/SUPUESTOS.md`, la fila "Información disponible" dice "semanas completas hasta s-1, y de sábado a martes de s". El candidato usa la hidrología de sábado a jueves.
- La fila "Pronóstico a una semana" dice "Es el modelo registrado desde el 5 de noviembre": ya no emite.

### Parte 13. Supuestos regulatorios

Lo que SUPUESTOS describe de la regla coincide con el material de XM:
- semana de sábado a viernes;
- cálculo el viernes para s+2 con los precios de s-1;
- la fórmula Σ MXT × (PM − CEE);
- ajuste 1 con 5 días reales;
- ajuste 2 con TX2;
- la división en dos montos cuando el precio supera el de escasez, cuya suma sigue dependiendo de PM.

**P13-1 (Medio). El precio del período de riesgo.**
- `docs/PREGUNTAS_XM.md` (tabla inicial) registra que la CREG 101 127 de 2026 considera, para los cargos de exportación, el **máximo** entre:
  - el precio de bolsa TIE;
  - el precio de la planta más cara más el costo de arranque y parada;
  - el costo marginal del importador.
- SUPUESTOS lista "si la CREG 101 127 cambió este artículo" como pendiente, pero no advierte que **ya hay un indicio** de que, mientras rija (hasta el 31 de mayo de 2027), el precio de exportación puede no ser el de bolsa.
- Impacto: no cambia el backtest de 2018 a agosto de 2026. Pero la evaluación de las semanas del período de riesgo, y la utilidad del registro mientras rija la norma, dependen de este punto. Hoy no hay exportaciones.
- Corrección: agregarlo como riesgo explícito en SUPUESTOS y en la página Garantía TIE.

**Sensibilidad de los supuestos del proyecto**

| Supuesto | ¿Es de la regla? | Sensibilidad medida |
|---|---|---|
| Promedio horario simple (máxima transferencia constante) | No, aproximación | Con el precio ponderado por demanda como objetivo, la diferencia media es 1.9 % y la mejora del modelo se mantiene en 14.8 %. Con solo las horas de punta (18–21 h), la diferencia es 19.6 % y la mejora baja a 12.5 %. La conclusión resiste. |
| Precio nacional en COP frente a "Precio Medio Total" TIE en centUSD/kWh | No | No verificable sin las series de transferencias TIE. La tasa de cambio agrega a 3 semanas un error que el modelo no cubre. |
| Fórmula de exportación igual a la de importación | No | No verificable: las diapositivas de exportación son capturas de Excel. |
| Calificación con TX2 | Sí (ajuste 2) | La emisión califica 3 semanas después, cuando el objetivo ya tiene TX2 o una versión posterior. Es coherente con SUPUESTOS. |

## 4. Verificado sin problemas

| Revisión | Evidencia |
|---|---|
| Copia limpia y repositorio intacto | `git archive 5aa58e2`; `git status --short` = 0 líneas antes y después |
| pydataxm frente a la consulta directa | Precio del 1 al 7 de octubre de 2026: diferencia 0 entre los dos métodos y frente a la caché |
| Rezago real | El domingo 15 a las 17:47: precio hasta el 12-nov (3 días), hidrología hasta el 14-nov (1 día), ofertas hasta el 31-oct |
| Tabla TIE | Reconstruida en la copia, es idéntica al parquet del repositorio (879 semanas, diferencia 0); todos los índices son sábados y consecutivos |
| Semana del 1-feb-2025 | 168 horas, precio 646.5423 = tabla; objetivo del 22-feb 242.0521 = tabla; sábado a martes (96 h) 528.0194 = tabla; martes rel −0.25338 = tabla; aportes de sábado a jueves 1.07115 = tabla; embalse −0.01345 = tabla |
| `PERIODO_SEMANA` | Vuelve a `W-SUN` después de `tabla_tie` |
| Tabla a una semana | Semana del 3-feb-2025 ponderada por demanda: 652.6025 = tabla; `precio_sig` = precio de la semana siguiente; 1 semana con demanda estimada (2-nov-2026) |
| Variables TIE | 12 (11 de s-1 + `parcial_rel`), sin ENOS ni térmica; candidato +3; y = log(P<sub>+3</sub>/P) con error 0 |
| Duan | El factor (1.05735 en una prueba) sale solo del entrenamiento; el pronóstico no depende del tamaño del bloque de prueba |
| Embargo (fila concreta) | Bloque del 20-ene-2024, emisión el viernes 2-feb-2024. La última fila de entrenamiento es del 30-dic-2023 y su objetivo termina el 26-ene, conocido el 30-ene. |
| Etiquetas E16 | `semana_objetivo` = base + 3 semanas; `fecha_emision` siempre viernes; mismas semanas para todos los modelos; entrenamiento creciente |
| Cota | Recalculada = guardada; alterar los reales de las 2 filas anteriores no cambia la cota de la última (rezago 3) |
| Cobertura | Registrado: 90.5 % en total; desarrollo 90.9, selección 87.9, final 93.8; semanas con cambio ≥ 25 % (239): 82.8 %; embalse < 45 % (43): 93.0 %; exceso 85 % |
| Regímenes | En las semanas de salto el registrado erra 153 frente a 197 de la regla; con embalse bajo, 108 frente a 144 (p = 0.07) |
| Diebold-Mariano | n = 461, 5 rezagos (horizonte 3 pide ≥ 2). Registrado frente a la regla: p de 1.6×10⁻⁴ a 4.3×10⁻⁵ con 2, 5, 10 y 20 rezagos; IC bootstrap [−26.0, −9.2] |
| Corrección por búsqueda | Holm sobre las 7 comparaciones de E16 contra la regla: todas < 0.05; registrado 0.0003 |
| Reproducción | E16, E15, E14 y E12 vueltos a correr en la copia: diferencia 0 en los resúmenes y en `E16_ancho` y `E14_ancho` (14, 27, 5 y 7 s) |
| Calendario | `semanas("2025-02-14")` = (8-feb, 1-feb, 22-feb), igual al ejemplo de XM; cualquier día de la semana da lo mismo |
| Emisión en seco del 13-nov | Normal, sin motivos; pronóstico 397.46, cota 710.12, regla 388.94, candidato 391.72; 52 semanas: MAE 119.9 frente a 127.0, cobertura 88.5 %, sesgo −4.2 % (p = 0.54); `reproducir()` exacto |
| Huella | Dos filas, con y sin candidato y con parcial nulo: `verificar_registro()` = [] tras escribir y leer |
| Cifras de la app | Desde `predicciones_tie.parquet`: registrado 98.27, regla 115.29 (= E16); últimas 52: 119.9 frente a 127.0; el p de la app (0.40) = `evaluation.diebold_mariano` (0.3993) |
| Tests | En la copia: 79 pasan, 1 se omite (P11-3) |
| Auditoría previa | A2 (reproducción), B1 (7 páginas), B2 (emisión de extremo a extremo) y B3 (series atrasadas) siguen corregidos |

## 5. No verificable

- **El precio exacto de la fórmula TIE** (nacional o liquidación TIE en USD, ponderado por energía transferida): no hay series de transferencias horarias TIE en la caché.
- **La fórmula de exportación y el efecto de la CREG 101 127** sobre el artículo 23: el material de XM es de 2025 y las diapositivas de exportación son imágenes.
- **La hora de publicación del precio y la hidrología el viernes**: solo hay observaciones sueltas (jueves 20:10 y domingo 17:47).
- **El despliegue en Streamlit Cloud** con `app/requirements.txt`: depende de la versión de Python que elija la plataforma. En local abre.
- **La integración continua en Linux** para los commits de la rama, porque no se ha ejecutado (P11-1).

## 6. Guiones

Guardados en el scratchpad de la sesión (no en el repositorio):

| Script | Partes |
|---|---|
| `p1_3.py` | 1 a 3: caché, tabla TIE reconstruida, semana del 1-feb-2025, variables |
| `p4_7.py` | 4 a 7: Duan, embargo con fila concreta, cota, cobertura por régimen, DM, Holm |
| `p9_13.py` | 9 y 13: calendario, emisión en seco, huella con nulos, sensibilidad a la ponderación |

Comandos:

```bash
git archive --format=tar 5aa58e2 -o repo.tar && tar -xf repo.tar -C copia
```

```bash
cd copia && ..\..\XM_Proyecto\.venv\Scripts\python.exe src\experimentos.py e16
```

```bash
cd copia && ..\..\XM_Proyecto\.venv\Scripts\python.exe -m pytest -q tests -rs
```

```bash
gh run list --branch app-streamlit --limit 3
```
