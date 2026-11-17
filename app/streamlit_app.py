"""Panel del proyecto XM–UNAL: modelos para anticipar precios relacionados con las obligaciones TIE.

Uso local:  streamlit run app/streamlit_app.py
Lee solo results/app/ (lo genera `python src/resultados_app.py`) y docs/SUPUESTOS.md. No reentrena modelos
ni cambia cifras: solo presenta los resultados ya calculados.

Navegación:
- Análisis principal: Inicio; objetivo principal (compras TIE en bolsa, E26); objetivo de referencia (precio
  nacional de bolsa, E16 y E24); objetivo complementario (precio realizado de exportación, E19 y E20).
- Operación y registro: emisión ilustrativa y registro prospectivo; informe PDF.
- Metodología: cómo se construyen y evalúan los modelos; experimento complementario de una semana.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "results" / "app"
sys.path.insert(0, str(RAIZ / "src"))
import colores as col  # noqa: E402  (paleta de la app; el informe PDF usa isa101)
import config  # noqa: E402  (definición de los tres objetivos y su condición de oficial o reconstruido)
import presentacion as pr  # noqa: E402  (nombres, estados y avisos compartidos con el informe PDF)

st.set_page_config(page_title="Modelos para precios relacionados con las obligaciones TIE", page_icon="⚡",
                   layout="wide")

# --- Nombres de las series ------------------------------------------------------------------------------
REGLA = "Regla de referencia"
NUESTRO = "Modelo registrado"
PRUEBA = "Modelo en prueba"
OBSERVADO = "Valor observado"
COTA = "Cota estadística calibrada (90 %)"
SUPERA = "Semanas que superaron la cota"
NOMBRES_SIMPLES = {
    # Objetivo de referencia (precio nacional de bolsa), complementario (exportación) y principal (compras TIE)
    "Regla XM (repetir s-1)": REGLA,
    "Modelo registrado (sábado a martes + costo marginal mié-vie, con corrección de sesgo)": NUESTRO,
    "Modelo elegido (Huber + regla)": NUESTRO,
    "Modelo compras TIE (nacional × diferencial)": NUESTRO,
    "Candidato en paralelo (+ hidrología hasta el jueves y martes)": PRUEBA,
    "Modelo anterior (sin costo marginal)": "Versión anterior del modelo registrado (sin costo marginal)",
    "Regla con sábado a martes de s": "Regla con los días más recientes (sábado a martes de s)",
    "Ridge 14": "Variante: modelo básico",
    "Ridge 14 con corrección de sesgo": "Variante: modelo básico con corrección de sesgo",
    "Ridge 14 + sábado a martes de s": "Variante: modelo básico + días recientes",
    "Ridge 14 + sábado a martes de s, con corrección de sesgo": "Variante: modelo básico + días recientes, con corrección de sesgo",
    "Huber + sábado a martes": "Variante: con días recientes",
    "Huber": "Variante: solo el modelo, sin la regla",
    "Precio nacional × diferencial": "Variante: precio nacional ajustado",
    "Ridge + nacional + sábado a martes": "Variante: con el precio nacional",
    "LightGBM": "Variante: árboles de decisión",
    # Experimento complementario de una semana
    "Ingenuo": "Copiar la semana pasada",
    "Ridge 14 (oficial)": "Ridge 14 (modelo base del experimento)",
}

# --- Colores (src/colores.py) ---------------------------------------------------------------------------
# Un color fijo por papel: negro lo observado, gris la regla, naranja el modelo registrado, verde el modelo en
# prueba, azul las alternativas y la cota, rojo las alertas. El color no dice que un modelo esté validado:
# solo distingue papeles, y cada serie lleva además nombre, trazo y símbolo propios.
INK, INK2, MUTED, GRID, BASE = col.TEXTO, col.TEXTO_2, col.TEXTO_TENUE, col.REJILLA, col.EJE
COLOR = {REGLA: col.REGLA, NUESTRO: col.MODELO, PRUEBA: col.PRUEBA, "Copiar la semana pasada": col.REGLA,
         "Ridge 14 (modelo base del experimento)": col.MODELO}
TRAZO = {REGLA: "dash", "Copiar la semana pasada": "dash", NUESTRO: "solid",
         "Ridge 14 (modelo base del experimento)": "solid", PRUEBA: "dot"}
TRAZOS_ALTERNATIVOS = ["dashdot", "longdash", "longdashdot", "dot"]

ALARMA = (f"Triángulo rojo: semana en que el valor observado superó la cota estadística calibrada del 90 % (no es "
          f"una fórmula oficial de XM). Negro: valor observado; gris discontinuo: regla de referencia; naranja: "
          f"modelo registrado; azul punteado: cota.")
HUECOS = ("Los huecos son semanas sin observación pública calificada para ese periodo: no se unen con líneas ni se "
          "cuentan como cero.")
NOTA_UNIDADES = "Los errores solo son comparables dentro del mismo objetivo y unidad."
AVISO_REGISTRO = ("Registro prospectivo aún no consolidado: la primera emisión prevista es el viernes 20 de noviembre "
                  "de 2026. Hasta que acumule semanas calificadas, las cifras salen del backtest simulado.")
ORIENTACION = ("El panel compara modelos estadísticos del proyecto contra una regla de referencia basada en material "
               "público de formación de XM. No reproduce una fórmula oficial de garantía y ningún modelo está validado "
               "para fijar garantías.")

# Etiquetas metodológicas de cada objetivo: se muestran como texto, no solo con color.
ETIQUETAS = {
    "principal": ["Objetivo principal", "E26", "Evidencia débil", "Reconstruido; no es una fórmula oficial de XM"],
    "referencia": ["Objetivo de referencia", "E16 y E24", "Evidencia estadística favorable frente a la regla"],
    "complementario": ["Objetivo complementario", "E19 y E20", "Resultado no concluyente", "Evidencia débil",
                       "Reconstruido; no es una fórmula oficial de XM"],
}
TITULO_E22 = pr.TITULO_E22[0].lower() + pr.TITULO_E22[1:]  # "monto … del MXT" (respeta la sigla)
UNIDAD_LARGA = {"COP/kWh": "pesos por kWh (COP/kWh)", "centUSD/kWh": "centavos de dólar por kWh (centUSD/kWh)"}
FUENTE = {"principal": "API pública de XM: CompBolsaTIEMoneda / CompBolsaTIEEner (reconstrucción del proyecto)",
          "referencia": "API pública de XM: PrecBolsNaci, promedio horario de la semana TIE",
          "complementario": "API pública de XM: ExportMonedaUSD / ExpoEner (reconstrucción del proyecto)"}

CSS = f"""
<style>
[data-testid="stMetric"] {{background:#ffffff; border:1px solid {col.REJILLA}; border-radius:8px;
  padding:10px 14px;}}
[data-testid="stMetricLabel"] p {{color:{col.TEXTO_2}; font-weight:600;}}
[data-testid="stMetricValue"] {{color:{col.TEXTO};}}
[data-testid="stMetricValue"] div, [data-testid="stMetricLabel"] p, [data-testid="stMetricDelta"] div
  {{white-space:normal; overflow:visible; text-overflow:clip;}}
