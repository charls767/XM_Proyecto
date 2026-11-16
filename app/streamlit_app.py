"""App del proyecto XM–UNAL: ¿cuánto costará la energía que Colombia vende a Ecuador?

Uso local:  streamlit run app/streamlit_app.py
Lee solo results/app/ (lo genera `python src/resultados_app.py`) y docs/SUPUESTOS.md.

Páginas:
1. Inicio: qué problema resolvemos y el resultado en una pantalla.
2. Precio realizado de exportación: lo que Ecuador pagó por kWh (reconstruido; no es el precio oficial del depósito).
3. Precio de bolsa: el precio general del mercado, con crisis y saltos.
4. Pronóstico de esta semana: lo último que se registró y por qué.
5. Extra, la semana siguiente: el primer planteamiento, con 13 modelos.
6. Cómo funciona: pasos, glosario y supuestos.
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
import isa101 as isa  # noqa: E402  (paleta ISA-101 compartida con el informe PDF)
import config  # noqa: E402  (definición de los tres objetivos y su condición de oficial o reconstruido)

st.set_page_config(page_title="Precio de la energía para Ecuador", page_icon="⚡", layout="wide")

# --- Nombres simples para los modelos ---------------------------------------------------------------
REGLA = "Regla actual de XM"
NUESTRO = "Nuestro modelo"
PRUEBA = "Modelo en prueba"
NOMBRES_SIMPLES = {
    # Precio de bolsa (referencia) y precio realizado de exportación (complementario)
    "Regla XM (repetir s-1)": REGLA,
    "Modelo registrado (sábado a martes + costo marginal mié-vie, con corrección de sesgo)": NUESTRO,
    "Modelo elegido (Huber + regla)": NUESTRO,
    "Candidato en paralelo (+ hidrología hasta el jueves y martes)": PRUEBA,
    "Modelo anterior (sin costo marginal)": "Versión anterior de nuestro modelo",
    "Regla con sábado a martes de s": "Regla con los días más recientes",
    "Ridge 14": "Modelo básico",
    "Ridge 14 con corrección de sesgo": "Modelo básico, sin tendencia a quedarse corto",
    "Ridge 14 + sábado a martes de s": "Modelo básico + días recientes",
    "Ridge 14 + sábado a martes de s, con corrección de sesgo": "Modelo básico + días recientes, sin tendencia a quedarse corto",
    "Huber + sábado a martes": "Variante: con días recientes",
    "Huber": "Variante: solo el modelo, sin la regla",
    "Precio nacional × diferencial": "Variante: precio nacional ajustado",
    "Ridge + nacional + sábado a martes": "Variante: con el precio nacional",
    "LightGBM": "Variante: árboles de decisión",
    # Pronóstico a una semana
    "Ingenuo": "Copiar la semana pasada",
}

# --- Colores según ISA-101 (src/isa101.py) ------------------------------------------------------------
# Lo normal va en grises; un solo acento sobrio (azul pizarra) para nuestro modelo; el color saturado
# solo marca lo anormal (rojo: el precio superó el techo). La identidad también va en el trazo.
INK, INK2, MUTED, GRID, BASE = isa.TEXTO, isa.TEXTO_2, isa.TEXTO_TENUE, isa.REJILLA, isa.EJE
COLOR = {REGLA: isa.REGLA, NUESTRO: isa.MODELO, PRUEBA: isa.PRUEBA, "Copiar la semana pasada": isa.REGLA,
         "Ridge 14 (oficial)": isa.MODELO}
TRAZO = {REGLA: "dash", "Copiar la semana pasada": "dash", NUESTRO: "solid", "Ridge 14 (oficial)": "solid"}
TRAZOS_ALTERNATIVOS = ["dot", "dashdot", "longdash", "longdashdot"]


ALARMA = ("Triángulo rojo: semana en que el precio real superó el techo. Es la única alarma de la gráfica: "
          "lo normal va en grises (norma ISA-101).")


def trazo(m, i=0):
    """Color y trazo de una serie: la regla gris discontinua, nuestro modelo azul pizarra, el resto gris."""
    return COLOR.get(m, isa.PRUEBA), TRAZO.get(m, TRAZOS_ALTERNATIVOS[i % len(TRAZOS_ALTERNATIVOS)])


def indicador_estado(estado):
    """Indicador de estado ISA-101: gris si es normal; color y símbolo solo si es anormal."""
    e = str(estado or "normal").lower()
    fondo = isa.ESTADO_COLOR.get(e, isa.FONDO_PANEL)
    st.markdown(f"<div style='background:{fondo};border:1px solid {isa.EJE};padding:6px 12px;display:inline-block;"
                f"font-weight:600;color:{isa.TEXTO}'>Estado: {isa.ESTADO_TEXTO.get(e, e)}</div>",
                unsafe_allow_html=True)
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
    return tie, expo, semana, modelos, episodios, ctx_expo, reg_semana, ultimo


def _renombrar(c):
    if c.startswith("cota|"):
        return "cota|" + NOMBRES_SIMPLES.get(c[5:], c[5:])
    return NOMBRES_SIMPLES.get(c, c)


TIE, EXPO, SEMANA, MODELOS, EPISODIOS, CTX_EXPO, REG_SEMANA, ULTIMO = cargar(
    max(a.stat().st_mtime for a in DATOS.iterdir()))


def modelos_de(p):
    return [c for c in p.columns if c not in ("semana_objetivo", "real", "base", "regimen_expo")
            and not c.startswith("cota|")]


# --- Cálculos ----------------------------------------------------------------------------------------

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
    """La respuesta a "¿la diferencia es real o pudo ser suerte?", en palabras."""
    if np.isnan(p):
        return "Muy pocas semanas para saber"
    if p < 0.05:
        return "Sí, es real"
    if p < 0.10:
        return "Casi seguro"
    return "No se puede asegurar"


def tabla(p, modelos, referencia):
    """Una fila por modelo con medidas fáciles de leer."""
    filas = []
    error_ref = (p[referencia] - p.real).abs().mean()
    for m in modelos:
        s = p.dropna(subset=[m])
        e = s[m] - s.real
        fila = {"Modelo": m, "Error promedio": e.abs().mean(),
                "Error típico (% del precio)": (e.abs() / s.real).median() * 100,
                "Cuánto mejor que la referencia (%)": (1 - e.abs().mean() / error_ref) * 100 if m != referencia else 0.0,
                "Desvío promedio": e.mean()}
        cota = f"cota|{m}"
        fila["Semanas bajo el techo (%)"] = (s.real <= s[cota]).mean() * 100 if cota in s else np.nan
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("Error promedio")


def formato(unidad, decimales):
    f = f"%.{decimales}f"
    return {
        "Error promedio": st.column_config.NumberColumn(f"Error promedio ({unidad})", format=f,
                                                        help="Cuánto se equivoca en promedio. Más bajo es mejor."),
        "Error típico (% del precio)": st.column_config.NumberColumn(format="%.0f %%",
                                                                     help="El error de una semana normal, como porcentaje del precio."),
        "Cuánto mejor que la referencia (%)": st.column_config.NumberColumn(format="%+.0f %%",
                                                                            help="Positivo: se equivoca menos que la referencia."),
        "Desvío promedio": st.column_config.NumberColumn(format=f"%+.{decimales}f",
                                                         help="Negativo: en promedio se queda corto (adivina menos de lo que fue)."),
        "Semanas bajo el techo (%)": st.column_config.NumberColumn(format="%.0f %%",
                                                                   help="El techo es un valor alto que el precio real no debería pasar. La meta es 90 %."),
    }


# --- Gráficos ----------------------------------------------------------------------------------------

def estilo(fig, alto=380, titulo_y=None):
    """Estilo ISA-101: fondo gris neutro, rejilla tenue, sin decoración."""
    fig.update_layout(
        height=alto, margin=dict(l=8, r=8, t=30, b=8), paper_bgcolor=isa.FONDO, plot_bgcolor=isa.FONDO,
        font=dict(family=isa.FUENTE, color=isa.TEXTO_2, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
        hovermode="x unified", hoverlabel=dict(bgcolor=isa.FONDO_PANEL, font_color=isa.TEXTO))
    fig.update_xaxes(showgrid=False, linecolor=isa.EJE, ticks="outside", tickcolor=isa.EJE)
    fig.update_yaxes(gridcolor=isa.REJILLA, zeroline=False, title=titulo_y, title_font_color=isa.TEXTO_TENUE)
    return fig


def grafico(p, modelos, unidad, techo=None, puntos=False, alto=420):
    """Lo que pasó (negro), lo que adivinó cada modelo (gris o azul pizarra) y, si se pide, el techo de uno.

    Las semanas en que el precio real superó el techo se marcan en rojo con un triángulo: es la única
    condición anormal de la gráfica (ISA-101).
    """
    fig = go.Figure()
    if puntos:  # sin exportación no hay dato: huecos en vez de líneas que unen periodos vacíos
        p = p.set_index("semana_objetivo")
        p = p.reindex(pd.date_range(p.index.min(), p.index.max(), freq="7D")).rename_axis("semana_objetivo").reset_index()
    cota = f"cota|{techo}" if techo else None
    if cota and cota in p:
        fig.add_scatter(x=p.semana_objetivo, y=p[cota], name="Techo (90 %)",
                        line=dict(color=isa.TECHO, width=1.2, dash="dot"))
    modo = "lines+markers" if puntos else "lines"
    fig.add_scatter(x=p.semana_objetivo, y=p.real, name="Lo que pasó", mode=modo,
                    line=dict(color=isa.REAL, width=2.5), marker=dict(size=5, color=isa.REAL))
    for i, m in enumerate(modelos):
        color, dash = trazo(m, i)
        fig.add_scatter(x=p.semana_objetivo, y=p[m], name=m, mode="markers" if puntos else "lines",
                        line=dict(color=color, width=2, dash=dash),
                        marker=dict(size=7, color=color, symbol="square" if m == NUESTRO else "circle"))
    if cota and cota in p:
        sobre = p[p.real > p[cota]]
        if len(sobre):
            fig.add_scatter(x=sobre.semana_objetivo, y=sobre.real, mode="markers",
                            name=f"Superó el techo ({len(sobre)} semanas)",
                            marker=dict(symbol="triangle-up", size=12, color=isa.ALARMA_ALTA,
                                        line=dict(color=isa.TEXTO, width=1)))
    fig.update_traces(hovertemplate="%{y:,.2f}" if unidad.startswith("centavos") else "%{y:,.0f}")
    return estilo(fig, alto, unidad)


def barras_explicacion(aportes):
    """Gris oscuro: empuja hacia arriba; gris claro: hacia abajo. El color queda para las alarmas."""
    a = pd.DataFrame(aportes).assign(pct=lambda x: (np.exp(x.aporte_log) - 1) * 100)
    a = a.reindex(a.pct.abs().sort_values().index)
    fig = go.Figure(go.Bar(x=a.pct, y=a.nombre, orientation="h",
                           marker=dict(color=np.where(a.pct >= 0, isa.SUBE, isa.BAJA), line=dict(color=isa.EJE, width=0.5)),
                           hovertemplate="%{y}: %{x:+.1f} %<extra></extra>"))
    fig.update_xaxes(title="Cuánto empuja el precio (%)", gridcolor=GRID, showgrid=True, zeroline=True,
                     zerolinecolor=BASE)
    fig.update_yaxes(title=None, gridcolor="rgba(0,0,0,0)")
    return estilo(fig, 420).update_layout(hovermode="closest", showlegend=False)


# --- Páginas -----------------------------------------------------------------------------------------

def inicio():
    st.title("¿Cuánto costará la energía que Colombia vende a Ecuador?")
    st.markdown("""
