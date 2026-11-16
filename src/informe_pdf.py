"""Informe PDF automático del proyecto, con gráficas según ISA-101.

Uso:
    python src/informe_pdf.py              # informe con los resultados actuales de results/app/

Lo corre `correr_semanal.bat` después de cada emisión. Deja dos copias:
- `informes/informe_TIE_AAAA-MM-DD.pdf`: el archivo histórico de esa corrida.
- `results/app/informe_ultimo.pdf`: el que descarga la app.

Páginas: 1) resumen y pronóstico vigente, 2) precio de bolsa, 3) precio de exportación,
4) registro y explicación del pronóstico, 5) supuestos y límites. Solo lee resultados ya
calculados (results/app/ y registro/): no consulta la API ni reentrena.
"""
import json
import shutil
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluation as ev  # noqa: E402
import isa101 as isa  # noqa: E402
import xm_client as xm  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "results" / "app"
INFORMES = RAIZ / "informes"
A4 = (8.27, 11.69)
REGLA = "Regla XM (repetir s-1)"
PERIODOS = [("2018 a 2026", "2018-01-01", "2026-12-31"), ("2025 a 2026 (prueba final)", "2025-01-01", "2026-12-31"),
            ("2022 a 2024 (elección)", "2022-01-01", "2024-12-31")]

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 9,
    "text.color": isa.TEXTO, "axes.labelcolor": isa.TEXTO_2, "axes.edgecolor": isa.EJE,
    "xtick.color": isa.TEXTO_2, "ytick.color": isa.TEXTO_2, "axes.facecolor": isa.FONDO,
    "figure.facecolor": isa.FONDO, "savefig.facecolor": isa.FONDO, "axes.grid": True, "grid.color": isa.REJILLA,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


# --- Datos ---------------------------------------------------------------------------------------------

def _columna(p, prefijo):
    return next(c for c in p.columns if c.startswith(prefijo))


def cargar():
    tie = pd.read_parquet(DATOS / "predicciones_tie.parquet")
    expo = pd.read_parquet(DATOS / "predicciones_expo.parquet")
    ultimo = json.loads((DATOS / "ultimo_tie.json").read_text(encoding="utf-8"))
    archivo = RAIZ / "registro" / "pronosticos_tie.csv"
    reg = pd.read_csv(archivo, parse_dates=["fecha_emision", "semana_objetivo"]) if archivo.exists() else None
    datos_hasta = {}
    for n, nombre in (("precio", "Precio de bolsa"), ("aportes", "Aportes hídricos"),
                      ("expo_energia", "Exportaciones")):
        try:
            datos_hasta[nombre] = xm.ultima_fecha_en_cache(n)
        except Exception:
            datos_hasta[nombre] = None
    return tie, expo, ultimo, reg, datos_hasta


def medidas(p, modelo):
    """Error de la regla y del modelo, mejora, p de Diebold-Mariano y cobertura del techo."""
    p = p.dropna(subset=["real", modelo, REGLA])
    if len(p) < 10:
        return None
    er, em = (p[REGLA] - p.real).abs().mean(), (p[modelo] - p.real).abs().mean()
    techo = f"cota|{modelo}"
    return {"semanas": len(p), "regla": er, "modelo": em, "mejora": (1 - em / er) * 100,
            "p": ev.diebold_mariano(p, modelo, REGLA)[1], "sesgo": (p[modelo] - p.real).mean(),
            "cobertura": (p.real <= p[techo]).mean() * 100 if techo in p else np.nan}


def confiable(p):
    if np.isnan(p):
        return "pocas semanas"
    return "sí (p < 0.05)" if p < 0.05 else f"casi (p = {p:.2f})" if p < 0.10 else f"no (p = {p:.2f})"


def filtrar(p, ini, fin):
    return p[(p.semana_objetivo >= pd.Timestamp(ini)) & (p.semana_objetivo <= pd.Timestamp(fin))]


# --- Piezas de página ----------------------------------------------------------------------------------

def pagina(pdf, titulo, numero, generado):
    fig = plt.figure(figsize=A4)
    fig.text(0.07, 0.955, titulo, fontsize=15, weight="bold", color=isa.TEXTO)
    fig.add_artist(plt.Line2D([0.07, 0.93], [0.945, 0.945], color=isa.EJE, linewidth=0.8))
    fig.text(0.07, 0.025, "Proyecto XM–UNAL · Precio para la garantía TIE · prototipo académico, no oficial de XM",
             fontsize=7, color=isa.TEXTO_TENUE)
    fig.text(0.93, 0.025, f"Generado {generado:%d/%m/%Y %H:%M} · pág. {numero}", fontsize=7,
             color=isa.TEXTO_TENUE, ha="right")
    return fig


