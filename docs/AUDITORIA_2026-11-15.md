# Tercera auditoría: garantía TIE, app y operación

**Fecha:** 15 de noviembre de 2026 · **Alcance:** rama `app-streamlit` en f4a99fc. Cubre E15, E16, `src/semanal_tie.py`, `src/resultados_app.py`, la app en Streamlit, los registros y la documentación. · **Complementa:** [AUDITORIA.md](AUDITORIA.md) (5 de noviembre) y [AUDITORIA_2026-11-10.md](AUDITORIA_2026-11-10.md).

## Veredicto

**La metodología de E16 está bien hecha.** Se reproduce exactamente, no usa información futura y no es optimista por la versión de los datos. Hay dos debilidades reales:

1. **En el último año el modelo TIE se queda corto y su ventaja frente a la regla de XM deja de ser significativa.** Es el mismo patrón que la auditoría del 10 de noviembre encontró en el modelo a una semana.
2. **Lo que se presenta no está alineado con lo que se registra.** La app y la ficha técnica abren con el pronóstico a una semana, pero desde hoy se registra el de la garantía TIE. Además, el snapshot TIE no permite reproducir el pronóstico.

Las cifras salen de la caché local al 12 de noviembre de 2026 (precio) y de `results/E16_ancho.parquet`.

## Estado de los hallazgos (actualizado el mismo 15 de noviembre)

| # | Estado | Qué se hizo |
|---|---|---|
| A1 | **Mitigado** | La emisión TIE vigila las últimas 52 semanas calificadas: error frente a la regla, cobertura y sesgo (HAC). Si alguno falla, el estado pasa a *vigilancia*. La app y la ficha muestran el último año (120 frente a 127, p = 0.40) junto a 2018–2026. El sesgo en sí no se corrigió: es un rasgo del periodo. |
| A2 | **Corregido** | El snapshot guarda media y escala, coeficientes, factor de Duan y margen de la cota. `semanal_tie.reproducir()` reconstruye pronóstico y cota exactos (test). |
| M1 | **Corregido** | La portada abre con la regla de XM frente al modelo registrado; el pronóstico a una semana queda como complemento. Metodología reescrita. |
| M2 | **Corregido** | README, ficha técnica y AUDITORIA.md actualizados. El README explica cómo abrir la app en vez del tablero viejo. |
| M3 | Abierto | Solo se confirma observando la hora de publicación en varios días, o preguntando al CRM de XM. No afecta al modelo TIE. |
| M4 | Aceptado | La cota ancha es consecuencia del horizonte de tres semanas. Se reporta su exceso (85 %) junto a la cobertura. |
| B1 | **Corregido** | El test de la app abre las 7 páginas (variable de entorno `APP_PAGINA`). |
| B2 | **Corregido** | Test de extremo a extremo de `emitir()` en seco, con la caché del 13 de noviembre. |
| B3 | **Corregido** | El aviso de series atrasadas compara la hidrología contra el martes de la semana s. |
| B4 | Aceptado | La variable global se restaura con `try/finally` y la emisión no corre en paralelo. |
| B5 | Aceptado | Se resuelve con el registro TIE desde el 20 de noviembre. |

Además se agregó a E16 la variante que se registra (sin ofertas): erra 98.3, igual que con ofertas, y sus cifras son las que muestran la app y la ficha. La app ya no usa el parámetro `use_container_width`, que Streamlit retira.

---

## Hallazgos

### Alto

**A1. En las semanas recientes el modelo TIE se queda corto y no supera a la regla con significancia.**

| Ventana (semanas objetivo hasta el 31-oct-2026) | MAE regla XM | MAE modelo | Sesgo regla | Sesgo modelo | Cobertura de la cota del modelo |
|---|---|---|---|---|---|
| Últimas 26 | 177.3 | 162.6 | −26.6 | **−70.2** | 85 % |
| Últimas 52 | 127.0 | 117.8 | −20.6 | **−33.8** | 85 % |
| 2018–2026 | 115.3 | 98.2 | −2.4 | −7.5 | 90.5 % |

- En 52 semanas la diferencia frente a la regla tiene p = 0.35 (Diebold-Mariano): **no es significativa**.
- Desde el período de riesgo (9 semanas objetivo desde septiembre de 2026) el modelo erra 134 y la regla 181. Son muy pocas semanas para concluir.
- **Causa probable:** la misma de la auditoría anterior. 2026 tiene precios altos y sostenidos, y la variable de nivel del precio empuja hacia la media.
- **Recomendación:** presentar las dos cifras, la de 2018–2026 y la del último año. Agregar al monitoreo TIE el control de sesgo que ya existe para el modelo a una semana (5 % del precio, HAC).