[data-testid="stDataFrame"] {{border:1px solid {col.REJILLA}; border-radius:6px; background:#ffffff;}}
[data-testid="stAlertContentWarning"] {{color:#5c3f00;}}
[data-testid="stAlertContentInfo"] {{color:#123e7a;}}
[data-testid="stAlertContainer"] {{border-left:4px solid {col.EJE};}}
.tarjeta {{background:#ffffff; border:1px solid {col.REJILLA}; border-radius:8px; padding:10px 14px;
  min-height:104px; overflow-wrap:anywhere;}}
.tarjeta-titulo {{color:{col.TEXTO_2}; font-weight:600; font-size:0.875rem; margin-bottom:6px;}}
.tarjeta-valor {{color:{col.TEXTO}; font-size:1.15rem; font-weight:600; line-height:1.3;}}
.objetivo {{background:#ffffff; border:1px solid {col.EJE}; border-radius:10px; padding:14px 16px;
  overflow-wrap:anywhere;}}
.objetivo h4 {{margin:4px 0 8px 0; font-size:1.15rem; color:{col.TEXTO};}}
.objetivo table {{width:100%; border-collapse:collapse; font-size:0.9rem;}}
.objetivo td {{padding:3px 0; border-bottom:1px solid {col.REJILLA}; vertical-align:top;}}
.objetivo td:first-child {{color:{col.TEXTO_2}; width:46%; padding-right:8px;}}
.objetivo .estado {{margin-top:10px; font-weight:700; color:{col.TEXTO};}}
.objetivo .nota {{margin-top:6px; font-size:0.85rem; color:{col.TEXTO_2};}}
.orientacion {{background:#ffffff; border:1px solid {col.EJE}; border-left:6px solid {col.ALTERNATIVO};
  border-radius:8px; padding:12px 16px; margin:4px 0 12px 0;}}
.orientacion b {{color:{col.TEXTO};}}
.calendario {{display:flex; flex-direction:column; gap:4px; font-size:0.9rem;}}
.calendario div.paso {{background:#ffffff; border:1px solid {col.REJILLA}; border-radius:6px; padding:6px 10px;
  color:{col.TEXTO};}}
.calendario div.flecha {{text-align:center; color:{col.TEXTO_TENUE}; line-height:1;}}
.etiqueta {{display:inline-block; margin:0 6px 6px 0; padding:2px 10px; border:1px solid {col.EJE};
  border-radius:12px; background:#ffffff; color:{col.TEXTO}; font-size:0.85rem; font-weight:600;}}
</style>
"""


def etiquetas(clave):
    """Etiquetas metodológicas de un objetivo (texto con borde, sin depender del color)."""
    st.markdown("".join(f"<span class='etiqueta'>{e}</span>" for e in ETIQUETAS[clave]), unsafe_allow_html=True)


def trazo(m, i=0):
    """Color y trazo de una serie: regla gris discontinua, modelo registrado naranja, en prueba verde punteado,
    alternativas en azul (u otro tono frío si hay varias) con trazos distintos."""
    otro = col.ALTERNATIVOS[i % len(col.ALTERNATIVOS)]
    return COLOR.get(m, otro), TRAZO.get(m, TRAZOS_ALTERNATIVOS[i % len(TRAZOS_ALTERNATIVOS)])


def tarjeta(titulo, valor):
    """Tarjeta con texto largo que se ajusta en varias líneas (st.metric lo cortaría)."""
    st.markdown(f"<div class='tarjeta'><div class='tarjeta-titulo'>{titulo}</div>"
                f"<div class='tarjeta-valor'>{valor}</div></div>", unsafe_allow_html=True)


PASOS_CALENDARIO = [
    "Viernes de la semana s: día de cálculo",
    "Datos públicos disponibles hasta ese viernes (semana s-1 completa y sábado a martes de s)",
    "Pronóstico de la semana objetivo s+2",
    "Semana objetivo: de sábado a viernes",
    "Comparación posterior con el valor observado",
]


def calendario():
    """Bloque visual de la regla temporal: viernes s → semana objetivo s+2, con referencia en s-1."""
    pasos = "<div class='flecha'>↓</div>".join(f"<div class='paso'>{p}</div>" for p in PASOS_CALENDARIO)
    st.markdown(f"<div class='calendario'>{pasos}</div>", unsafe_allow_html=True)


def indicador_estado(estado):
    """Indicador de estado: panel claro si es normal; ámbar con símbolo y texto si es vigilancia o respaldo."""
    e = str(estado or "normal").lower()
    fondo = col.ESTADO_COLOR.get(e, col.FONDO_PANEL)
    st.markdown(f"<div style='background:{fondo};border:1px solid {col.EJE};border-radius:6px;padding:6px 12px;"
                f"display:inline-block;font-weight:600;color:{col.TEXTO}'>Estado del cálculo: "
                f"{col.ESTADO_TEXTO.get(e, e)}</div>", unsafe_allow_html=True)


PERIODOS = {
    "2018 a 2026 (la evaluación principal)": ("2018-01-01", "2026-12-31"),
    "2025 a 2026 (prueba final, no se usó para elegir)": ("2025-01-01", "2026-12-31"),
    "2022 a 2024 (con esto se eligió el modelo)": ("2022-01-01", "2024-12-31"),
    "2014 a 2021": ("2014-01-01", "2021-12-31"),
}
PRINCIPAL = list(PERIODOS)[0]
FINAL = list(PERIODOS)[1]
# Una semana "sube" si el precio sube 25 % o más, y "baja" si cae más de 20 %.
UMBRAL_BAJA, UMBRAL_SUBE = np.log(0.80), np.log(1.25)


@st.cache_data
def cargar(version):
    """Lee los resultados ya calculados. `version` cambia cuando se regeneran, y así la caché se renueva."""
    tie = pd.read_parquet(DATOS / "predicciones_tie.parquet").rename(columns=_renombrar)
    expo = pd.read_parquet(DATOS / "predicciones_expo.parquet").rename(columns=_renombrar)
    semana = pd.read_parquet(DATOS / "predicciones.parquet").rename(columns=_renombrar)
    modelos = pd.read_csv(DATOS / "modelos.csv")
    modelos["modelo"] = modelos.modelo.map(lambda m: NOMBRES_SIMPLES.get(m, m))
    episodios = pd.read_csv(DATOS / "episodios.csv")
    ctx_expo = pd.read_parquet(DATOS / "contexto_expo.parquet")
    reg_semana = pd.read_csv(DATOS / "registro.csv", parse_dates=["fecha_emision", "semana_objetivo"])
    ultimo = json.loads((DATOS / "ultimo_tie.json").read_text(encoding="utf-8"))
    archivo_compra = DATOS / "predicciones_compra.parquet"
    compra = pd.read_parquet(archivo_compra).rename(columns=_renombrar) if archivo_compra.exists() else None
    return tie, expo, semana, modelos, episodios, ctx_expo, reg_semana, ultimo, compra


def _renombrar(c):
    if c.startswith("cota|"):
        return "cota|" + NOMBRES_SIMPLES.get(c[5:], c[5:])
    return NOMBRES_SIMPLES.get(c, c)


TIE, EXPO, SEMANA, MODELOS, EPISODIOS, CTX_EXPO, REG_SEMANA, ULTIMO, COMPRA = cargar(
    max(a.stat().st_mtime for a in DATOS.iterdir()))
DATOS_OBJETIVO = {"principal": COMPRA, "referencia": TIE, "complementario": EXPO}


def modelos_de(p):
    return [c for c in p.columns if c not in ("semana_objetivo", "real", "base", "regimen_expo")
            and not c.startswith("cota|")]


# --- Cálculos (sin cambios: las cifras salen de results/app/) ---------------------------------------------

def filtrar(p, periodo):
    ini, fin = PERIODOS[periodo]
    return p[(p.semana_objetivo >= pd.Timestamp(ini)) & (p.semana_objetivo <= pd.Timestamp(fin))]


def p_valor(p, modelo, referencia):
    """Probabilidad de que la diferencia de error sea suerte (Diebold-Mariano con varianza de Newey-West)."""
    from scipy import stats
    dl = ((p[modelo] - p.real).abs() - (p[referencia] - p.real).abs()).dropna().to_numpy()
    n = len(dl)
    if n < 10:
        return np.nan
    rezagos = int(np.floor(4 * (n / 100) ** (2 / 9)))
    u = dl - dl.mean()
    v = (u @ u) / n
    for k in range(1, rezagos + 1):
        v += 2 * (1 - k / (rezagos + 1)) * (u[k:] @ u[:-k]) / n
    return float(2 * stats.t.sf(abs(dl.mean() / np.sqrt(v / n)), n - 1))


def confiable(p):
    """Qué tan probable es que la diferencia sea azar, en palabras, con el valor p a la vista.

    No dice que la mejora sea cierta: el valor p no corrige por haber elegido entre variantes. El estado
    metodológico de cada objetivo está en presentacion.OBJETIVO.
    """
    if np.isnan(p):
        return "Muy pocas semanas para saber"
    if p < 0.05:
        return f"Diferencia poco probable por azar ({pr.valor_p(p)})"
    if p < 0.10:
        return f"No concluyente ({pr.valor_p(p)})"
    return f"No se puede asegurar ({pr.valor_p(p)})"


def resumen_objetivo(clave, p=None):
    """Cifras del backtest de un objetivo frente a la regla, en la evaluación principal (2018 a 2026)."""
    p = filtrar(DATOS_OBJETIVO[clave], PRINCIPAL) if p is None else p
    p = p.dropna(subset=["real", REGLA, NUESTRO])
    er, en = (p[REGLA] - p.real).abs().mean(), (p[NUESTRO] - p.real).abs().mean()
    return {"semanas": len(p), "desde": p.semana_objetivo.min(), "hasta": p.semana_objetivo.max(),
            "error_regla": er, "error_modelo": en, "diferencia": (en / er - 1) * 100,
            "p": p_valor(p, NUESTRO, REGLA)}


def periodo_texto(p):
    q = p.dropna(subset=["real"])
    if q.empty:
        return "sin semanas"
    return f"{q.semana_objetivo.min():%d/%m/%Y} a {q.semana_objetivo.max():%d/%m/%Y}"


def estado_modelo(m, referencia, clave):
    if m == referencia:
        return "Referencia de comparación"
    if clave and m == NUESTRO:
        return pr.OBJETIVO[clave]["estado"]
    if m == PRUEBA:
        return "En prueba; lo decide el registro prospectivo"
    if m == "Ridge 14 (modelo base del experimento)":
        return "Modelo base del experimento complementario"
    return "Variante del backtest (no elegida)"


def tabla(p, modelos, referencia, clave=None, objetivo="", unidad=""):
    """Una fila por modelo: objetivo, unidad, periodo, semanas, errores, cobertura de la cota, valor p y estado."""
    filas = []
    error_ref = (p[referencia] - p.real).abs().mean()
    for m in modelos:
        s = p.dropna(subset=[m, "real"])
        e = s[m] - s.real
        cota = f"cota|{m}"
        filas.append({
            "Modelo": m, "Objetivo": objetivo, "Unidad": unidad, "Periodo": periodo_texto(s),
            "Semanas evaluadas": len(s), "Error promedio": e.abs().mean(),
            "Error típico (% del valor)": (e.abs() / s.real).median() * 100,
            "Diferencia frente a la regla (%)": (e.abs().mean() / error_ref - 1) * 100 if m != referencia else 0.0,
            "Desvío promedio": e.mean(),
            "Cobertura de la cota (%)": (s.real <= s[cota]).mean() * 100 if cota in s else np.nan,
            "Valor p (DM)": "—" if m == referencia else pr.valor_p(p_valor(p, m, referencia)),
            "Estado de la evidencia": estado_modelo(m, referencia, clave)})
    return pd.DataFrame(filas).sort_values("Error promedio")


def formato(unidad, decimales):
    f = f"%.{decimales}f"
    return {
        "Error promedio": st.column_config.NumberColumn(f"Error promedio ({unidad})", format=f,
                                                        help="Error absoluto medio. Más bajo es mejor."),
        "Error típico (% del valor)": st.column_config.NumberColumn(
            format="%.0f %%", help="Mediana del error absoluto como porcentaje del valor observado."),
        "Diferencia frente a la regla (%)": st.column_config.NumberColumn(
            format="%+.0f %%", help="Negativo: el modelo se equivoca menos que la regla de referencia."),
        "Desvío promedio": st.column_config.NumberColumn(
            format=f"%+.{decimales}f", help="Negativo: en promedio el pronóstico queda por debajo del valor observado."),
        "Cobertura de la cota (%)": st.column_config.NumberColumn(
            format="%.0f %%", help="Semanas en que el valor observado no superó la cota estadística calibrada. "
                                   "La meta es 90 %."),
        "Valor p (DM)": st.column_config.TextColumn(
            help="Prueba de Diebold-Mariano frente a la regla. No corrige por haber elegido entre variantes."),
    }


def mostrar_tabla(t, unidad, decimales):
    st.dataframe(t, hide_index=True, width="stretch", column_config=formato(unidad, decimales))
    st.caption(NOTA_UNIDADES)


# --- Gráficos -------------------------------------------------------------------------------------------

def estilo(fig, alto=380, titulo_y=None):
    """Fondo marfil claro, texto oscuro, rejilla tenue y leyenda horizontal."""
    fig.update_layout(
        height=alto, margin=dict(l=8, r=8, t=30, b=8), paper_bgcolor=col.FONDO, plot_bgcolor=col.FONDO,
        font=dict(family=col.FUENTE, color=col.TEXTO_2, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None, font=dict(color=col.TEXTO)),
        hovermode="x unified", hoverlabel=dict(bgcolor="white", font_color=col.TEXTO))
    fig.update_xaxes(showgrid=False, linecolor=col.EJE, ticks="outside", tickcolor=col.EJE)
    fig.update_yaxes(gridcolor=col.REJILLA, zeroline=False, title=titulo_y, title_font_color=col.TEXTO_TENUE)
    return fig


def grafico(p, modelos, unidad, techo=None, puntos=False, alto=420):
    """Valor observado (negro), regla de referencia (gris discontinuo), modelo registrado (naranja), modelo en
    prueba (verde punteado), alternativas (azul) y, si se pide, la cota estadística de uno (azul punteado).

    `unidad` es "COP/kWh" o "centUSD/kWh". Las semanas en que el valor observado superó la cota se marcan con
    un triángulo rojo. Con `puntos`, las semanas sin observación quedan como huecos (no se unen ni valen cero).
    """
    d = 2 if unidad.startswith("centUSD") else 0
    fig = go.Figure()
    if puntos:  # sin observación no hay dato: huecos en vez de líneas que unen periodos vacíos
        p = p.set_index("semana_objetivo")
        p = p.reindex(pd.date_range(p.index.min(), p.index.max(), freq="7D")).rename_axis("semana_objetivo").reset_index()
    valor = f"%{{y:,.{d}f}} {unidad}"
    cota = f"cota|{techo}" if techo else None
    if cota and cota in p:
        fig.add_scatter(x=p.semana_objetivo, y=p[cota], name=COTA, hovertemplate=valor,
                        line=dict(color=col.TECHO, width=1.2, dash="dot"), opacity=0.8)
    fin = (p.semana_objetivo + pd.Timedelta(days=6)).dt.strftime("%d/%m/%Y")
    fig.add_scatter(x=p.semana_objetivo, y=p.real, name=OBSERVADO, mode="lines+markers" if puntos else "lines",
                    customdata=fin, hovertemplate=valor + " (sábado %{x|%d/%m/%Y} a viernes %{customdata})",
                    line=dict(color=col.REAL, width=2.5), marker=dict(size=5, color=col.REAL))
    for i, m in enumerate(modelos):
        color, dash = trazo(m, i)
        fig.add_scatter(x=p.semana_objetivo, y=p[m], name=m, mode="markers" if puntos else "lines",
                        hovertemplate=valor, line=dict(color=color, width=2, dash=dash),
                        marker=dict(size=7, color=color, symbol="square" if m == NUESTRO else "circle"))
    if cota and cota in p:
        sobre = p[p.real > p[cota]]
        if len(sobre):
            fig.add_scatter(x=sobre.semana_objetivo, y=sobre.real, mode="markers", hovertemplate=valor,
                            name=f"{SUPERA} ({len(sobre)})",
                            marker=dict(symbol="triangle-up", size=12, color=col.ALARMA_ALTA,
                                        line=dict(color=col.TEXTO, width=1)))
    fig.update_xaxes(hoverformat="Semana objetivo que inicia el sábado %d/%m/%Y")
    return estilo(fig, alto, UNIDAD_LARGA.get(unidad, unidad))


def ficha_grafico(titulo, clave, p, fuente=None, puntos=False, cota=False):
    """Título completo y ficha del gráfico: objetivo, unidad, periodo, semanas y fuente."""
    o = pr.OBJETIVO[clave]
    q = p.dropna(subset=["real"])
    st.markdown(f"**{titulo}**")
    st.caption(f"Objetivo: {o['nombre']} ({clave}; {o['experimento']}) · Unidad: {o['unidad']} · Periodo: "
               f"{periodo_texto(p)} · Semanas con valor observado: {len(q)} · Fuente: {fuente or FUENTE[clave]}. "
               "Resultados del backtest histórico, no del registro prospectivo.")


def notas_grafico(puntos=False, cota=False):
    st.caption(pr.NOTA_REGLA + (" " + HUECOS if puntos else "") + (" " + ALARMA if cota else ""))


def barras_explicacion(aportes):
    """Rojo: empuja el precio hacia arriba; azul: hacia abajo. El signo también se lee en el eje."""
    a = pd.DataFrame(aportes).assign(pct=lambda x: (np.exp(x.aporte_log) - 1) * 100)
    a["nombre"] = [pr.NOMBRES.get(v, n) for v, n in zip(a.variable, a.nombre)]
    a = a.reindex(a.pct.abs().sort_values().index)
    fig = go.Figure(go.Bar(x=a.pct, y=a.nombre, orientation="h",
                           marker=dict(color=np.where(a.pct >= 0, col.SUBE, col.BAJA), line=dict(color=col.EJE, width=0.5)),
                           hovertemplate="%{y}: %{x:+.1f} %<extra></extra>"))
    fig.update_xaxes(title="Cuánto empuja el pronóstico frente a una semana normal (%)", gridcolor=GRID,
                     showgrid=True, zeroline=True, zerolinecolor=BASE)
    fig.update_yaxes(title=None, gridcolor="rgba(0,0,0,0)")
    return estilo(fig, 420).update_layout(hovermode="closest", showlegend=False)


def boton_informe():
    """Descarga del informe PDF que se genera en cada corrida (src/informe_pdf.py)."""
    pdf = DATOS / "informe_ultimo.pdf"
    if pdf.exists():
        st.download_button("Descargar el informe en PDF", pdf.read_bytes(), file_name="informe_garantia_TIE.pdf",
                           mime="application/pdf", help="Seis páginas: resumen, los tres objetivos, registro y "
                                                        "supuestos. Se genera en cada corrida.")


# --- Componentes de página --------------------------------------------------------------------------------

def tarjeta_objetivo(clave):
    """Tarjeta de Inicio: unidad, periodo, semanas, errores, diferencia, valor p, estado y disponibilidad."""
    o = pr.OBJETIVO[clave]
    d = o["decimales"]
    if DATOS_OBJETIVO[clave] is None:
        st.markdown(f"<div class='objetivo'><h4>{o['nombre']}</h4>Sin resultados en results/app/.</div>",
                    unsafe_allow_html=True)
        return
    r = resumen_objetivo(clave)
    estado = o["estado"]
    if clave == "referencia":
        ultimo = TIE.tail(52)
        estado += f" (evaluación global 2018–2026; en el último año: {pr.valor_p(p_valor(ultimo, NUESTRO, REGLA))})"
    filas = [("Variable", o["variable"]), ("Unidad", o["unidad"]), ("Experimento", o["experimento"]),
             ("Periodo (semanas objetivo)", f"{r['desde']:%d/%m/%Y} a {r['hasta']:%d/%m/%Y}"),
             ("Semanas evaluadas", f"{r['semanas']}"),
             ("Error de la regla de referencia", f"{r['error_regla']:,.{d}f} {o['unidad']}"),
             ("Error del modelo registrado", f"{r['error_modelo']:,.{d}f} {o['unidad']}"),
             ("Diferencia frente a la regla", f"{r['diferencia']:+.1f} %"),
             ("Valor p (Diebold-Mariano)", pr.valor_p(r["p"]))]
    tabla_html = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in filas)
    chips = "".join(f"<span class='etiqueta'>{e}</span>" for e in ETIQUETAS[clave])
    st.markdown(f"<div class='objetivo'>{chips}"
                f"<h4>{o['nombre']}</h4><table>{tabla_html}</table>"
                f"<div class='estado'>Estado de la evidencia: {estado}</div>"
                f"<div class='nota'>{pr.NOTA_CORTA[clave]}</div></div>", unsafe_allow_html=True)
    st.page_link(PAGINAS[clave], label="Ver el detalle", icon="➡️")


def resumen_metricas(clave, p):
    """Fila de tarjetas de una página de objetivo, para el periodo elegido."""
    o = pr.OBJETIVO[clave]
    d = o["decimales"]
    r = resumen_objetivo(clave, p)
    c = st.columns([1, 1, 1, 1, 1.6])
    c[0].metric(f"Error de la regla ({o['unidad']})", f"{r['error_regla']:,.{d}f}")
    c[1].metric(f"Error del modelo registrado ({o['unidad']})", f"{r['error_modelo']:,.{d}f}",
                f"{r['diferencia']:+.1f} %", delta_color="off", help="Diferencia frente a la regla de referencia.")
    c[2].metric("Semanas evaluadas", f"{r['semanas']}")
    with c[3]:
        tarjeta("Valor p (Diebold-Mariano)", pr.valor_p(r["p"]))
    with c[4]:
        tarjeta("Estado de la evidencia (evaluación 2018–2026)", o["estado"])
    st.caption(f"Periodo del cálculo: {r['desde']:%d/%m/%Y} a {r['hasta']:%d/%m/%Y} (semanas objetivo de sábado a "
               f"viernes). Errores absolutos medios en {UNIDAD_LARGA[o['unidad']]}. El valor p no corrige por haber "
               "elegido entre variantes.")


def que_es(clave, limitacion, disponibilidad=None):
    o = pr.OBJETIVO[clave]
    st.markdown(f"""
| | |
|---|---|
| **Variable** | `{o['variable']}` |
| **Unidad** | {UNIDAD_LARGA[o['unidad']]} |
| **Experimentos** | {o['experimento']} |
| **Qué representa** | {o['funcion'][0].upper() + o['funcion'][1:]}. |
| **Limitación** | {limitacion} |
| **Comparación** | {pr.REGLA_NOMBRE}: repite el valor de la semana s-1 para la semana objetivo s+2. |
""")
    if disponibilidad:
        st.warning(disponibilidad)


# --- Páginas: análisis principal ---------------------------------------------------------------------------

def inicio():
    st.title("Modelos para anticipar precios relacionados con las obligaciones TIE")
    st.markdown("##### Caso XM–UNAL: comparación entre una regla de referencia y tres objetivos públicos reconstruidos")
    st.markdown(f"<div class='orientacion'><b>¿Qué hace este panel?</b><br>{ORIENTACION}</div>",
                unsafe_allow_html=True)

    st.subheader("Resultado principal")
    st.markdown("""
- **El objetivo principal es el precio de las compras TIE en bolsa** (E26): indicio favorable con evidencia débil, y hoy sin datos públicos para emitir.
- **El precio nacional de bolsa es una referencia**, no el objetivo principal (E16 y E24): es donde la evidencia estadística es más favorable.
- **El precio realizado de exportación es complementario** (E19 y E20): el resultado no es concluyente.
- **Los tres objetivos tienen unidades, muestras y niveles de evidencia diferentes**: sus errores no se comparan entre sí.
""")
    c = st.columns(3)
    for i, clave in enumerate(pr.ORDEN):
        with c[i]:
            tarjeta_objetivo(clave)
    st.caption(f"{NOTA_UNIDADES} Cifras del backtest simulado 2018–2026 (semanas objetivo de sábado a viernes). "
               f"{pr.NOTA_REGLA}")

    st.subheader("Disponibilidad de datos y registro")
    for aviso in pr.AVISOS_DISPONIBILIDAD:
        st.warning(aviso)
    st.info(AVISO_REGISTRO)

    st.subheader(f"E22: {TITULO_E22}")
    st.markdown(pr.NOTA_E22)

    st.subheader("Lo más importante")
    st.markdown("""
- **Los modelos usan lo más reciente.** La regla de referencia repite la semana s-1, que el viernes de cálculo ya tiene diez días; los modelos del proyecto también usan los días de la semana s que ya están publicados.
- **Ningún modelo anticipa los saltos bruscos de precio**, ni la regla ni los modelos. Ahí está el límite.
- **El backtest no es el registro prospectivo.** Las cifras salen de una simulación con datos del pasado; la evaluación prospectiva empieza con la primera emisión registrada.
""")
    st.caption(pr.NO_VALIDADO)
    boton_informe()
    st.info("**Prototipo académico de la Universidad Nacional**, no una herramienta oficial de XM.")


def compras():
    st.title("Compras TIE en bolsa — objetivo principal")
    etiquetas("principal")
    que_es("principal",
           "Variable pública reconstruida por el proyecto. La evidencia es débil y no existe confirmación pública de "
           "que sea exactamente la variable que XM utiliza para calcular una garantía.",
           pr.AVISOS_DISPONIBILIDAD[0])
    if COMPRA is None:
        st.info("No hay resultados de E26 en results/app/.")
        return
    periodo = st.selectbox("Periodo de evaluación", list(PERIODOS), key="per_compra")
    p = filtrar(COMPRA, periodo)
    resumen_metricas("principal", p)
    ficha_grafico("Compras TIE en bolsa: valor observado, regla de referencia y modelo registrado (E26)",
                  "principal", p, puntos=True, cota=True)
    st.plotly_chart(grafico(p, [REGLA, NUESTRO], "COP/kWh", techo=NUESTRO, puntos=True), width="stretch")
    notas_grafico(puntos=True, cota=True)
    st.markdown("**Errores por modelo en el periodo elegido**")
    mostrar_tabla(tabla(p, [REGLA, NUESTRO], REGLA, "principal", "Compras TIE en bolsa", "COP/kWh"), "COP/kWh", 0)
    st.markdown("""
**Cómo se lee:** el modelo registrado pronostica el precio nacional de bolsa de la semana s+2 y lo ajusta con la
diferencia entre las compras TIE y el precio nacional de la semana s-1. Se eligió entre 9 variantes; el valor p no
corrige por esa búsqueda, por eso la evidencia es débil.
""")


def bolsa():
    st.title("Precio nacional de bolsa — objetivo de referencia")
    etiquetas("referencia")
    que_es("referencia",
           "No es exclusivo de las transacciones TIE: es una referencia y no se presenta como valor de garantía. La "
           "evidencia favorable es de la evaluación global 2018–2026; en el último año (52 semanas) la diferencia "
           "frente a la regla no es concluyente.")
    periodo = st.selectbox("Periodo de evaluación", list(PERIODOS), key="per_bolsa")
    p = filtrar(TIE, periodo)
    resumen_metricas("referencia", p)
    principales = [REGLA, NUESTRO, PRUEBA]
    techo = st.toggle("Mostrar la cota estadística calibrada del modelo registrado", key="techo_bolsa")
    ficha_grafico("Precio nacional de bolsa: valor observado, regla de referencia, modelo registrado y modelo en "
                  "prueba (E16 y E24)", "referencia", p, cota=techo)
    st.plotly_chart(grafico(p, principales, "COP/kWh", techo=NUESTRO if techo else None), width="stretch")
    notas_grafico(cota=techo)
    st.markdown("**Errores por modelo en el periodo elegido**")
    mostrar_tabla(tabla(p, principales, REGLA, "referencia", "Precio nacional de bolsa", "COP/kWh"), "COP/kWh", 1)
    st.caption("El **modelo en prueba** suma la hidrología de la semana en curso. Se registra al lado del modelo "
               "registrado; si después de 26 semanas reales se equivoca menos, lo reemplaza.")
    with st.expander("Ver todas las variantes que se probaron en el backtest"):
        mostrar_tabla(tabla(p, modelos_de(p), REGLA, "referencia", "Precio nacional de bolsa", "COP/kWh"), "COP/kWh", 1)

    st.subheader("Episodios de precios altos")
    st.markdown("Semanas en que el precio se dispara: es cuando más importa no quedarse corto.")
    ep = st.selectbox("Episodio", EPISODIOS.episodio.tolist())
    f = EPISODIOS.set_index("episodio").loc[ep]
    q = TIE[(TIE.semana_objetivo >= f.inicio) & (TIE.semana_objetivo <= f.fin)]
    if q.empty:
        st.info("Este episodio todavía no tiene semanas evaluadas.")
    else:
        mostrar_tabla(tabla(q, principales, REGLA, "referencia", "Precio nacional de bolsa", "COP/kWh"), "COP/kWh", 1)
        ficha_grafico(f"Precio nacional de bolsa durante el episodio «{ep}»", "referencia", q, cota=True)
        st.plotly_chart(grafico(q, [REGLA, NUESTRO], "COP/kWh", techo=NUESTRO, alto=380), width="stretch")
        notas_grafico(cota=True)

    st.subheader("¿Anticipa los saltos?")
    st.markdown("Cada semana se clasifica como **Baja** (cae más de 20 %), **Igual** o **Sube** (sube 25 % o más) "
                "frente a la semana base. La matriz cuenta cuántas veces el modelo dijo lo mismo que se observó.")
    m = st.radio("Modelo", [NUESTRO, PRUEBA], horizontal=True)
    q = p.dropna(subset=[m])

    def clase(x):
        return pd.cut(np.log(x / q.base), [-np.inf, UMBRAL_BAJA, UMBRAL_SUBE, np.inf], right=False,
                      labels=["Baja", "Igual", "Sube"])

    t = pd.crosstab(clase(q.real), clase(q[m])).reindex(index=["Baja", "Igual", "Sube"],
                                                        columns=["Baja", "Igual", "Sube"], fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=t.values, x=[f"Pronóstico: {c}" for c in t.columns], y=[f"Observado: {r}" for r in t.index],
        colorscale=col.ESCALA_CALOR, showscale=False,
        text=t.values, texttemplate="%{text}", textfont=dict(size=16),
        hovertemplate="%{y} · %{x}: %{z} semanas<extra></extra>", xgap=2, ygap=2))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(estilo(fig, 320).update_layout(hovermode="closest"), width="stretch")
    sube, baja = t.loc["Sube"].sum(), t.loc["Baja"].sum()
    st.markdown(f"De **{sube}** semanas con subida fuerte observada, el modelo la anticipó en **{t.at['Sube', 'Sube']}**. "
                f"De **{baja}** con bajada fuerte, en **{t.at['Baja', 'Baja']}**. La regla de referencia nunca "
                "anticipa cambios: siempre dice *Igual*.")


def exportacion():
    st.title("Precio realizado de exportación — objetivo complementario")
    etiquetas("complementario")
    que_es("complementario",
           "Precio realizado y reconstruido a partir de las exportaciones observadas. No es una predicción oficial de "
           "XM ni una fórmula confirmada de garantía. Evidencia débil por el tamaño de la muestra, las exportaciones "
           "intermitentes y los cambios regulatorios. Solo existe en las semanas con al menos 1 GWh exportado.",
           pr.AVISOS_DISPONIBILIDAD[1])
    periodo = st.selectbox("Periodo de evaluación", list(PERIODOS), key="per_expo")
    p = filtrar(EXPO, periodo)
    resumen_metricas("complementario", p)
    ficha_grafico("Precio realizado de exportación: valor observado, regla de referencia y modelo registrado "
                  "(E19; cota por régimen regulatorio, E20)", "complementario", p, puntos=True, cota=True)
    st.plotly_chart(grafico(p, [REGLA, NUESTRO], "centUSD/kWh", techo=NUESTRO, puntos=True), width="stretch")
    notas_grafico(puntos=True, cota=True)
    st.caption("E20: en las semanas con reglas especiales de exportación, la cota se calibra con los errores de ese "
               "régimen regulatorio.")
    st.markdown("**Errores por modelo en el periodo elegido**")
    mostrar_tabla(tabla(p, [REGLA, NUESTRO], REGLA, "complementario", "Precio realizado de exportación",
                        "centUSD/kWh"), "centUSD/kWh", 2)
    pv = p_valor(p, NUESTRO, REGLA)
    st.markdown(f"""
**Qué muestra el backtest**
- **El modelo registrado es una mezcla:** la mitad es la regla de referencia y la otra mitad una regresión robusta (Huber) que mira la diferencia entre este precio y el nacional, los días recientes y el estado del sistema.
- **La mejora es pequeña: {pr.OBJETIVO["complementario"]["estado"].lower()}** ({pr.valor_p(pv)}; {len(p.dropna(subset=["real"]))} semanas con exportación). Por eso se registra cada semana al lado de la regla, para ver si se sostiene con datos nuevos.
- **Cuando cambian las reglas de exportación** (por ejemplo, exportar solo con plantas térmicas), este precio llega a ser el doble del nacional.
""")
    st.subheader(f"E22: {TITULO_E22}")
    st.markdown(pr.NOTA_E22)
    with st.expander("Ver todas las variantes que se probaron en el backtest"):
        mostrar_tabla(tabla(p, modelos_de(p), REGLA, "complementario", "Precio realizado de exportación",
                            "centUSD/kWh"), "centUSD/kWh", 2)
    with st.expander("Ver el precio de exportación al lado del precio nacional de bolsa (COP/kWh)"):
        c = CTX_EXPO[CTX_EXPO.index >= "2018-01-01"]
        st.markdown("**Precio realizado de exportación y precio nacional de bolsa, ambos en COP/kWh (valores "
                    "observados)**")
        st.caption(f"Semanas base de {c.index.min():%d/%m/%Y} a {c.index.max():%d/%m/%Y}. Fuente: API pública de XM "
                   "(ExpoMoneda / ExpoEner y PrecBolsNaci). Ambos son observados; aquí no hay pronósticos.")
        fig = go.Figure()
        fig.add_scatter(x=c.index, y=c.precio, name="Precio nacional de bolsa (observado)",
                        hovertemplate="%{y:,.0f} COP/kWh", line=dict(color=col.ALTERNATIVO, width=2, dash="dash"))
        fig.add_scatter(x=c.index, y=c.precio_expo_cop, name="Precio realizado de exportación (observado)",
                        mode="lines+markers", hovertemplate="%{y:,.0f} COP/kWh",
                        line=dict(color=col.REAL, width=2.5), marker=dict(size=5))
        st.plotly_chart(estilo(fig, 360, UNIDAD_LARGA["COP/kWh"]), width="stretch")
        st.caption("Desde 2023 el precio de exportación se separa del nacional. Desde agosto de 2026 llega a ser "
                   "varias veces mayor.")


# --- Páginas: operación y registro ---------------------------------------------------------------------------

def emision():
    st.title("Emisión ilustrativa y registro prospectivo")
    st.info(AVISO_REGISTRO)
    st.subheader("Registro prospectivo")
    st.markdown("Cada viernes se guarda el pronóstico **antes de conocer el valor observado**, en un registro que no "
                "se puede editar (cada fila lleva una huella encadenada a la anterior). Es la evaluación prospectiva "
                "de los modelos; el backtest es solo histórico.")
    archivo = DATOS / "registro_tie.csv"
    r = pd.read_csv(archivo, parse_dates=["fecha_emision", "semana_objetivo"]) if archivo.exists() else pd.DataFrame()
    if len(r):
        u = r.iloc[-1]
        st.markdown(f"**Última emisión registrada: viernes {u.fecha_emision:%d/%m/%Y}**, para la semana objetivo del "
                    f"{u.semana_objetivo:%d/%m/%Y} al {u.semana_objetivo + pd.Timedelta(days=6):%d/%m/%Y} "
                    "(objetivo de referencia: precio nacional de bolsa, COP/kWh).")
        c = st.columns(4)
        c[0].metric("Regla de referencia (COP/kWh)", f"{u.regla_xm:,.0f}")
        c[1].metric("Modelo registrado (COP/kWh)", f"{u.pronostico:,.0f}")
        c[2].metric("Cota estadística calibrada (COP/kWh)", f"{u.cota90:,.0f}")
        with c[3]:
            indicador_estado(u.estado)
        with st.expander("Ver todo el registro"):
            st.dataframe(r, hide_index=True, width="stretch")
    else:
        st.markdown("**El registro aún no tiene emisiones.** La primera está prevista para el viernes 20 de noviembre "
                    "de 2026, para la semana objetivo del 28 de noviembre al 4 de diciembre.")

    u = ULTIMO
    estado = str(u.get("estado") or "normal").lower()
    fecha, objetivo = pd.Timestamp(u["fecha_calculo"]), pd.Timestamp(u["semana_objetivo"])
    st.subheader("Ejemplo de emisión simulada")
    st.markdown("**Cálculo retrospectivo; no pertenece todavía al registro prospectivo.**")
    st.warning("Este cálculo corresponde al objetivo de referencia: precio nacional de bolsa. No es una emisión actual "
               "de E26 ni representa el precio oficial de una garantía.")
    modelo = (f"Variante de respaldo del modelo registrado (sin la variable faltante; versión {config.VERSION_TIE})"
              if estado == "respaldo" else f"Modelo registrado, versión {config.VERSION_TIE}")
    st.markdown(f"""
| Campo | Valor |
|---|---|
| Fecha simulada de emisión | viernes {fecha:%d/%m/%Y} (semana s) |
| Semana base de la regla | sábado {pd.Timestamp(u['semana_base']):%d/%m/%Y} a viernes {pd.Timestamp(u['semana_base']) + pd.Timedelta(days=6):%d/%m/%Y} (semana s-1) |
| Semana objetivo | sábado {objetivo:%d/%m/%Y} a viernes {objetivo + pd.Timedelta(days=6):%d/%m/%Y} (semana s+2) |
| Horizonte | s+2: la semana objetivo empieza 8 días después del viernes de cálculo |
| Objetivo pronosticado | Objetivo de referencia: precio nacional de bolsa (PrecBolsNaci) |
| Unidad | COP/kWh |
| Modelo utilizado | {modelo} |
| Regla de referencia | {pr.REGLA_NOMBRE} |
| Estado del cálculo | {col.ESTADO_TEXTO.get(estado, estado)} |
| Tipo | Ejemplo retrospectivo (cálculo en seco); no está en el registro prospectivo |
""")
    c = st.columns(3)
    c[0].metric("Regla de referencia (COP/kWh)", f"{u['regla_xm']:,.0f}")
    c[1].metric("Modelo (COP/kWh)", f"{u['pronostico']:,.0f}",
                f"{(u['pronostico'] / u['regla_xm'] - 1) * 100:+.1f} % frente a la regla", delta_color="off")
    c[2].metric("Cota estadística calibrada (COP/kWh)", f"{u['cota90']:,.0f}")
    if estado == "respaldo":
        st.markdown(f"<div class='orientacion' style='border-left-color:{col.ALARMA_MEDIA}'><b>Estado: modelo de "
                    "respaldo</b><br>Se utilizó una variante alternativa porque faltaba una variable necesaria para el "
                    "modelo principal. Este resultado es informativo y debe diferenciarse de una emisión normal.</div>",
                    unsafe_allow_html=True)
    else:
        indicador_estado(estado)
    for m in u.get("motivos") or []:
        st.caption(f"Motivo: {pr.legible(str(m))}")
    for n in u.get("notas") or []:
        st.caption(f"Nota: {pr.legible(str(n))}.")
    st.caption(pr.NO_VALIDADO)
    for aviso in pr.AVISOS_DISPONIBILIDAD:
        st.warning(aviso)
    st.markdown("**¿Qué empuja este pronóstico?** Cada barra muestra cuánto mueve una variable el pronóstico hacia "
                "arriba (rojo, a la derecha del cero) o hacia abajo (azul, a la izquierda), frente a una semana normal.")
    st.plotly_chart(barras_explicacion(u["aportes"]), width="stretch")


def informe():
    st.title("Informe PDF")
    st.markdown("""
El informe se genera en cada corrida (`python src/informe_pdf.py`) con los mismos resultados, nombres y estados de
evidencia que este panel. Tiene seis páginas:

1. **Resumen:** los tres objetivos con semanas, periodo, unidad, errores, valor p y estado de la evidencia; disponibilidad de datos y la emisión ilustrativa.
2. **Objetivo principal:** compras TIE en bolsa (E26).
3. **Objetivo de referencia:** precio nacional de bolsa (E16 y E24).
4. **Objetivo complementario:** precio realizado de exportación (E19 y E20).
5. **Registro prospectivo** y explicación del pronóstico.
6. **Supuestos, límites, preguntas abiertas y fuentes.**
""")
    st.caption("Las gráficas del PDF usan una paleta en grises (norma ISA-101) pensada para impresión; los nombres, "
               "las cifras y los estados son los mismos del panel. " + pr.NO_VALIDADO)
    boton_informe()


# --- Páginas: metodología -------------------------------------------------------------------------------------

def como_funciona():
    st.title("Cómo se construyen y evalúan los modelos")
    st.subheader("A. Datos")
    st.markdown("""
Se descargan series públicas de la API de XM (Sinergox) y se agregan por semana TIE (sábado a viernes):

| Serie | Qué mide | Unidad de la serie | Uso |
|---|---|---|---|
| `CompBolsaTIEMoneda`, `CompBolsaTIEEner` | Compras TIE en bolsa: monto y energía | COP y kWh | Objetivo principal (cociente, COP/kWh) |
| `PrecBolsNaci` | Precio de bolsa nacional, horario | COP/kWh | Objetivo de referencia (promedio horario) |
| `ExportMonedaUSD`, `ExpoEner` | Exportaciones: monto en dólares y energía | USD y kWh | Objetivo complementario (cociente, centUSD/kWh) |
| `CEE` | Costo equivalente de energía, mensual | COP/kWh | Hipótesis de equivalencia y E22 |
| Demanda, aportes, embalses, ofertas, costo marginal programado | Estado del sistema | varias | Variables de los modelos |
""")
    st.subheader("B. Calendario")
    calendario()
    st.markdown("""
- El **viernes de la semana s** se calcula el pronóstico de la **semana objetivo s+2**, de sábado a viernes; empieza 8 días después.
- La **regla de referencia** repite el valor de la **semana s-1**, la última completa.
- Los tres objetivos (E26, E16/E24 y E19/E20) usan este mismo horizonte: de la semana base s-1 a la semana objetivo s+2.
- El **experimento de una semana** (lunes a domingo, la semana siguiente) es un análisis complementario anterior: no es el modelo principal ni se confunde con E26.
""")
    st.caption(pr.REGLA_ATRIBUIDA)

    st.subheader("C. Tres objetivos")
    filas = "\n".join(f"| {pr.OBJETIVO[c]['nombre']} | `{pr.OBJETIVO[c]['variable']}` | {pr.OBJETIVO[c]['unidad']} | "
                      f"{pr.OBJETIVO[c]['experimento']} | {ETIQUETAS[c][0]} | {pr.OBJETIVO[c]['estado']} |"
                      for c in pr.ORDEN)
    st.markdown("| Objetivo | Variable | Unidad | Experimento | Función | Estado de la evidencia |\n"
                "|---|---|---|---|---|---|\n" + filas)
    st.caption("Las tres variables son reconstrucciones del proyecto a partir de series oficiales; ninguna es una "
               "cifra oficial de garantía. " + NOTA_UNIDADES)

    st.subheader("D. Evaluación")
    st.markdown("""
- **Backtest walk-forward:** para cada semana desde 2014 se entrena solo con lo que se sabía ese viernes (reentrenamiento cada 4 semanas y 2 semanas de embargo) y se pronostica la semana s+2. Los años 2022–2024 sirvieron para elegir el modelo; 2025–2026 se reservaron como prueba final.
- **Comparación contra la regla de referencia:** cada modelo se compara con la regla en las mismas semanas.
- **Error absoluto medio:** promedio de |pronóstico − valor observado|, en la unidad de cada objetivo.
- **Prueba de Diebold-Mariano:** dice qué tan probable es que la diferencia de errores frente a la regla sea azar (varianza de Newey-West).
- **Cota estadística calibrada (conformal):** un valor alto que el valor observado no debería superar en 9 de cada 10 semanas, calibrado con los errores de las últimas 104 semanas ya calificadas. **Cobertura:** porcentaje de semanas en que no se superó; la meta es 90 %.
- **Selección de variantes:** E26 se eligió entre 9 variantes y E19 entre unas 30; el valor p no corrige por esa búsqueda, por eso la evidencia de esos objetivos es débil o no concluyente.
- **Backtest histórico frente a registro prospectivo:** el backtest es una simulación con datos del pasado; el registro guarda cada emisión antes de conocer el resultado y es la prueba que falta.
""")

    st.subheader("Glosario")
    st.markdown(f"""
| Término | Qué significa |
|---|---|
| **Garantía** | El depósito que deja Ecuador antes de cada semana para asegurar el pago de la energía. |
| **Regla de referencia** | {pr.REGLA_NOMBRE}: repetir el valor de la semana s-1. Su vigencia no está confirmada. |
| **Valor observado** | Lo que efectivamente se publicó para la semana objetivo. |
| **Objetivo reconstruido** | Una variable calculada por el proyecto con series públicas de XM; no es una cifra oficial. |
| **Error promedio** | Error absoluto medio. Más bajo es mejor. |
| **Desvío promedio** | Si el pronóstico tiende a quedar por debajo (negativo) o por encima (positivo). |
| **Cota estadística calibrada** | Un valor alto que el valor observado no debería superar en 9 de cada 10 semanas. No es una fórmula oficial de XM. |
| **Estado de la evidencia** | Indicio favorable con evidencia débil (E26), evidencia estadística favorable frente a la regla base (E16 y E24) o no concluyente (E19). Ningún modelo está validado para fijar garantías. |
| **Valor p** | Probabilidad de ver una diferencia así por azar (Diebold-Mariano). No corrige por haber elegido entre variantes. |
| **E22** | {pr.TITULO_E22}; no es el monto oficial de la garantía. |
| **Emisión ilustrativa** | Un cálculo retrospectivo que muestra cómo sería una emisión; no entra al registro. |
| **Registro prospectivo** | La lista de pronósticos guardados antes de conocer el resultado. No se puede editar. |
| **Modelo en prueba** | Una versión nueva que se registra al lado; si gana durante 26 semanas, reemplaza al modelo registrado. |
| **kWh** | Kilovatio-hora: la unidad de energía. |
""")
    with st.expander("Detalles técnicos y supuestos completos"):
        st.markdown("""
- **Objetivo principal (E26):** precio nacional de bolsa de s+2 (Ridge con corrección de sesgo) por la diferencia entre las compras TIE y el precio nacional de s-1.
- **Objetivo de referencia (E16 y E24):** regresión Ridge sobre el cambio del logaritmo del precio entre la semana s-1 y la s+2, con corrección de sesgo de Duan. Usa variables de la semana s-1, el precio de sábado a martes de la semana s y el costo marginal del despacho programado de miércoles a viernes de s.
- **Objetivo complementario (E19 y E20):** promedio entre la regla de referencia y una regresión robusta (Huber) sobre el cambio del precio de exportación; cota calibrada aparte en las semanas con reglas especiales (E20).
- **Evaluación:** walk-forward con reentrenamiento cada 4 semanas y 2 semanas de embargo; significancia con Diebold-Mariano (varianza de Newey-West). Todos los experimentos están en `docs/EXPERIMENTOS.md`.
""")
        st.markdown(f"- **Regla temporal:** {pr.REGLA_ATRIBUIDA}\n- **Monto aproximado:** {pr.NOTA_E22}\n"
                    f"- **Fuentes:** {pr.FUENTES}")
        st.markdown(pr.sin_frases((RAIZ / "docs" / "SUPUESTOS.md").read_text(encoding="utf-8")))


def semana_siguiente():
    st.title("Experimento complementario: horizonte de una semana")
    st.markdown("""
Este fue el **primer planteamiento** del proyecto: pronosticar el precio nacional de bolsa de la **semana siguiente**
(de lunes a domingo, horizonte de una semana). **No es el modelo principal ni un modelo de garantía:** la garantía usa
la semana objetivo s+2, de sábado a viernes. Se conserva porque aquí se compararon **13 modelos distintos**.

La referencia de este experimento es **copiar la semana pasada**.
""")
    periodo = st.selectbox("Periodo de evaluación", list(PERIODOS), key="per_sem")
    p = filtrar(SEMANA, periodo)
    nombres = MODELOS.modelo.tolist()
    t = tabla(p, nombres, "Copiar la semana pasada", None, "Precio nacional de bolsa, semana siguiente",
              "COP/kWh").merge(MODELOS.rename(columns={"modelo": "Modelo", "descripcion": "Qué es"})[["Modelo", "Qué es"]],
                               on="Modelo")
    t = t[["Modelo", "Qué es", *[c for c in t.columns if c not in ("Modelo", "Qué es")]]]
    mostrar_tabla(t, "COP/kWh", 1)
    st.markdown("""
- **Casi todos los modelos quedan parecidos:** los más complejos no ganan a los simples.
- **El que más mejora usa el costo marginal programado de la misma semana**, que solo se conoce cuando la semana ya empezó.
""")
    sel = st.multiselect("Modelos en el gráfico", nombres,
                         default=["Copiar la semana pasada", "Ridge 14 (modelo base del experimento)",
                                  "Ridge 14 + costo marginal 3 días"])
    st.markdown("**Precio nacional de bolsa de la semana siguiente (lunes a domingo): valor observado y modelos**")
    st.caption(f"Unidad: COP/kWh · Periodo: {periodo_texto(p)} · Semanas: {len(p.dropna(subset=['real']))} · Fuente: "
               "API pública de XM (PrecBolsNaci). Backtest histórico.")
    st.plotly_chart(grafico(p, sel, "COP/kWh"), width="stretch")
    with st.expander("Registro de pronósticos de la semana siguiente (detenido el 15 de noviembre de 2026)"):
        r = REG_SEMANA[["fecha_emision", "semana_objetivo", "estado", "pronostico", "cota90", "real_provisional"]]
        st.dataframe(r, hide_index=True, width="stretch")


# --- Navegación -----------------------------------------------------------------------------------------------
# APP_PAGINA permite abrir otra página por defecto (lo usan los tests para recorrerlas todas).
_INICIAL = os.environ.get("APP_PAGINA", "")
st.markdown(CSS, unsafe_allow_html=True)  # contraste de tarjetas, tablas y etiquetas


def _pagina(funcion, titulo, icono, ruta=""):
    extra = {"url_path": ruta} if ruta else {}
    return st.Page(funcion, title=titulo, icon=icono, default=_INICIAL == ruta, **extra)


PAGINAS = {
    "inicio": _pagina(inicio, "Inicio", "🏠"),
    # Títulos cortos en el menú (el grupo da el contexto); el título completo va en cada página.
    "principal": _pagina(compras, "Principal: compras TIE", "🎯", "compras"),
    "referencia": _pagina(bolsa, "Referencia: precio de bolsa", "📈", "bolsa"),
    "complementario": _pagina(exportacion, "Complementario: exportación", "💵", "exportacion"),
    "emision": _pagina(emision, "Emisión ilustrativa y registro", "🔎", "pronostico"),
    "informe": _pagina(informe, "Informe PDF", "📄", "informe"),
    "como": _pagina(como_funciona, "Construcción y evaluación", "🧭", "como"),
    "semana": _pagina(semana_siguiente, "Experimento de una semana", "🗓️", "semana"),
}
pg = st.navigation({
    "Análisis principal": [PAGINAS[k] for k in ("inicio", "principal", "referencia", "complementario")],
    "Operación y registro": [PAGINAS["emision"], PAGINAS["informe"]],
    "Metodología": [PAGINAS["como"], PAGINAS["semana"]],
})
with st.sidebar:
    st.markdown("**Calendario de emisión**")
    calendario()
    st.caption("Referencia: semana s-1. Semana objetivo: s+2, de sábado a viernes. " + pr.NO_VALIDADO)
pg.run()