def parrafo(fig, x, y, texto, ancho=95, tam=9, color=None, interlinea=0.0165, peso="normal"):
    """Escribe un párrafo con ajuste de línea y devuelve la altura siguiente."""
    for linea in texto.split("\n"):
        partes = textwrap.wrap(linea, ancho) or [""]
        for p in partes:
            fig.text(x, y, p, fontsize=tam, color=color or isa.TEXTO, weight=peso)
            y -= interlinea
    return y


def tabla(ax, filas, columnas, anchos=None, alarma=None):
    """Tabla gris. `alarma`: {(fila, columna): color} para resaltar solo lo anormal."""
    ax.axis("off")
    t = ax.table(cellText=filas, colLabels=columnas, loc="upper center", cellLoc="center", colWidths=anchos)
    t.auto_set_font_size(False)
    t.set_fontsize(8)
    t.scale(1, 1.35)
    for (i, j), c in t.get_celld().items():
        c.set_edgecolor(isa.REJILLA)
        c.set_facecolor(isa.FONDO_PANEL if i == 0 else isa.FONDO)
        c.get_text().set_color(isa.TEXTO)
        if i == 0:
            c.get_text().set_weight("bold")
        if alarma and (i, j) in alarma:
            c.set_facecolor(alarma[(i, j)])
    return t


def caja_estado(fig, x, y, estado, motivos):
    """Indicador de estado ISA-101: gris si es normal; color y símbolo solo si es anormal."""
    estado = str(estado or "normal").lower()
    fig.patches.append(plt.Rectangle((x, y - 0.012), 0.25, 0.035, transform=fig.transFigure,
                                     facecolor=isa.ESTADO_COLOR.get(estado, isa.FONDO_PANEL),
                                     edgecolor=isa.EJE, linewidth=0.8))
    fig.text(x + 0.012, y, f"Estado: {isa.ESTADO_TEXTO.get(estado, estado)}", fontsize=10, weight="bold",
             color=isa.TEXTO)
    if motivos:
        parrafo(fig, x + 0.27, y + 0.008, " · ".join(motivos), ancho=60, tam=7.5, color=isa.TEXTO_2,
                interlinea=0.013)


def grafico_serie(ax, p, modelo, unidad, puntos=False, nombre_modelo="Nuestro modelo"):
    """Real, regla, modelo y techo en grises; las semanas en que el real superó el techo, en rojo."""
    estilo = dict(marker="o", markersize=3, linestyle="none") if puntos else {}
    techo = f"cota|{modelo}"
    if puntos:
        # Semanas sin dato quedan como huecos: la línea no une periodos sin exportación.
        p = p.set_index("semana_objetivo")
        p = p.reindex(pd.date_range(p.index.min(), p.index.max(), freq="7D")).rename_axis("semana_objetivo").reset_index()
    if techo in p:
        ax.plot(p.semana_objetivo, p[techo], color=isa.TECHO, linestyle=":", linewidth=1.0, label="Techo (90 %)")
    ax.plot(p.semana_objetivo, p.real, color=isa.REAL, linewidth=1.8, label="Lo que pasó",
            **({"marker": "o", "markersize": 3} if puntos else {}))
    ax.plot(p.semana_objetivo, p[REGLA], color=isa.REGLA, linewidth=1.2, label="Regla de XM",
            **(estilo if puntos else {"linestyle": "--"}))
    ax.plot(p.semana_objetivo, p[modelo], color=isa.MODELO, linewidth=1.5, label=nombre_modelo,
            **(dict(marker="s", markersize=3, linestyle="none") if puntos else {}))
    if techo in p:
        sobre = p[p.real > p[techo]]
        if len(sobre):
            ax.scatter(sobre.semana_objetivo, sobre.real, marker="^", s=40, color=isa.ALARMA_ALTA, zorder=5,
                       edgecolor=isa.TEXTO, linewidth=0.5, label=f"Superó el techo ({len(sobre)} semanas)")
    ax.set_ylabel(unidad)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(loc="upper left", fontsize=7.5, ncol=3)