**La historia en cuatro pasos**

1. Colombia le vende electricidad a Ecuador.
2. Para asegurar el pago, Ecuador deja **un depósito** antes de cada semana. A ese depósito se le llama *garantía*.
3. Para calcular el depósito, XM necesita **adivinar el precio** de una semana que empieza dentro de 8 días.
4. Hoy XM usa una **regla sencilla**: supone que el precio será igual al de hace tres semanas. **Este proyecto intenta adivinarlo mejor.**
""")
    with st.expander("Los tres objetivos del proyecto y qué tan oficiales son"):
        st.markdown("\n".join(
            f"- **{c.capitalize()}:** {config.etiqueta_objetivo(c)}. Fuente: {o['fuente']}. {o['validacion']}"
            for c, o in config.OBJETIVOS.items()))
        st.caption("XM no publica el precio de la garantía. Ninguna de estas variables es el precio oficial de la "
                   "garantía, y ninguna está validada para fijarla.")
    expo, bolsa = filtrar(EXPO, PRINCIPAL), filtrar(TIE, PRINCIPAL)
    for titulo, p, unidad, dec, texto in (
            ("Precio realizado de exportación (reconstruido)", expo, "centavos de dólar por kWh", 2,
             "Lo que Ecuador paga por cada kilovatio-hora."),
            ("Precio de bolsa: el precio general del mercado colombiano", bolsa, "pesos por kWh", 0,
             "El precio al que se compra y vende la energía en Colombia, hora por hora.")):
        st.subheader(titulo)
        st.caption(f"{texto} Errores promedio en {unidad}, de 2018 a 2026.")
        er, en = (p[REGLA] - p.real).abs().mean(), (p[NUESTRO] - p.real).abs().mean()
        c = st.columns(4)
        c[0].metric("Error de la regla actual", f"{er:,.{dec}f}")
        c[1].metric("Error de nuestro modelo", f"{en:,.{dec}f}", f"{(en / er - 1) * 100:+.0f} %",
                    delta_color="off")
        c[2].metric("¿La mejora es real?", confiable(p_valor(p, NUESTRO, REGLA)))
        c[3].metric("Semanas comparadas", f"{len(p)}")

    st.subheader("Lo más importante")
    ultimo = TIE.tail(52)
    er52, en52 = (ultimo[REGLA] - ultimo.real).abs().mean(), (ultimo[NUESTRO] - ultimo.real).abs().mean()
    st.markdown(f"""
