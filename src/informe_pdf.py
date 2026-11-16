"""Informe PDF automático del proyecto, con gráficas según ISA-101.

Uso:
    python src/informe_pdf.py              # informe con los resultados actuales de results/app/

Lo corre `correr_semanal.bat` después de cada emisión. Deja dos copias:
- `informes/informe_TIE_AAAA-MM-DD.pdf`: el archivo histórico de esa corrida.
- `results/app/informe_ultimo.pdf`: el que descarga la app.

Páginas: 1) los tres objetivos, su estado metodológico y el pronóstico vigente, 2) compras TIE en
bolsa (objetivo principal, E26), 3) precio de bolsa (referencia, E16 y E24), 4) precio realizado de
exportación (complementario, E19), 5) registro y explicación del pronóstico, 6) supuestos, límites y
fuentes. Solo lee resultados ya calculados (results/app/ y registro/): no consulta la API ni reentrena.
Los estados de la evidencia y los textos compartidos con la app vienen de `presentacion.py`.
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
import presentacion as pr  # noqa: E402
import xm_client as xm  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "results" / "app"
INFORMES = RAIZ / "informes"
A4 = (8.27, 11.69)
REGLA = "Regla XM (repetir s-1)"
TITULO = "Informe semanal: tres objetivos y sus modelos (garantía TIE)"
PIE = "Proyecto XM–UNAL · tres objetivos reconstruidos con datos públicos · prototipo académico, no oficial de XM"
# Texto escrito en la última generación (lo revisan los tests, sin necesidad de leer el PDF).
TEXTO_GENERADO = []
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
    compra = pd.read_parquet(DATOS / "predicciones_compra.parquet")
    ultimo = json.loads((DATOS / "ultimo_tie.json").read_text(encoding="utf-8"))
    archivo = RAIZ / "registro" / "pronosticos_tie.csv"
    reg = pd.read_csv(archivo, parse_dates=["fecha_emision", "semana_objetivo"]) if archivo.exists() else None
    datos_hasta = {}
    for n, nombre in (("precio", "Precio de bolsa"), ("aportes", "Aportes hídricos"),
                      ("expo_energia", "Exportaciones"), ("tie_compra_energia", "Compras TIE")):
        try:
            datos_hasta[nombre] = xm.ultima_fecha_en_cache(n)
        except Exception:
            datos_hasta[nombre] = None
    return tie, expo, compra, ultimo, reg, datos_hasta


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


def guardar(pdf, fig):
    """Guarda la página y anota su texto en TEXTO_GENERADO."""
    import matplotlib.text as mtext
    TEXTO_GENERADO.extend(a.get_text() for a in fig.findobj(mtext.Text) if a.get_text())
    TEXTO_GENERADO.extend(c.get_text().get_text() for ax in fig.axes for t in ax.tables
                          for c in t.get_celld().values() if c.get_text().get_text())
    pdf.savefig(fig)
    plt.close(fig)


def filtrar(p, ini, fin):
    return p[(p.semana_objetivo >= pd.Timestamp(ini)) & (p.semana_objetivo <= pd.Timestamp(fin))]


# --- Piezas de página ----------------------------------------------------------------------------------

def pagina(pdf, titulo, numero, generado):
    fig = plt.figure(figsize=A4)
    fig.text(0.07, 0.955, titulo, fontsize=15, weight="bold", color=isa.TEXTO)
    fig.add_artist(plt.Line2D([0.07, 0.93], [0.945, 0.945], color=isa.EJE, linewidth=0.8))
    fig.text(0.07, 0.025, PIE, fontsize=7, color=isa.TEXTO_TENUE)
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


def tabla(ax, filas, columnas, anchos=None, alarma=None, tam=8):
    """Tabla gris. `alarma`: {(fila, columna): color} para resaltar solo lo anormal."""
    ax.axis("off")
    t = ax.table(cellText=filas, colLabels=columnas, loc="upper center", cellLoc="center", colWidths=anchos)
    t.auto_set_font_size(False)
    t.set_fontsize(tam)
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
        parrafo(fig, x + 0.27, y + 0.008, pr.legible(" · ".join(motivos)), ancho=60, tam=7.5, color=isa.TEXTO_2,
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
                      f"{m['mejora']:+.0f} %", pr.valor_p(m["p"]),
                      "—" if np.isnan(m["cobertura"]) else f"{m['cobertura']:.0f} %"])
        if m["mejora"] < 0:
            alarma[(i, 4)] = isa.ALARMA_MEDIA  # el modelo erró más que la regla
        if not np.isnan(m["cobertura"]) and m["cobertura"] < 80:
            alarma[(i, 6)] = isa.ALARMA_MEDIA
    return filas, alarma


COLUMNAS_PERIODO = ["Periodo", "Semanas", "Error regla", "Error modelo", "Mejora", "Valor p (DM)", "Bajo el techo"]


# --- Páginas -------------------------------------------------------------------------------------------

def p1_resumen(pdf, ultimo, reg, datos_hasta, generado, medidas_obj):
    fig = pagina(pdf, TITULO, 1, generado)
    y = parrafo(fig, 0.07, 0.915, (
        "Colombia vende electricidad a Ecuador y Ecuador deja un depósito (garantía) antes de cada semana. "
        + pr.REGLA_ATRIBUIDA + " Este proyecto pronostica tres precios públicos reconstruidos relacionados con esa "
        "regla y los compara siempre con ella. " + pr.NO_VALIDADO), ancho=116, tam=8.5, interlinea=0.0155)
    y -= 0.006
    fig.text(0.07, y, "Datos disponibles hasta: " + " · ".join(
        f"{k} {v:%d/%m/%Y}" for k, v in datos_hasta.items() if v is not None), fontsize=8, color=isa.TEXTO_2)

    # Los tres objetivos: cifras del backtest simulado y estado de la evidencia.
    y -= 0.035
    fig.text(0.07, y, "Los tres objetivos (backtest simulado; semanas objetivo de sábado a viernes)", fontsize=11,
             weight="bold")
    filas, estados = [], []
    for clave in pr.ORDEN:
        o, m = pr.OBJETIVO[clave], medidas_obj[clave]
        d = o["decimales"]
        filas.append([f"{clave.capitalize()} ({o['experimento']})", o["unidad"], f"{m['semanas']}",
                      f"{m['desde']:%m/%y}–{m['hasta']:%m/%y}", f"{m['regla']:,.{d}f}", f"{m['modelo']:,.{d}f}",
                      f"{m['mejora']:+.1f} %", pr.valor_p(m["p"])])
        estados.append([f"{clave.capitalize()} ({o['experimento']})", o["estado"]])
    ax = fig.add_axes([0.07, y - 0.1, 0.86, 0.085])
    tabla(ax, filas, ["Objetivo", "Unidad", "Semanas", "Periodo", "Error regla", "Error modelo", "Mejora", "Valor p (DM)"],
          anchos=[0.25, 0.12, 0.08, 0.12, 0.1, 0.11, 0.09, 0.13], tam=7.5)
    y -= 0.105
    ax = fig.add_axes([0.07, y - 0.085, 0.86, 0.075])
    tabla(ax, estados, ["Objetivo", "Estado de la evidencia"], anchos=[0.3, 0.68], tam=7.5)
    y -= 0.095
    y = parrafo(fig, 0.07, y, (
        "«Valor p (DM)»: prueba de Diebold-Mariano frente a la regla. No corrige por haber elegido entre variantes: "
        "E26 se eligió entre 9 y E19 entre unas 30. Errores promedio en la unidad de cada objetivo."), ancho=128,
        tam=7.5, color=isa.TEXTO_2, interlinea=0.0135)

    # Avisos de disponibilidad de datos.
    y -= 0.012
    fig.text(0.07, y, "Disponibilidad de datos", fontsize=11, weight="bold")
    y -= 0.02
    for aviso in pr.AVISOS_DISPONIBILIDAD:
        y = parrafo(fig, 0.085, y, "• " + aviso, ancho=114, tam=8.5, interlinea=0.0155) - 0.003

    # Pronóstico vigente: el último registrado o, si aún no hay, el ejemplo con los datos de hoy.
    y -= 0.015
    if reg is not None and len(reg):
        u = reg.iloc[-1]
        titulo = f"Último pronóstico registrado ({u.fecha_emision:%d/%m/%Y})"
        objetivo, estado = u.semana_objetivo, u.estado
        motivos = [m for m in str(u.motivos).split(" | ") if m and m != "nan"]
        valores = [("Precio de bolsa (COP/kWh)", u.regla_xm, u.pronostico, u.cota90, 0)]
        if pd.notna(u.get("compra_pronostico")):
            valores.insert(0, ("Compras TIE en bolsa (COP/kWh)", u.compra_regla, u.compra_pronostico, u.compra_cota90, 0))
        if pd.notna(u.get("expo_pronostico")):
            valores.append(("Precio realizado de exportación (centUSD/kWh)", u.expo_regla, u.expo_pronostico,
                            u.expo_cota90, 2))
        notas = []
    else:
        titulo = (f"Ejemplo con los datos de hoy (calculado como el viernes "
                  f"{pd.Timestamp(ultimo['fecha_calculo']):%d/%m/%Y}; no registrado)")
        objetivo, estado, motivos = pd.Timestamp(ultimo["semana_objetivo"]), ultimo.get("estado"), ultimo.get("motivos", [])
        valores = [("Precio de bolsa (COP/kWh)", ultimo["regla_xm"], ultimo["pronostico"], ultimo["cota90"], 0)]
        notas = ultimo.get("notas", [])
    fig.text(0.07, y, titulo, fontsize=11, weight="bold")
    y -= 0.02
    fig.text(0.07, y, f"Semana objetivo: {objetivo:%d/%m/%Y} al {objetivo + pd.Timedelta(days=6):%d/%m/%Y} "
                      "(sábado a viernes)", fontsize=9, color=isa.TEXTO_2)
    y -= 0.035
    caja_estado(fig, 0.07, y, estado, motivos)
    ax = fig.add_axes([0.07, y - 0.025 - 0.028 * (len(valores) + 1), 0.86, 0.028 * (len(valores) + 1)])
    tabla(ax, [[n, f"{r:,.{d}f}", f"{m:,.{d}f}", f"{(m / r - 1) * 100:+.1f} %", f"{c:,.{d}f}"] for n, r, m, c, d in valores],
          ["Precio", "Regla de XM", "Modelo", "Diferencia", "Techo (90 %)"], anchos=[0.36, 0.14, 0.14, 0.14, 0.17])
    y -= 0.04 + 0.028 * (len(valores) + 1)
    for nota in notas:
        y = parrafo(fig, 0.07, y, "Nota: " + pr.legible(nota) + ".", ancho=140, tam=7.5, color=isa.TEXTO_2,
                    interlinea=0.0135)
    guardar(pdf, fig)


def p_precio(pdf, p, modelo, titulo, unidad, dec, explicacion, numero, generado, puntos=False, desde=None):
    fig = pagina(pdf, titulo, numero, generado)
    y = parrafo(fig, 0.07, 0.915, explicacion, ancho=104)
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
        f"Errores en {unidad}. «Mejora»: cuánto menos se equivoca el modelo que la regla. «Valor p (DM)»: prueba de "
        "Diebold-Mariano frente a la regla; no corrige por haber elegido entre variantes. «Bajo el techo»: semanas en "
        "que el precio real no superó el techo; la meta es 90 %. Una celda amarilla marca una condición anormal: el "
        "modelo erró más que la regla o el techo cubrió menos de 80 %."), ancho=118, tam=8, color=isa.TEXTO_2)
    guardar(pdf, fig)


def p4_registro(pdf, reg, ultimo, generado):
    fig = pagina(pdf, "Registro de pronósticos y explicación", 5, generado)
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
    guardar(pdf, fig)


def p5_notas(pdf, generado):
    fig = pagina(pdf, "Supuestos, límites, fuentes y cómo leer este informe", 6, generado)
    texto = f"""Supuestos (del proyecto, no confirmados por XM)