def filas_periodos(p, modelo, dec):
    filas, alarma = [], {}
    ultimas = p.dropna(subset=["real"]).tail(52)
    for i, (nombre, ini, fin) in enumerate([*PERIODOS, ("Último año (52 semanas)", None, None)], start=1):
        q = ultimas if ini is None else filtrar(p, ini, fin)
        m = medidas(q, modelo)
        if m is None:
            filas.append([nombre, "—", "—", "—", "—", "—", "—"])
            continue
        filas.append([nombre, f"{m['semanas']}", f"{m['regla']:,.{dec}f}", f"{m['modelo']:,.{dec}f}",
                      f"{m['mejora']:+.0f} %", confiable(m["p"]),
                      "—" if np.isnan(m["cobertura"]) else f"{m['cobertura']:.0f} %"])
        if m["mejora"] < 0:
            alarma[(i, 4)] = isa.ALARMA_MEDIA  # el modelo erró más que la regla
        if not np.isnan(m["cobertura"]) and m["cobertura"] < 80:
            alarma[(i, 6)] = isa.ALARMA_MEDIA
    return filas, alarma


COLUMNAS_PERIODO = ["Periodo", "Semanas", "Error regla", "Error modelo", "Mejora", "¿Es real?", "Bajo el techo"]


# --- Páginas -------------------------------------------------------------------------------------------

def p1_resumen(pdf, tie, expo, ultimo, reg, datos_hasta, generado, m_bolsa, m_expo):
    fig = pagina(pdf, "Precio para la garantía TIE: informe semanal", 1, generado)
    y = parrafo(fig, 0.07, 0.915, (
        "Colombia vende electricidad a Ecuador. Antes de cada semana, Ecuador deposita una garantía que XM calcula "
        "el viernes con el precio de hace tres semanas (Resolución CREG 004 de 2003, art. 23). Este proyecto "
        "pronostica mejor ese precio con la información disponible el viernes. El informe se genera "
        "automáticamente con los resultados de cada corrida."), ancho=100)
    y -= 0.01
    fig.text(0.07, y, "Datos disponibles hasta: " + " · ".join(
        f"{k} {v:%d/%m/%Y}" for k, v in datos_hasta.items() if v is not None), fontsize=8, color=isa.TEXTO_2)

    # Pronóstico vigente: el último registrado o, si aún no hay, el ejemplo con los datos de hoy.
    y -= 0.045
    if reg is not None and len(reg):
        u = reg.iloc[-1]
        titulo = f"Último pronóstico registrado ({u.fecha_emision:%d/%m/%Y})"
        objetivo, estado = u.semana_objetivo, u.estado
        motivos = [m for m in str(u.motivos).split(" | ") if m and m != "nan"]
        valores = [("Precio de bolsa (COP/kWh)", u.regla_xm, u.pronostico, u.cota90, 0)]
        if pd.notna(u.get("expo_pronostico")):
            valores.append(("Precio de exportación (centUSD/kWh)", u.expo_regla, u.expo_pronostico, u.expo_cota90, 2))
    else:
        titulo = f"Ejemplo con los datos de hoy (calculado como el viernes {pd.Timestamp(ultimo['fecha_calculo']):%d/%m/%Y}; no registrado)"
        objetivo, estado, motivos = pd.Timestamp(ultimo["semana_objetivo"]), ultimo.get("estado"), ultimo.get("motivos", [])
        valores = [("Precio de bolsa (COP/kWh)", ultimo["regla_xm"], ultimo["pronostico"], ultimo["cota90"], 0)]
    fig.text(0.07, y, titulo, fontsize=11, weight="bold")
    y -= 0.02
    fig.text(0.07, y, f"Semana objetivo: {objetivo:%d/%m/%Y} al {objetivo + pd.Timedelta(days=6):%d/%m/%Y} "
                      "(sábado a viernes)", fontsize=9, color=isa.TEXTO_2)
    y -= 0.035
    caja_estado(fig, 0.07, y, estado, motivos)
    ax = fig.add_axes([0.07, y - 0.14, 0.86, 0.11])
    tabla(ax, [[n, f"{r:,.{d}f}", f"{m:,.{d}f}", f"{(m / r - 1) * 100:+.1f} %", f"{c:,.{d}f}"] for n, r, m, c, d in valores],
          ["Precio", "Regla de XM", "Nuestro modelo", "Diferencia", "Techo (90 %)"], anchos=[0.34, 0.15, 0.17, 0.15, 0.17])

    # Desempeño en la simulación 2018–2026.
    y -= 0.155
    fig.text(0.07, y, "¿Qué tan bien funciona? Simulación semana a semana, 2018 a 2026", fontsize=11, weight="bold")
    filas = []
    for nombre, m, dec, unidad in (("Precio de bolsa", m_bolsa, 0, "COP/kWh"), ("Precio de exportación", m_expo, 2, "centUSD/kWh")):
        filas.append([f"{nombre} ({unidad})", f"{m['semanas']}", f"{m['regla']:,.{dec}f}", f"{m['modelo']:,.{dec}f}",
                      f"{m['mejora']:+.0f} %", confiable(m["p"])])
    ax = fig.add_axes([0.07, y - 0.12, 0.86, 0.1])
    tabla(ax, filas, ["Precio", "Semanas", "Error regla", "Error modelo", "Mejora", "¿Es real?"],
          anchos=[0.32, 0.1, 0.13, 0.14, 0.11, 0.2])

    y -= 0.145
    ult = medidas(tie.dropna(subset=["real"]).tail(52), _columna(tie, "Modelo registrado"))
    puntos = [
        f"En el precio de bolsa, nuestro modelo se equivoca {m_bolsa['mejora']:.0f} % menos que la regla; la diferencia {'es real' if m_bolsa['p'] < 0.05 else 'no es segura'}.",
        f"En el precio de exportación (el que usa la garantía) la mejora es de {m_expo['mejora']:.0f} % y {confiable(m_expo['p'])}: hay pocas semanas con exportaciones. Es un candidato.",
        f"En el último año, precio de bolsa: {ult['modelo']:,.0f} frente a {ult['regla']:,.0f} COP/kWh; ¿es real?: {confiable(ult['p'])}." if ult else "",
        "Nadie anticipa los saltos bruscos de precio. Los triángulos rojos de las gráficas marcan las semanas en que el precio real superó el techo.",
        "Prueba independiente: el registro de pronósticos congelados, desde el 20 de noviembre de 2026.",
    ]
    fig.text(0.07, y, "Lo más importante", fontsize=11, weight="bold")
    y -= 0.022
    for t in filter(None, puntos):
        y = parrafo(fig, 0.085, y, "• " + t, ancho=98) - 0.004
    pdf.savefig(fig)
    plt.close(fig)