- **Nuestro modelo se equivoca menos que la regla** en los dos precios. En el precio de bolsa la diferencia es clara. En el de exportación es más pequeña y menos segura, porque hay pocas semanas con exportaciones.
- **Ayuda mirar lo más reciente.** La regla solo mira una semana que ya tiene diez días de vieja. Nuestro modelo también usa los días de esta semana que ya se conocen el viernes.
- **Nadie ve venir los saltos bruscos de precio**, ni la regla ni el modelo. Ahí está el límite.
- **En el último año** (52 semanas), en el precio de bolsa: {en52:,.0f} frente a {er52:,.0f} pesos por kWh ({confiable(p_valor(ultimo, NUESTRO, REGLA)).lower()}).
""")
    boton_informe()
    st.info("**Es un prototipo de la universidad**, no una herramienta oficial de XM. Las cifras salen de una "
            "simulación con datos del pasado. La prueba de verdad es el registro de pronósticos, que empieza el "
            "20 de noviembre de 2026.")


def exportacion():
    st.title("Precio de exportación")
    st.markdown("""
**Qué es:** lo que Ecuador paga por cada kilovatio-hora que le vende Colombia, en **centavos de dólar**.
Es un precio **realizado y reconstruido** por el proyecto, **no** el precio oficial del depósito: XM no lo publica. Solo existe en las semanas en que hubo exportaciones.

