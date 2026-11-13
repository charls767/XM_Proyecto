"""App de resultados del pronóstico semanal del precio de bolsa (caso XM–UNAL).

Uso local:  streamlit run app/streamlit_app.py
Lee solo results/app/ (lo genera `python src/resultados_app.py`) y docs/SUPUESTOS.md.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "results" / "app"

st.set_page_config(page_title="Pronóstico del precio de bolsa", page_icon="⚡", layout="wide")

# --- Colores: cada modelo tiene siempre el mismo color, sin importar cuántos se muestren ---------
INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
COLOR = {
    "Ridge 14 (oficial)": "#2a78d6",
    "Ridge 14 + costo marginal": "#eb6834",
    "Ensamble Ridge + LEAR": "#1baf7a",
    "LightGBM": "#eda100",
    "SARIMAX": "#e87ba4",
    "Ensamble Ridge + LightGBM + SARIMAX": "#008300",
    "LEAR diario": "#6250d6",
    "Ridge 19": "#e34948",
    "ARIMA": INK2,
    "Ingenuo": MUTED,
    "Estacional": BASE,
}
PRINCIPALES = ["Ridge 14 (oficial)", "Ensamble Ridge + LEAR", "Ridge 14 + costo marginal"]
PERIODOS = {
    "Evaluación 2018–2026": ("2018-01-01", "2026-12-31"),
    "Desarrollo 2014–2021": ("2014-01-01", "2021-12-31"),
    "Selección 2022–2024": ("2022-01-01", "2024-12-31"),
    "Prueba final 2025–2026": ("2025-01-01", "2026-12-31"),
    "Toda la historia 2014–2026": ("2014-01-01", "2026-12-31"),
}
# Clases de movimiento: igual que E14 (cambio < −20 %, entre ambos, ≥ +25 %).
UMBRAL_BAJA, UMBRAL_SUBE = np.log(0.80), np.log(1.25)


def estilo(fig, alto=380, titulo_y="COP/kWh"):
    fig.update_layout(
        height=alto, margin=dict(l=8, r=8, t=30, b=8), paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK2, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
        hovermode="x unified", hoverlabel=dict(bgcolor="white", font_color=INK),
    )
    fig.update_xaxes(showgrid=False, linecolor=BASE, ticks="outside", tickcolor=BASE)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title=titulo_y, title_font_color=MUTED)
    return fig


@st.cache_data
def cargar():
    p = pd.read_parquet(DATOS / "predicciones.parquet")
    modelos = pd.read_csv(DATOS / "modelos.csv")
    episodios = pd.read_csv(DATOS / "episodios.csv")
    contexto = pd.read_parquet(DATOS / "contexto.parquet")
    reg = pd.read_csv(DATOS / "registro.csv", parse_dates=["fecha_emision", "semana_base", "semana_objetivo"])
    ultimo = json.loads((DATOS / "ultimo.json").read_text(encoding="utf-8"))
    return p, modelos, episodios, contexto, reg, ultimo


P, MODELOS, EPISODIOS, CONTEXTO, REG, ULTIMO = cargar()
NOMBRES = MODELOS.modelo.tolist()


def filtrar(p, ini, fin):
    return p[(p.semana_objetivo >= pd.Timestamp(ini)) & (p.semana_objetivo <= pd.Timestamp(fin))]


def metricas(p, modelos):
    filas = []
    mae_ing = (p["Ingenuo"] - p.real).abs().mean()
    real_cambio = np.sign(p.real - p.base)
    for m in modelos:
        s = p.dropna(subset=[m])
        e = s[m] - s.real
        fila = {
            "Modelo": m, "Semanas": len(s), "MAE": e.abs().mean(), "RMSE": np.sqrt((e ** 2).mean()),
            "Error %": (e.abs() / s.real).mean() * 100, "Sesgo": e.mean(),
            "Mejora vs ingenuo %": (1 - e.abs().mean() / mae_ing) * 100 if m != "Ingenuo" else 0.0,
            "Acierta el sentido %": (np.sign(s[m] - s.base) == real_cambio.loc[s.index]).mean() * 100
            if m != "Ingenuo" else np.nan,
        }
        col = f"cota|{m}"
        fila["Cobertura cota 90 %"] = (s.real <= s[col]).mean() * 100 if col in s else np.nan
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("MAE")


FORMATO = {
    "MAE": st.column_config.NumberColumn("MAE (COP/kWh)", format="%.1f"),
    "RMSE": st.column_config.NumberColumn("RMSE", format="%.1f"),
    "Error %": st.column_config.NumberColumn("Error medio %", format="%.1f"),
    "Sesgo": st.column_config.NumberColumn("Sesgo", format="%+.1f", help="Negativo: se queda corto"),
    "Mejora vs ingenuo %": st.column_config.NumberColumn(format="%+.1f"),
    "Acierta el sentido %": st.column_config.NumberColumn(format="%.0f"),
    "Cobertura cota 90 %": st.column_config.NumberColumn(format="%.0f"),
}


def grafico_series(p, modelos, alto=420, cota=None):
    fig = go.Figure()
    if cota and f"cota|{cota}" in p:
        fig.add_scatter(x=p.semana_objetivo, y=p[f"cota|{cota}"], name=f"Cota 90 % ({cota})",
                        line=dict(color=COLOR[cota], width=1, dash="dot"), opacity=0.7)
    fig.add_scatter(x=p.semana_objetivo, y=p.real, name="Precio real", line=dict(color=INK, width=2))
    for m in modelos:
        fig.add_scatter(x=p.semana_objetivo, y=p[m], name=m,
                        line=dict(color=COLOR.get(m, INK2), width=2, dash="dash" if m == "Ingenuo" else None))
    fig.update_traces(hovertemplate="%{y:,.0f}")
    return estilo(fig, alto)


# --- Páginas ---------------------------------------------------------------------------------------

def resumen():
    st.title("Pronóstico semanal del precio de bolsa")
    st.caption("Caso XM–UNAL · precio promedio de la semana siguiente, ponderado por demanda · "
               "prototipo académico, no validado para fijar garantías")
    ev = metricas(filtrar(P, *PERIODOS["Evaluación 2018–2026"]), ["Ingenuo", *PRINCIPALES]).set_index("Modelo")
    of, cmg = ev.loc["Ridge 14 (oficial)"], ev.loc["Ridge 14 + costo marginal"]

    c = st.columns(4)
    c[0].metric("Error medio del oficial (COP/kWh)", f"{of.MAE:.1f}",
                f"{-of['Mejora vs ingenuo %']:.1f} % frente al ingenuo", delta_color="inverse")
    c[1].metric("Error típico (% del precio)", f"{of['Error %']:.0f} %")
    c[2].metric("Cobertura de la cota 90 %", f"{of['Cobertura cota 90 %']:.1f} %", "meta 90 %", delta_color="off")
    c[3].metric("Con costo marginal (COP/kWh)", f"{cmg.MAE:.1f}",
                f"{-cmg['Mejora vs ingenuo %']:.1f} % frente al ingenuo", delta_color="inverse")
    st.caption("Evaluación simulada 2018–2026: cada semana se pronosticó solo con lo que se sabía antes, "
               "reentrenando cada 4 semanas. Ingenuo = repetir el precio de la semana anterior.")

    st.subheader("Últimos dos años: real frente a los modelos principales")
    reciente = P[P.semana_objetivo >= P.semana_objetivo.max() - pd.Timedelta(weeks=104)]
    st.plotly_chart(grafico_series(reciente, ["Ingenuo", "Ridge 14 (oficial)", "Ridge 14 + costo marginal"]),
                    use_container_width=True)

    st.subheader("Qué dicen los resultados")
    st.markdown(f"""