• {pr.REGLA_ATRIBUIDA}
• El precio realizado de exportación (lo cobrado en USD entre la energía exportada) es una variable reconstruida. Su equivalencia con el valor aplicado en el cálculo de la garantía es una hipótesis: con el CEE oficial da 22.27 centUSD/kWh, frente a 22.75 en el ejemplo de XM para la semana base del 18 al 24 de enero de 2025.
• El viernes ya están publicados la semana s-1 completa y los días de sábado a martes de la semana s (rezago observado de unos 3 días); la hidrología llega hasta el jueves y el costo marginal programado de cada día se publica la víspera.
• El precio de bolsa se promedia por hora; la máxima transferencia del enlace se supone constante.

Límites conocidos
• {pr.NO_VALIDADO}
• Las cifras de 2018 a 2026 son una simulación usada para elegir los modelos: son optimistas.
• {pr.AVISOS_DISPONIBILIDAD[0]}
• {pr.AVISOS_DISPONIBILIDAD[1]}
• Mientras rija la CREG 101 127 de 2026 (período de riesgo, hasta el 31 de mayo de 2027), el valor que XM aplique en la garantía de exportación puede diferir del precio realizado que se pronostica. Es una pregunta abierta no resuelta con la información pública disponible.
• {pr.NOTA_E22}
• Ningún modelo anticipa los saltos bruscos de precio. El techo es ancho: cuando cubre, queda muy por encima del precio.