**Por qué es difícil:** cambia de golpe cuando cambian las reglas o el clima, y hay pocas semanas para aprender
(solo las semanas con exportaciones).
""")
    periodo = st.selectbox("¿Qué años mirar?", list(PERIODOS), key="per_expo")
    p = filtrar(EXPO, periodo)
    st.plotly_chart(grafico(p, [REGLA, NUESTRO], "centavos de dólar por kWh", techo=NUESTRO, puntos=True), width="stretch")
    st.caption(ALARMA)
    st.dataframe(tabla(p, [REGLA, NUESTRO], REGLA), hide_index=True, width="stretch",
                 column_config=formato("centavos de dólar por kWh", 2))
    pv = p_valor(p, NUESTRO, REGLA)
    st.markdown(f"""
**Qué aprendimos**
- **Nuestro modelo es una mezcla:** la mitad es la regla de XM y la otra mitad un modelo que mira la diferencia entre este precio y el nacional, los días recientes y el estado del sistema.
- **La mejora es pequeña y no del todo segura** ({confiable(pv).lower()}). Por eso se registra cada semana al lado de la regla, para ver si se sostiene con datos nuevos.
- **Cuando el gobierno cambia las reglas de exportación** (por ejemplo, exportar solo con plantas térmicas), este precio llega a ser el doble del nacional. El techo del modelo se calcula aparte en esas semanas.
""")
    with st.expander("Ver todas las variantes que se probaron"):
        st.dataframe(tabla(p, modelos_de(p), REGLA), hide_index=True, width="stretch",
                     column_config=formato("centavos de dólar por kWh", 2))
    with st.expander("Ver el precio de exportación al lado del precio nacional"):
        c = CTX_EXPO[CTX_EXPO.index >= "2018-01-01"]
        fig = go.Figure()
        fig.add_scatter(x=c.index, y=c.precio, name="Precio nacional", line=dict(color=isa.REGLA, width=2, dash="dash"))
        fig.add_scatter(x=c.index, y=c.precio_expo_cop, name="Precio de exportación", mode="lines+markers",
                        line=dict(color=isa.MODELO, width=2), marker=dict(size=5))
        fig.update_traces(hovertemplate="%{y:,.0f}")
        st.plotly_chart(estilo(fig, 360, "pesos por kWh"), width="stretch")
        st.caption("Desde 2023 el precio de exportación se separa del nacional. Desde agosto de 2026 llega a ser varias veces mayor.")


def bolsa():
    st.title("Precio de bolsa")
    st.markdown("""