def p_precio(pdf, p, modelo, titulo, unidad, dec, explicacion, numero, generado, puntos=False, desde=None):
    fig = pagina(pdf, titulo, numero, generado)
    y = parrafo(fig, 0.07, 0.915, explicacion, ancho=100)
    q = p if desde is None else p[p.semana_objetivo >= desde]
    ax = fig.add_axes([0.09, y - 0.42, 0.84, 0.39])
    grafico_serie(ax, q, modelo, unidad, puntos=puntos)
    ax.set_title(f"Semanas objetivo desde {q.semana_objetivo.min():%b %Y}", fontsize=9, color=isa.TEXTO_2, loc="left")
    y -= 0.48
    fig.text(0.07, y, "Error promedio por periodo", fontsize=11, weight="bold")
    filas, alarma = filas_periodos(p, modelo, dec)
    ax = fig.add_axes([0.07, y - 0.16, 0.86, 0.14])
    tabla(ax, filas, COLUMNAS_PERIODO, anchos=[0.26, 0.1, 0.12, 0.13, 0.1, 0.17, 0.12], alarma=alarma)
    y -= 0.2
    parrafo(fig, 0.07, y, (
        f"Errores en {unidad}. «Mejora»: cuánto menos se equivoca el modelo que la regla. «¿Es real?»: prueba de "
        "Diebold-Mariano (p < 0.05: la diferencia no es suerte). «Bajo el techo»: semanas en que el precio real no "
        "superó el techo; la meta es 90 %. Una celda amarilla marca una condición anormal: el modelo erró más que la "
        "regla o el techo cubrió menos de 80 %."), ancho=105, tam=8, color=isa.TEXTO_2)
    pdf.savefig(fig)
    plt.close(fig)