- **El modelo oficial erra {of.MAE:.0f} COP/kWh por semana**, {of['Mejora vs ingenuo %']:.0f} % menos que repetir el precio anterior, y acierta si el precio sube o baja en {of['Acierta el sentido %']:.0f} % de las semanas.
- **Su cota del 90 % cubre {of['Cobertura cota 90 %']:.0f} % de las semanas**, como se diseñó, pero solo ~70 % de las semanas de salto.
- **El costo marginal del despacho programado es la mejor información disponible**: con el lunes y el martes de la semana objetivo el error baja a {cmg.MAE:.0f} COP/kWh. Sirve solo si la garantía se fija con la semana ya iniciada.
- **Ningún modelo anticipa bien los saltos bruscos**: fallan sobre todo por pronosticar estabilidad.
""")


def capacidad():
    st.title("Capacidad predictiva")
    c1, c2 = st.columns([1, 2])
    periodo = c1.selectbox("Periodo de evaluación", list(PERIODOS), index=0)
    sel = c2.multiselect("Modelos en el gráfico", NOMBRES, default=["Ingenuo", *PRINCIPALES])
    p = filtrar(P, *PERIODOS[periodo])
    st.caption(f"{len(p)} semanas, de {p.semana_objetivo.min():%d/%m/%Y} a {p.semana_objetivo.max():%d/%m/%Y}. "
               "Todos los modelos se evalúan en las mismas semanas, fuera de muestra.")

    t = metricas(p, NOMBRES)
    st.subheader("Comparación de todos los modelos")
    st.dataframe(t, hide_index=True, use_container_width=True, column_config=FORMATO)
    st.caption("La cobertura solo aplica a los modelos con cota calibrada. "
               "‘Ridge 14 + costo marginal’ usa información de la semana objetivo ya iniciada.")

    st.subheader("Error medio por modelo")
    t2 = t.sort_values("MAE", ascending=True)
    fig = go.Figure(go.Bar(
        x=t2.MAE, y=t2.Modelo, orientation="h", marker=dict(color=[COLOR.get(m, INK2) for m in t2.Modelo]),
        text=[f"{v:.1f}" for v in t2.MAE], textposition="outside", hovertemplate="%{y}: %{x:.1f} COP/kWh<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title=None)
    estilo(fig, 40 * len(t2) + 60, titulo_y=None).update_layout(hovermode="closest", showlegend=False)
    fig.update_xaxes(title="MAE (COP/kWh)", gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Real frente a pronóstico")
    cota = st.radio("Mostrar la cota 90 % de", ["Ninguno"] + [m for m in sel if f"cota|{m}" in P],
                    horizontal=True)
    st.plotly_chart(grafico_series(p, sel, 460, None if cota == "Ninguno" else cota), use_container_width=True)

    st.subheader("Error por año")
    anual = p.assign(año=p.semana_objetivo.dt.year)
    fig = go.Figure()
    for m in sel:
        s = anual.groupby("año").apply(lambda g: (g[m] - g.real).abs().mean(), include_groups=False)
        fig.add_scatter(x=s.index, y=s.values, name=m, mode="lines+markers",
                        line=dict(color=COLOR.get(m, INK2), width=2, dash="dash" if m == "Ingenuo" else None),
                        marker=dict(size=8))
    fig.update_traces(hovertemplate="%{y:.1f}")
    st.plotly_chart(estilo(fig, 360, "MAE (COP/kWh)"), use_container_width=True)


def estres():
    st.title("Episodios de estrés")
    st.markdown("Semanas en que el precio se dispara o el sistema está bajo presión hídrica. "
                "Es donde más importa no quedarse corto.")
    ep = st.selectbox("Episodio", EPISODIOS.episodio.tolist())
    fila = EPISODIOS.set_index("episodio").loc[ep]
    p = filtrar(P, fila.inicio, fila.fin)
    if p.empty:
        st.info("Este episodio aún no tiene semanas evaluadas en el backtest.")
        return
    modelos = ["Ingenuo", *PRINCIPALES]
    st.dataframe(metricas(p, modelos), hide_index=True, use_container_width=True, column_config=FORMATO)
    st.plotly_chart(grafico_series(p, modelos, 440, "Ridge 14 (oficial)"), use_container_width=True)
    if ep.startswith("Período de riesgo"):
        st.caption("Desde el 7 de septiembre de 2026 no hay exportaciones a Ecuador y rigen reglas temporales "
                   "(CREG 101 127). Son pocas semanas: no permiten concluir si el modelo sigue funcionando.")


def movimientos():
    st.title("¿Anticipa los movimientos grandes?")
    st.markdown("Cada semana se clasifica según el cambio del precio frente a la semana base: **Baja** (cae más de "
                "20 %), **Estable** o **Sube** (sube 25 % o más). Se compara la clase real con la pronosticada.")
    c1, c2 = st.columns(2)
    m = c1.selectbox("Modelo", [n for n in NOMBRES if n != "Ingenuo"], index=NOMBRES.index("Ridge 14 (oficial)") - 1)
    periodo = c2.selectbox("Periodo", list(PERIODOS), index=0, key="per_mov")
    p = filtrar(P, *PERIODOS[periodo]).dropna(subset=[m])

    def clase(x):
        return pd.cut(np.log(x / p.base), [-np.inf, UMBRAL_BAJA, UMBRAL_SUBE, np.inf], right=False,
                      labels=["Baja", "Estable", "Sube"])

    tabla = pd.crosstab(clase(p.real), clase(p[m])).reindex(index=["Baja", "Estable", "Sube"],
                                                             columns=["Baja", "Estable", "Sube"], fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=tabla.values, x=[f"Pronóstico: {c}" for c in tabla.columns], y=[f"Real: {r}" for r in tabla.index],
        colorscale=[[0, "#f0efec"], [0.15, "#cde2fb"], [1, "#184f95"]], showscale=False,
        text=tabla.values, texttemplate="%{text}", textfont=dict(size=16),
        hovertemplate="%{y} · %{x}: %{z} semanas<extra></extra>", xgap=2, ygap=2))
    fig.update_yaxes(autorange="reversed", title=None, gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(estilo(fig, 340, None).update_layout(hovermode="closest"), use_container_width=True)

    c = st.columns(3)
    for i, k in enumerate(["Sube", "Baja"]):
        reales = tabla.loc[k].sum()
        c[i].metric(f"Anticipa las semanas que {'suben' if k == 'Sube' else 'bajan'}",
                    f"{tabla.loc[k, k] / reales * 100:.0f} %" if reales else "—", f"{tabla.loc[k, k]} de {reales}",
                    delta_color="off")
    falsas = tabla[["Baja", "Sube"]].sum().sum() - tabla.loc["Baja", "Baja"] - tabla.loc["Sube", "Sube"]
    c[2].metric("Falsas alarmas", int(falsas), "movimientos pronosticados que no ocurrieron", delta_color="off")
    st.caption("El error típico de todos los modelos es pronosticar estabilidad cuando el precio sí se mueve.")


def explicacion():
    st.title("Pronóstico de la semana y su explicación")
    ult = REG.iloc[-1]
    c = st.columns(4)
    c[0].metric("Semana objetivo", f"{ult.semana_objetivo:%d/%m/%Y}")
    c[1].metric("Pronóstico (COP/kWh)", f"{ult.pronostico:,.1f}", f"{ult.cambio_pct:+.1f} %", delta_color="off")
    c[2].metric("Cota 90 % (COP/kWh)", f"{ult.cota90:,.1f}")
    c[3].metric("Estado", str(ult.estado).capitalize())
    if ult.estado == "respaldo":
        so = ULTIMO["sin_ofertas"]
        st.warning(f"La emisión del {ult.fecha_emision:%d/%m/%Y} salió en **respaldo**: XM aún no publicaba los precios "
                   f"de oferta de noviembre, así que se registró el ingenuo. Como referencia, el modelo sin las tres "
                   f"variables de oferta pronostica **{so['pronostico']:,.1f} COP/kWh** "
                   f"({(so['pronostico'] / so['precio_base'] - 1) * 100:+.1f} %). Esta variante no está en el registro.")

    ex = ULTIMO["explicacion"]
    st.subheader(f"Qué explica el último pronóstico completo (semana base {pd.Timestamp(ex['semana_base']):%d/%m/%Y})")
    st.markdown(f"Precio base **{ex['precio_base']:,.1f}** → pronóstico **{ex['pronostico']:,.1f} COP/kWh** "
                f"({(ex['pronostico'] / ex['precio_base'] - 1) * 100:+.1f} %). Como el modelo es lineal, el cambio "
                "pronosticado se reparte exactamente entre las variables, frente a una semana promedio.")
    a = pd.DataFrame(ex["aportes"]).assign(pct=lambda x: (np.exp(x.aporte_log) - 1) * 100)
    a = a.reindex(a.pct.abs().sort_values().index)
    fig = go.Figure(go.Bar(
        x=a.pct, y=a.nombre, orientation="h",
        marker=dict(color=np.where(a.pct >= 0, "#e34948", "#2a78d6")),
        hovertemplate="%{y}: %{x:+.1f} %<extra></extra>"))
    fig.update_xaxes(title="Aporte al cambio del precio (%)", gridcolor=GRID, showgrid=True, zeroline=True,
                     zerolinecolor=BASE)
    fig.update_yaxes(title=None, gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(estilo(fig, 470, None).update_layout(hovermode="closest", showlegend=False),
                    use_container_width=True)
    st.caption("Rojo: empuja el precio hacia arriba. Azul: hacia abajo.")

    st.subheader("Registro de pronósticos reales")
    st.markdown("Desde el 5 de noviembre de 2026 cada pronóstico queda congelado antes de conocer el resultado, "
                "con una huella encadenada que impide editarlo después. Es la evidencia independiente del modelo.")
    r = REG[["fecha_emision", "semana_objetivo", "estado", "pronostico", "cota90", "real_provisional"]].copy()
    r["error_provisional"] = r.pronostico - r.real_provisional
    st.dataframe(r, hide_index=True, use_container_width=True, column_config={
        "fecha_emision": st.column_config.DateColumn("Emitido", format="DD/MM/YYYY"),
        "semana_objetivo": st.column_config.DateColumn("Semana objetivo", format="DD/MM/YYYY"),
        "pronostico": st.column_config.NumberColumn("Pronóstico", format="%.1f"),
        "cota90": st.column_config.NumberColumn("Cota 90 %", format="%.1f"),
        "real_provisional": st.column_config.NumberColumn("Real (provisional)", format="%.1f"),
        "error_provisional": st.column_config.NumberColumn("Error (provisional)", format="%+.1f"),
    })
    st.caption("El precio real es provisional hasta la liquidación mensual de XM (versiones TXR/TXF).")


def metodologia():
    st.title("Metodología y supuestos")
    st.markdown("""