**A2. El snapshot TIE no permite reproducir el pronóstico.** `registro/snapshots_tie/` guarda las variables, los coeficientes y el intercepto, pero no la media y la escala del `StandardScaler`, el factor de Duan ni el margen de la cota. La auditoría del 10 de noviembre (hallazgo sobre reproducción) ya lo había corregido en `semanal.py` con `reproducir()`. `semanal_tie.py` repite el problema.
- **Recomendación:** guardar la escala, el factor de Duan y el margen log, y agregar una función `reproducir()` con un test, como en `semanal.py`. Conviene hacerlo antes de la primera emisión del viernes 20.

### Medio

**M1. La app abre con el pronóstico a una semana.** La portada muestra el MAE de 54.0 y el de 33.2 con costo marginal. La página Metodología dice "semana siguiente (lunes a domingo), ponderado por demanda". La garantía TIE aparece solo en un recuadro y en su página.
- **Recomendación:** que la portada abra con la regla de XM frente al modelo TIE, y dejar el pronóstico a una semana como complemento.

**M2. Documentos desactualizados.**
- [FICHA_TECNICA.md](../FICHA_TECNICA.md), "Para qué sirve" y "Qué hace": siguen describiendo el modelo a una semana.
- [README.md](../README.md), línea 23: "La semana va de lunes a domingo".
- [AUDITORIA.md:70](AUDITORIA.md): dice que Duan "no se aplicó". E15 y E16 mostraron que, calculado dentro de cada bloque, mejora el error y el sesgo, y el modelo TIE lo usa.
- **README, "Ver el tablero":** remite a `dashboard/index.html`, que el `.bat` ya no regenera.

**M3. El costo marginal de 3 días sigue sin confirmar.** Observaciones: el jueves 12 a las 22:06 no estaba el del viernes 13, y el domingo 15 a las 17:25 no estaba el del lunes 16. XM lo publica tarde la víspera o el mismo día. La app dice "probablemente ya está publicado al emitir el miércoles". Esa frase sigue siendo una hipótesis.

**M4. La cota TIE es ancha.** Cuando cubre, queda 88 % por encima del precio real, en promedio. Como límite para una garantía es caro.

### Bajo

**B1. El test de la app solo abre la portada.** Revisé a mano las 7 páginas en el navegador y ninguna tiene errores, pero un cambio podría romper una página sin que fallen los tests.

**B2. `semanal_tie.emitir` no tiene un test de extremo a extremo.** Los tests cubren el calendario y el registro. La emisión se probó en seco a mano (13 de noviembre: normal, 397.5 COP/kWh; con la caché vieja: respaldo; hoy: rechaza la semana base incompleta).

**B3. El aviso de "series atrasadas" en `semanal_tie.py` casi nunca se activa.** Compara contra el viernes de s-1, que ya se exige completo para emitir.

**B4. `dp.PERIODO_SEMANA` es una variable global que `tabla_tie()` cambia temporalmente.** Funciona y se restaura con `try/finally`, pero no es seguro si algún día se usa en paralelo.

**B5. Sesgo por haber elegido el mejor.** El modelo TIE es el mejor de 6 variantes fijadas de antemano, en el experimento 16 del proyecto. La evidencia independiente empieza con el registro TIE, el 20 de noviembre.

---

## Verificado sin problemas

| Revisión | Resultado |
|---|---|
| Reproducción de E16 desde la caché | MAE idénticos (115.29 y 98.23) y las mismas 461 semanas |
| Objetivo de E16 | y = log(P<sub>s+3</sub>/P<sub>s</sub>) exacto; 879 semanas TIE consecutivas, todas con 168 horas |
| Entrenamiento al emitir (13-nov) | Última fila usada: 10-oct, con objetivo hasta el 6-nov, antes de la emisión |
| Días de sábado a martes | Terminan 3 días antes del viernes, igual al rezago observado |
| Versión de los datos | Con TX1 en lunes y martes, el MAE es 98.5 frente a 98.8: no hay optimismo |
| Cota | Usa errores con rezago de 3 semanas; cobertura 90.9 %, 89.8 % y 90.6 % por periodo |
| Sin variables de oferta | MAE igual (98.8): el modelo TIE no depende de que XM publique las ofertas |
| Registro a una semana | Huellas íntegras; 2 filas, sin alteraciones |
| Registro TIE | Aún vacío; el test de alteración pasa |
| App | Las 7 páginas cargan sin errores |
| Tests | 72 pasan, 1 se omite (el de reconstrucción, porque la última emisión salió en respaldo) |

## Estado operativo

- XM no ha publicado los precios de oferta de noviembre (consulta del 15 de noviembre). Al modelo TIE no le afecta.
- La primera emisión TIE es el viernes 20 de noviembre: semana base del 7 al 13 de noviembre, semana objetivo del 28 de noviembre al 4 de diciembre.
- La rama `app-streamlit` tiene 6 commits sin mergear a `main`. El informe ya no está versionado (commit bad1997).