def p4_registro(pdf, reg, ultimo, generado):
    fig = pagina(pdf, "Registro de pronósticos y explicación", 4, generado)
    y = parrafo(fig, 0.07, 0.915, (
        "Cada viernes el pronóstico se guarda antes de conocer el resultado, en un registro que no se puede editar: "
        "cada fila lleva una huella SHA-256 encadenada a la anterior. Cuando se publica el precio real, se califica."),
        ancho=100)
    if reg is None or not len(reg):
        y = parrafo(fig, 0.07, y - 0.01, "El registro aún no tiene emisiones. La primera es el viernes 20 de "
                                         "noviembre de 2026, para la semana del 28 de noviembre al 4 de diciembre.",
                    ancho=100, color=isa.TEXTO_2)
    else:
        r = reg.tail(12)
        filas, alarma = [], {}
        for i, (_, f) in enumerate(r.iterrows(), start=1):
            filas.append([f"{f.fecha_emision:%d/%m/%Y}", f"{f.semana_objetivo:%d/%m/%Y}", isa.ESTADO_TEXTO.get(f.estado, f.estado),
                          f"{f.regla_xm:,.0f}", f"{f.pronostico:,.0f}", f"{f.cota90:,.0f}",
                          "—" if pd.isna(f.real) else f"{f.real:,.0f}",
                          "—" if pd.isna(f.error_regla) else f"{f.error_regla:+,.0f}",
                          "—" if pd.isna(f.error) else f"{f.error:+,.0f}"])
            if f.estado in isa.ESTADO_COLOR and f.estado != "normal":
                alarma[(i, 2)] = isa.ESTADO_COLOR[f.estado]
            if pd.notna(f.real) and f.real > f.cota90:
                alarma[(i, 6)] = isa.ALARMA_ALTA
        ax = fig.add_axes([0.07, y - 0.03 - 0.025 * (len(filas) + 1), 0.86, 0.025 * (len(filas) + 1)])
        tabla(ax, filas, ["Emitido", "Semana objetivo", "Estado", "Regla", "Modelo", "Techo", "Real", "Error regla",
                          "Error modelo"])
        y -= 0.06 + 0.025 * (len(filas) + 1)
        cal = reg.dropna(subset=["real"])
        if len(cal):
            y = parrafo(fig, 0.07, y, f"Calificadas: {len(cal)}. Error promedio de la regla {cal.error_regla.abs().mean():,.0f} "
                                      f"y del modelo {cal.error.abs().mean():,.0f} COP/kWh.", ancho=100)
        y -= 0.01

    # Explicación del pronóstico de ejemplo: barras en grises (sube oscuro, baja claro).
    a = pd.DataFrame(ultimo["aportes"]).assign(pct=lambda x: (np.exp(x.aporte_log) - 1) * 100)
    a = a.reindex(a.pct.abs().sort_values().index).tail(12)
    fig.text(0.07, y - 0.01, f"¿Por qué el modelo dice lo que dice? (ejemplo del viernes "
                             f"{pd.Timestamp(ultimo['fecha_calculo']):%d/%m/%Y})", fontsize=11, weight="bold")
    alto = min(0.42, max(0.25, y - 0.12))
    ax = fig.add_axes([0.38, y - 0.04 - alto, 0.55, alto])
    ax.barh(a.nombre, a.pct, color=np.where(a.pct >= 0, isa.SUBE, isa.BAJA), edgecolor=isa.EJE, linewidth=0.5)
    ax.axvline(0, color=isa.EJE, linewidth=0.8)
    ax.set_xlabel("Cuánto empuja el precio frente a una semana normal (%)")
    ax.tick_params(axis="y", labelsize=7.5)
    ax.grid(axis="y", visible=False)
    fig.text(0.07, y - 0.04 - alto - 0.06, "Gris oscuro: empuja hacia arriba. Gris claro: hacia abajo. "
                                           "El color se reserva para alarmas (ISA-101).", fontsize=7.5, color=isa.TEXTO_2)
    pdf.savefig(fig)
    plt.close(fig)