**Qué es:** el precio general de la energía en Colombia, en **pesos por kilovatio-hora**. Es la base del mercado.
Aquí se pronostica el promedio de una semana (de sábado a viernes) que empieza dentro de 8 días.

**Qué usa nuestro modelo:** el precio y el clima de la semana pasada, los días de esta semana que ya se conocen,
y el precio que el sistema planea para los próximos días.
""")
    periodo = st.selectbox("¿Qué años mirar?", list(PERIODOS), key="per_bolsa")
    p = filtrar(TIE, periodo)
    principales = [REGLA, NUESTRO, PRUEBA]
    techo = st.toggle("Mostrar el techo de nuestro modelo", key="techo_bolsa")
    st.plotly_chart(grafico(p, [REGLA, NUESTRO], "pesos por kWh", techo=NUESTRO if techo else None), width="stretch")
    if techo:
        st.caption(ALARMA)
    st.dataframe(tabla(p, principales, REGLA), hide_index=True, width="stretch", column_config=formato("pesos por kWh", 1))
    st.caption("El **modelo en prueba** suma el clima de esta semana. Se registra al lado del nuestro; si después de "
               "26 semanas reales se equivoca menos, lo reemplaza.")
    with st.expander("Ver todas las variantes que se probaron"):
        st.dataframe(tabla(p, modelos_de(p), REGLA), hide_index=True, width="stretch", column_config=formato("pesos por kWh", 1))

    st.subheader("¿Y en las crisis?")
    st.markdown("Semanas en que el precio se dispara. Es cuando más importa no quedarse corto.")
    ep = st.selectbox("Crisis", EPISODIOS.episodio.tolist())
    f = EPISODIOS.set_index("episodio").loc[ep]
    q = TIE[(TIE.semana_objetivo >= f.inicio) & (TIE.semana_objetivo <= f.fin)]
    if q.empty:
        st.info("Esta crisis todavía no tiene semanas evaluadas.")
    else:
        st.dataframe(tabla(q, principales, REGLA), hide_index=True, width="stretch", column_config=formato("pesos por kWh", 1))
        st.plotly_chart(grafico(q, [REGLA, NUESTRO], "pesos por kWh", techo=NUESTRO, alto=380), width="stretch")

    st.subheader("¿Ve venir los saltos?")
    st.markdown("Cada semana se marca como **Baja** (cae más de 20 %), **Igual** o **Sube** (sube 25 % o más). "
                "La tabla cuenta cuántas veces el modelo dijo lo mismo que pasó.")
    m = st.radio("Modelo", [NUESTRO, PRUEBA], horizontal=True)
    q = p.dropna(subset=[m])

    def clase(x):
        return pd.cut(np.log(x / q.base), [-np.inf, UMBRAL_BAJA, UMBRAL_SUBE, np.inf], right=False,
                      labels=["Baja", "Igual", "Sube"])

    t = pd.crosstab(clase(q.real), clase(q[m])).reindex(index=["Baja", "Igual", "Sube"],
                                                        columns=["Baja", "Igual", "Sube"], fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=t.values, x=[f"Dijo: {c}" for c in t.columns], y=[f"Pasó: {r}" for r in t.index],
        colorscale=isa.ESCALA_GRISES, showscale=False,
        text=t.values, texttemplate="%{text}", textfont=dict(size=16),
        hovertemplate="%{y} · %{x}: %{z} semanas<extra></extra>", xgap=2, ygap=2))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(estilo(fig, 320).update_layout(hovermode="closest"), width="stretch")
    sube, baja = t.loc["Sube"].sum(), t.loc["Baja"].sum()
    st.markdown(f"De **{sube}** semanas en que el precio subió fuerte, el modelo lo vio venir en **{t.at['Sube', 'Sube']}**. "
                f"De **{baja}** en que bajó fuerte, en **{t.at['Baja', 'Baja']}**. La regla de XM nunca anticipa "
                "cambios: siempre dice *Igual*.")


def boton_informe():
    """Descarga del informe PDF que se genera en cada corrida (src/informe_pdf.py)."""
    pdf = DATOS / "informe_ultimo.pdf"
    if pdf.exists():
        st.download_button("Descargar el informe en PDF", pdf.read_bytes(), file_name="informe_garantia_TIE.pdf",
                           mime="application/pdf", help="Resumen, gráficas, desempeño, registro y supuestos. "
                                                        "Se genera automáticamente en cada corrida.")


def pronostico():
    st.title("Pronóstico de esta semana")
    boton_informe()
    archivo = DATOS / "registro_tie.csv"
    st.markdown("Cada viernes se guarda el pronóstico **antes de saber qué pasa**, en un registro que no se puede "
                "editar (cada fila tiene una huella digital encadenada a la anterior). Es la prueba de verdad del modelo.")
    if archivo.exists():
        r = pd.read_csv(archivo, parse_dates=["fecha_emision", "semana_objetivo"])
        u = r.iloc[-1]
        st.subheader(f"Último pronóstico registrado: {u.fecha_emision:%d/%m/%Y}")
        st.caption(f"Para la semana del {u.semana_objetivo:%d/%m/%Y} al {u.semana_objetivo + pd.Timedelta(days=6):%d/%m/%Y}.")
        c = st.columns(4)
        c[0].metric("Regla de XM (pesos por kWh)", f"{u.regla_xm:,.0f}")
        c[1].metric("Nuestro modelo (pesos por kWh)", f"{u.pronostico:,.0f}")
        c[2].metric("Techo (pesos por kWh)", f"{u.cota90:,.0f}")
        with c[3]:
            indicador_estado(u.estado)
        if "expo_pronostico" in r and pd.notna(u.get("expo_pronostico")):
            c = st.columns(4)
            c[0].metric("Exportación, regla (centavos de dólar)", f"{u.expo_regla:,.2f}")
            c[1].metric("Exportación, nuestro modelo", f"{u.expo_pronostico:,.2f}")
            c[2].metric("Exportación, techo", f"{u.expo_cota90:,.2f}")
        with st.expander("Ver todo el registro"):
            st.dataframe(r, hide_index=True, width="stretch")
    else:
        st.info("El primer pronóstico se registra el viernes 20 de noviembre de 2026, para la semana del 28 de "
                "noviembre al 4 de diciembre.")

    u = ULTIMO
    st.subheader("Ejemplo con los datos de hoy")
    st.caption(f"Calculado como si fuera el viernes {pd.Timestamp(u['fecha_calculo']):%d/%m/%Y}, para la semana del "
               f"{pd.Timestamp(u['semana_objetivo']):%d/%m/%Y}. No está en el registro.")
    c = st.columns(3)
    c[0].metric("Regla de XM (pesos por kWh)", f"{u['regla_xm']:,.0f}")
    c[1].metric("Nuestro modelo (pesos por kWh)", f"{u['pronostico']:,.0f}",
                f"{(u['pronostico'] / u['regla_xm'] - 1) * 100:+.0f} % frente a la regla", delta_color="off")
    c[2].metric("Techo (pesos por kWh)", f"{u['cota90']:,.0f}")
    indicador_estado(u.get("estado"))
    if u.get("estado") == "respaldo":
        st.caption("Ese día faltaba un dato del sistema, así que se usó la versión de respaldo del modelo.")
    st.markdown("**¿Por qué dice eso?** Cada barra muestra cuánto empuja una pieza de información el precio "
                "hacia arriba (gris oscuro) o hacia abajo (gris claro), comparado con una semana normal. Siguiendo ISA-101, el color se reserva para las alarmas.")
    st.plotly_chart(barras_explicacion(u["aportes"]), width="stretch")


def semana_siguiente():
    st.title("Extra: el precio de la semana siguiente")
    st.markdown("""