**Qué se pronostica.** El precio de bolsa nacional promedio de la semana siguiente (lunes a domingo), ponderado por demanda, y una cota superior que el precio real no debería superar en 9 de cada 10 semanas.

**Datos.** API pública de XM: precio, demanda, aportes, embalse, capacidad, precios de oferta, generación y despacho programado, de 2010 a hoy.

**Modelo oficial.** Regresión Ridge sobre el cambio logarítmico del precio con 14 variables: nivel y dinámica del precio, embalse, aportes, precios de oferta térmicos y no térmicos, y época del año. La cota se calibra con los errores de las últimas 104 semanas (conformal).

**Evaluación.** Walk-forward: cada semana se pronostica solo con datos anteriores, reentrenando cada 4 semanas. Se compararon 67 configuraciones en 14 experimentos; el periodo 2022–2024 se usó para elegir y 2025–2026 como prueba final.
""")
    st.divider()
    st.markdown((RAIZ / "docs" / "SUPUESTOS.md").read_text(encoding="utf-8"))


pg = st.navigation([
    st.Page(resumen, title="Resumen", icon="🏠", default=True),
    st.Page(capacidad, title="Capacidad predictiva", icon="📈", url_path="capacidad"),
    st.Page(estres, title="Episodios de estrés", icon="⚠️", url_path="estres"),
    st.Page(movimientos, title="Movimientos grandes", icon="↕️", url_path="movimientos"),
    st.Page(explicacion, title="Pronóstico actual", icon="🔎", url_path="pronostico"),
    st.Page(metodologia, title="Metodología y supuestos", icon="📄", url_path="metodologia"),
])
pg.run()