def p5_notas(pdf, generado):
    fig = pagina(pdf, "Supuestos, límites y cómo leer este informe", 5, generado)
    texto = """Supuestos principales
• La garantía de exportación usa el precio de exportación de la semana s-1 (lo cobrado en USD entre la energía exportada) y se calcula el viernes de la semana s para la semana s+2 (sábado a viernes), según el material de formación de XM sobre la CREG 004 de 2003.
• El viernes ya están publicados la semana s-1 completa y los días de sábado a martes de la semana s (rezago de unos 3 días); la hidrología llega hasta el jueves.
• El precio de bolsa se promedia por hora; la máxima transferencia del enlace se supone constante.
• La calificación usa el precio publicado; la regla final usa la segunda liquidación (TX2).

Límites conocidos
• Las cifras de 2018 a 2026 son una simulación usada para diseñar los modelos: son optimistas. La prueba independiente es el registro.
• El precio de exportación tiene pocas semanas con datos y cambia con las reglas del Ministerio de Minas y Energía: su mejora no es segura.
• Mientras rija la CREG 101 127 de 2026 (período de riesgo, hasta el 31 de mayo de 2027), el precio de la garantía de exportación puede no ser el que se pronostica. Pendiente de confirmar con XM.
• Ningún modelo anticipa los saltos bruscos de precio. El techo es ancho: cuando cubre, queda muy por encima del precio.
• El monto de la garantía también depende de la máxima transferencia, el costo equivalente en energía y la tasa de cambio, que no se pronostican.

Cómo leer las gráficas (ISA-101)
• Fondo gris y datos normales en grises: la vista descansa y lo anormal resalta.
• Negro grueso: lo que pasó. Gris discontinuo: la regla de XM. Azul pizarra: nuestro modelo. Gris punteado: el techo.
• Rojo con triángulo: el precio real superó el techo (alarma alta). Amarillo: vigilancia o resultado peor que la regla. Naranja: emisión de respaldo.

Fuentes
• API pública de XM (pydataxm): precio de bolsa, demanda, aportes, embalses, ofertas, exportaciones (ExpoEner, ExportMonedaUSD).
• Detalle de métodos y experimentos: docs/EXPERIMENTOS.md, docs/SUPUESTOS.md y las auditorías en docs/."""
    y = 0.915
    for bloque in texto.split("\n"):
        es_titulo = bloque and not bloque.startswith("•")
        y = parrafo(fig, 0.07 if es_titulo else 0.085, y, bloque, ancho=100 if es_titulo else 98,
                    tam=10.5 if es_titulo else 9, peso="bold" if es_titulo else "normal") - (0.006 if es_titulo else 0.002)
    pdf.savefig(fig)
    plt.close(fig)


def generar(destino=None, generado=None):
    """Genera el informe y devuelve la ruta del PDF histórico."""
    generado = generado or pd.Timestamp.now()
    tie, expo, ultimo, reg, datos_hasta = cargar()
    nuestro_bolsa, nuestro_expo = _columna(tie, "Modelo registrado"), _columna(expo, "Modelo elegido")
    m_bolsa = medidas(filtrar(tie, *PERIODOS[0][1:]), nuestro_bolsa)
    m_expo = medidas(filtrar(expo, *PERIODOS[0][1:]), nuestro_expo)
    INFORMES.mkdir(exist_ok=True)
    destino = Path(destino) if destino else INFORMES / f"informe_TIE_{generado:%Y-%m-%d}.pdf"
    with PdfPages(destino) as pdf:
        p1_resumen(pdf, tie, expo, ultimo, reg, datos_hasta, generado, m_bolsa, m_expo)
        p_precio(pdf, tie, nuestro_bolsa, "Precio de bolsa", "COP/kWh", 0, (
            "El precio general de la energía en Colombia, promedio por hora de la semana TIE (sábado a viernes). "
            "Nuestro modelo usa el precio y la hidrología de la semana s-1, los días de sábado a martes de la semana s "
            "y el costo marginal programado de miércoles a viernes, con corrección de sesgo."), 2, generado,
                 desde=tie.semana_objetivo.max() - pd.Timedelta(weeks=104))
        p_precio(pdf, expo, nuestro_expo, "Precio de exportación", "centUSD/kWh", 2, (
            "Lo que Ecuador paga por cada kWh que le vende Colombia: el precio que usa la garantía. Solo existe en las "
            "semanas con exportaciones (al menos 1 GWh). Nuestro modelo promedia la regla de XM con una regresión "
            "robusta (Huber). Es un candidato: la mejora aún no es segura."), 3, generado, puntos=True,
                 desde=pd.Timestamp("2022-01-01"))
        p4_registro(pdf, reg, ultimo, generado)
        p5_notas(pdf, generado)
        info = pdf.infodict()
        info["Title"] = "Precio para la garantía TIE: informe semanal"
        info["Author"] = "Proyecto XM–UNAL"
    shutil.copyfile(destino, DATOS / "informe_ultimo.pdf")
    return destino


if __name__ == "__main__":
    print(f"Informe generado: {generar()}")