Este fue el **primer planteamiento** del proyecto: adivinar el precio de la **próxima** semana (de lunes a domingo).
No sirve para el depósito, porque el depósito se calcula con 8 días de anticipación. Se conserva porque aquí se
compararon **13 modelos distintos** y muestra qué tan lejos se puede llegar.

La referencia es **copiar la semana pasada**.
""")
    periodo = st.selectbox("¿Qué años mirar?", list(PERIODOS), key="per_sem")
    p = filtrar(SEMANA, periodo)
    nombres = MODELOS.modelo.tolist()
    t = tabla(p, nombres, "Copiar la semana pasada").merge(
        MODELOS.rename(columns={"modelo": "Modelo", "descripcion": "Qué es"})[["Modelo", "Qué es"]], on="Modelo")
    t = t[["Modelo", "Qué es", *[c for c in t.columns if c not in ("Modelo", "Qué es")]]]
    st.dataframe(t, hide_index=True, width="stretch", column_config=formato("pesos por kWh", 1))
    st.markdown("""
- **Casi todos los modelos quedan parecidos**: los más complejos no ganan a los simples.
- **El que más mejora usa el precio que el sistema planea para la misma semana** (costo marginal programado), que solo se conoce cuando la semana ya empezó.
""")
    sel = st.multiselect("Modelos en el gráfico", nombres,
                         default=["Copiar la semana pasada", "Ridge 14 (oficial)", "Ridge 14 + costo marginal 3 días"])
    st.plotly_chart(grafico(p, sel, "pesos por kWh"), width="stretch")
    with st.expander("Registro de pronósticos de la semana siguiente (detenido el 15 de noviembre de 2026)"):
        r = REG_SEMANA[["fecha_emision", "semana_objetivo", "estado", "pronostico", "cota90", "real_provisional"]]
        st.dataframe(r, hide_index=True, width="stretch")


def como_funciona():
    st.title("Cómo funciona")
    st.markdown("""