Preguntas abiertas no resueltas con la información pública disponible
• La fórmula vigente de la garantía y su relación con el PONE, el precio de bolsa TIE y las compras TIE en bolsa; la composición de ExpoMoneda; el MXT y la conversión del CEE; el mecanismo de exportación desde agosto de 2026.

Cómo leer las gráficas (ISA-101)
• Fondo gris y datos normales en grises: la vista descansa y lo anormal resalta.
• Negro grueso: lo que pasó. Gris discontinuo: la regla de XM. Azul pizarra: el modelo. Gris punteado: el techo.
• Rojo con triángulo: el precio real superó el techo (alarma alta). Amarillo: vigilancia o resultado peor que la regla. Naranja: emisión de respaldo.

Fuentes
• {pr.FUENTES}
• Detalle de métodos y experimentos: docs/EXPERIMENTOS.md, docs/SUPUESTOS.md, docs/VARIABLES_XM.md y las auditorías en docs/."""
    y = 0.915
    for bloque in texto.split("\n"):
        es_titulo = bloque and not bloque.startswith("•")
        y = parrafo(fig, 0.07 if es_titulo else 0.085, y, bloque, ancho=100 if es_titulo else 116,
                    tam=10 if es_titulo else 8.3, peso="bold" if es_titulo else "normal",
                    interlinea=0.0152) - (0.005 if es_titulo else 0.0015)
    guardar(pdf, fig)


def generar(destino=None, generado=None, copiar=True):
    """Genera el informe y devuelve la ruta del PDF. `copiar=False` no actualiza results/app/informe_ultimo.pdf."""
    generado = generado or pd.Timestamp.now()
    TEXTO_GENERADO.clear()
    tie, expo, compra, ultimo, reg, datos_hasta = cargar()
    modelos = {"principal": (compra, _columna(compra, "Modelo compras TIE")),
               "referencia": (tie, _columna(tie, "Modelo registrado")),
               "complementario": (expo, _columna(expo, "Modelo elegido"))}
    medidas_obj = {}
    for clave, (p, col) in modelos.items():
        q = filtrar(p, *PERIODOS[0][1:]).dropna(subset=["real", col, REGLA])
        medidas_obj[clave] = {**medidas(q, col), "desde": q.semana_objetivo.min(), "hasta": q.semana_objetivo.max()}
    INFORMES.mkdir(exist_ok=True)
    destino = Path(destino) if destino else INFORMES / f"informe_TIE_{generado:%Y-%m-%d}.pdf"
    with PdfPages(destino) as pdf:
        p1_resumen(pdf, ultimo, reg, datos_hasta, generado, medidas_obj)
        o = pr.OBJETIVO["principal"]
        p_precio(pdf, compra, modelos["principal"][1], f"Objetivo principal: {o['nombre']} ({o['experimento']})",
                 "COP/kWh", 0, (
                     "Precio de las compras TIE en la bolsa colombiana: suma de CompBolsaTIEMoneda entre suma de "
                     "CompBolsaTIEEner de cada semana TIE (variable reconstruida a partir de series oficiales; "
                     "componente económico de las obligaciones TIE en bolsa). El modelo pronostica el precio de bolsa "
                     "nacional de s+2 y lo ajusta con la diferencia entre las compras TIE y el precio nacional de s-1. "
                     f"Estado de la evidencia: {o['estado'].lower()} (113 semanas; elegido entre 9 variantes). "
                     + pr.AVISOS_DISPONIBILIDAD[0]), 2, generado, puntos=True, desde=pd.Timestamp("2022-01-01"))
        o = pr.OBJETIVO["referencia"]
        p_precio(pdf, tie, modelos["referencia"][1], f"Objetivo de referencia: {o['nombre']} ({o['experimento']})",
                 "COP/kWh", 0, (
                     "El precio general de la energía en Colombia, promedio por hora de la semana TIE (sábado a "
                     "viernes). El modelo usa el precio y la hidrología de la semana s-1, los días de sábado a martes "
                     "de la semana s y el costo marginal programado de miércoles a viernes, con corrección de sesgo. "
                     f"Estado de la evidencia: {o['estado'].lower()}."), 3, generado,
                 desde=tie.semana_objetivo.max() - pd.Timedelta(weeks=104))
        o = pr.OBJETIVO["complementario"]
        p_precio(pdf, expo, modelos["complementario"][1], f"Objetivo complementario: {o['nombre']} ({o['experimento']})",
                 "centUSD/kWh", 2, (
                     "Lo que Ecuador paga por cada kWh que le vende Colombia: ExportMonedaUSD entre ExpoEner (precio "
                     "realizado y reconstruido; no es una cifra oficial de XM). Solo existe en las semanas con "
                     "exportaciones (al menos 1 GWh). El modelo promedia la regla de XM con una regresión robusta "
                     f"(Huber). Estado de la evidencia: {o['estado'].lower()}."), 4, generado, puntos=True,
                 desde=pd.Timestamp("2022-01-01"))
        p4_registro(pdf, reg, ultimo, generado)
        p5_notas(pdf, generado)
        info = pdf.infodict()
        info["Title"] = TITULO
        info["Author"] = "Proyecto XM–UNAL"
    if copiar:
        shutil.copyfile(destino, DATOS / "informe_ultimo.pdf")
    return destino


if __name__ == "__main__":
    print(f"Informe generado: {generar()}")