**Los pasos, cada viernes**

1. **Se bajan los datos** públicos de XM: precios, cuánta agua hay en los embalses, cuánta lluvia llega a los ríos, cuánto se exportó.
2. **Se arma un resumen por semana** (de sábado a viernes).
3. **El modelo aprende del pasado:** busca cómo cambiaron los precios después de semanas parecidas. Solo usa semanas cuyo resultado ya se conoce.
4. **Se hace el pronóstico** de la semana que empieza dentro de 8 días, y se calcula un **techo**.
5. **Se guarda en el registro**, junto a lo que diría la regla de XM. Cuando llega el precio real, se califica.

**Cómo sabemos que funciona:** se repitió el paso 3 y 4 para cada semana desde 2014, usando solo lo que se sabía
en ese momento, como si viajáramos en el tiempo. Así se mide el error sin hacer trampa. Los años 2022–2024 se
usaron para elegir el modelo, y 2025–2026 se guardaron para la prueba final.
""")
    st.subheader("Glosario")
    st.markdown("""
| Palabra | Qué significa |
|---|---|
| **Garantía** | El depósito que deja Ecuador antes de cada semana para asegurar que pagará. |
| **Regla actual de XM** | Suponer que el precio será igual al de hace tres semanas. Es lo que se usa hoy. |
| **Error promedio** | Cuánto se equivoca un pronóstico, en promedio. Más bajo es mejor. |
| **Desvío promedio** | Si el pronóstico tiende a quedarse corto (negativo) o a pasarse (positivo). |
| **Techo** | Un valor alto que el precio real no debería superar en 9 de cada 10 semanas. Sirve para un depósito prudente. |
| **¿La mejora es real?** | Si la diferencia con la regla es tan grande que no pudo ser suerte. |
| **Registro** | La lista de pronósticos guardados antes de saber el resultado. No se puede editar. |
| **Modelo en prueba** | Una versión nueva que se registra al lado; si gana durante 26 semanas, reemplaza a la nuestra. |
| **kWh** | Kilovatio-hora: la unidad en que se mide la energía. |
""")
    with st.expander("Detalles técnicos y supuestos completos"):
        st.markdown("""
- **Precio de bolsa:** regresión Ridge sobre el cambio del logaritmo del precio entre la semana s-1 y la s+2, con corrección de sesgo de Duan. Usa variables de la semana s-1, el precio de sábado a martes de la semana s y el costo marginal del despacho programado de miércoles a viernes de s.
- **Precio de exportación:** promedio entre la regla de XM y una regresión robusta (Huber) sobre el cambio del precio de exportación.
- **Techo:** cota conformal del 90 % con los errores de las últimas 104 semanas ya calificadas; en exportación, calculada aparte en las semanas con reglas especiales.
- **Evaluación:** walk-forward con reentrenamiento cada 4 semanas y 2 semanas de embargo; significancia con Diebold-Mariano (varianza de Newey-West). Todos los experimentos están en `docs/EXPERIMENTOS.md`.
""")
        st.markdown((RAIZ / "docs" / "SUPUESTOS.md").read_text(encoding="utf-8"))


# APP_PAGINA permite abrir otra página por defecto (lo usan los tests para recorrerlas todas).
_INICIAL = os.environ.get("APP_PAGINA", "")
pg = st.navigation([
    st.Page(inicio, title="Inicio", icon="🏠", default=_INICIAL == ""),
    st.Page(exportacion, title="Precio de exportación", icon="💵", url_path="exportacion", default=_INICIAL == "exportacion"),
    st.Page(bolsa, title="Precio de bolsa", icon="📈", url_path="bolsa", default=_INICIAL == "bolsa"),
    st.Page(pronostico, title="Pronóstico de esta semana", icon="🔎", url_path="pronostico", default=_INICIAL == "pronostico"),
    st.Page(semana_siguiente, title="Extra: la semana siguiente", icon="🗓️", url_path="semana", default=_INICIAL == "semana"),
    st.Page(como_funciona, title="Cómo funciona", icon="📄", url_path="como", default=_INICIAL == "como"),
])
pg.run()
