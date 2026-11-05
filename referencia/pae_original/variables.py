"""Construcción de la tabla semanal (lunes a domingo) con las variables de la propuesta.

Cada fila es una semana s, etiquetada con su lunes. Las variables usan solo
información de la semana s o anterior; `precio_sig` es el objetivo P_{s+1}.
"""

from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import xm_datos as xm

DATOS = Path(__file__).parent / "datos"
URL_ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
UMBRAL_ENOS = 0.5
TIPOS_TERMICOS = {"TERMICA", "COGENERADOR"}


def _semana(fechas):
    return fechas.dt.to_period("W-SUN").dt.start_time


# --- Precio y demanda -------------------------------------------------------

def precio_ponderado(precio, demanda):
    """P_s = sum(P_h D_h) / sum(D_h); solo semanas con las 168 horas completas."""
    p, d = xm.a_horario(precio), xm.a_horario(demanda)
    h = pd.DataFrame({"p": p, "d": d}).dropna()
    h["pd"] = h.p * h.d
    h["semana"] = _semana(h.index.to_series())
    h["dia"] = h.index.normalize()
    g = h.groupby("semana")
    sem = pd.DataFrame({
        "precio": g.pd.sum() / g.d.sum(),
        "precio_max_h": g.p.max(),
        "demanda_gwh": g.d.sum() / 1e6,
        "horas": g.size(),
    })
    diario = h.groupby("dia").pd.sum() / h.groupby("dia").d.sum()
    diario = diario.to_frame("p").assign(semana=_semana(diario.index.to_series()))
    sem["precio_ultimo_dia"] = diario.groupby("semana").p.last()
    sem["precio_std_diaria"] = diario.groupby("semana").p.std()
    return sem[sem.horas == 168].drop(columns="horas")


# --- Hidrología -------------------------------------------------------------

def hidrologia(aportes, aportes_media, volumen_pct):
    a = aportes.groupby("fecha").valor.sum()
    m = aportes_media.groupby("fecha").valor.sum()
    v = volumen_pct.groupby("fecha").valor.mean()
    d = pd.DataFrame({"aportes": a, "media": m, "vol": v})
    d["semana"] = _semana(d.index.to_series())
    g = d.groupby("semana")
    sem = pd.DataFrame({
        "aportes_gwh": g.aportes.sum() / 1e6,
        "aportes_pct_media": g.aportes.sum() / g.media.sum(),
        "embalse_cierre": g.vol.last(),
        "embalse_prom": g.vol.mean(),
    })
    sem["embalse_cambio"] = sem.embalse_cierre.diff()
    sem["aportes_pct_media_4s"] = (
        sem.aportes_gwh.rolling(4).sum() / (sem.aportes_gwh / sem.aportes_pct_media).rolling(4).sum()
    )
    return sem


# --- Clasificación térmica / no térmica ------------------------------------

def clasificar_recursos(listado, combustible, codigos):
    """Térmico según ListadoRecursos; los recursos que ya no están en el listado
    (p. ej. plantas retiradas) se consideran térmicos si reportan consumo de combustible."""
    tipo = listado.set_index("Code").Type.str.upper()
    con_combustible = set(combustible.loc[combustible.valor > 0, "codigo"])
    filas = []
    for c in sorted(set(codigos)):
        if c in tipo.index:
            filas.append((c, tipo[c] in TIPOS_TERMICOS, "listado"))
        else:
            filas.append((c, c in con_combustible, "combustible"))
    return pd.DataFrame(filas, columns=["codigo", "termico", "fuente"]).set_index("codigo")


def oferta_y_utilizacion(oferta, capacidad, generacion, clases):
    """Precio de oferta ponderado por capacidad efectiva neta y factor de utilización térmica.

    FUT_s = sum(G^T) / sum(C^T * 24 h), con G en kWh/día y C en kW, ambos sobre el
    mismo conjunto de recursos térmicos.
    """
    cap = capacidad.rename(columns={"valor": "cap_kw"})
    of = oferta.merge(cap, on=["fecha", "codigo"], how="left").dropna(subset=["valor", "cap_kw"])
    of = of[of.cap_kw > 0].join(clases.termico, on="codigo")
    of["semana"] = _semana(of.fecha)
    of["pc"] = of.valor * of.cap_kw
    g = of.groupby(["semana", "termico"])
    pond = (g.pc.sum() / g.cap_kw.sum()).unstack()
    sem = pd.DataFrame({"oferta_termica": pond.get(True), "oferta_no_termica": pond.get(False)})

    term = clases.index[clases.termico]
    gen = generacion[generacion.codigo.isin(term)].groupby("fecha").valor.sum()
    cap_t = capacidad[capacidad.codigo.isin(term)].groupby("fecha").valor.sum() * 24
    u = pd.DataFrame({"gen": gen, "cap": cap_t}).dropna()
    u["semana"] = _semana(u.index.to_series())
    gu = u.groupby("semana")
    sem["fut"] = gu.gen.sum() / gu.cap.sum()

    gen_tot = generacion.groupby("fecha").valor.sum()
    sem["participacion_termica"] = (
        gen.groupby(_semana(gen.index.to_series())).sum()
        / gen_tot.groupby(_semana(gen_tot.index.to_series())).sum()
    )
    return sem


# --- ENOS (NOAA ONI) --------------------------------------------------------

def oni(archivo=DATOS / "oni.txt"):
    """ONI con la fecha desde la cual estaba publicado.

    YR es el año del mes central de la estación (DJF 2026 = dic-2025..feb-2026).
    Se asume publicado el día 14 del mes siguiente al último mes de la estación,
    después de la discusión diagnóstica de CPC (segundo jueves del mes).
    """
    if not archivo.exists():
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(requests.get(URL_ONI, timeout=60).text)
    t = pd.read_csv(StringIO(archivo.read_text()), sep=r"\s+")
    estaciones = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
    t["mes_central"] = t.SEAS.map({s: i + 1 for i, s in enumerate(estaciones)})
    central = pd.to_datetime(dict(year=t.YR, month=t.mes_central, day=1))
    t["publicado"] = central + pd.offsets.MonthBegin(2) + pd.Timedelta(days=13)
    return t[["SEAS", "YR", "ANOM", "publicado"]].rename(columns={"ANOM": "oni"})


def enos_semanal(semanas, tabla_oni, rezago_meses=3):
    """Último ONI publicado al cierre de cada semana (domingo) y su valor con rezago."""
    t = tabla_oni.sort_values("publicado")
    cierre = pd.DataFrame({"semana": semanas, "cierre": semanas + pd.Timedelta(days=6, hours=23)})
    r = pd.merge_asof(cierre, t[["publicado", "oni"]], left_on="cierre", right_on="publicado")
    t_rez = t.assign(publicado=t.publicado + pd.DateOffset(months=rezago_meses))
    r["oni_rezago"] = pd.merge_asof(cierre, t_rez[["publicado", "oni"]], left_on="cierre",
                                    right_on="publicado").oni
    r["fase_enos"] = np.select([r.oni >= UMBRAL_ENOS, r.oni <= -UMBRAL_ENOS], [1, -1], 0)
    return r.set_index("semana")[["oni", "oni_rezago", "fase_enos"]]


# --- Tabla final ------------------------------------------------------------

def construir(datos, listado, tabla_oni=None):
    tabla_oni = oni() if tabla_oni is None else tabla_oni
    codigos = set(datos["oferta"].codigo) | set(datos["generacion"].codigo) | set(datos["capacidad"].codigo)
    clases = clasificar_recursos(listado, datos["combustible"], codigos)

    sem = (precio_ponderado(datos["precio"], datos["demanda"])
           .join(hidrologia(datos["aportes"], datos["aportes_media"], datos["volumen_pct"]))
           .join(oferta_y_utilizacion(datos["oferta"], datos["capacidad"], datos["generacion"], clases)))
    sem = sem.join(enos_semanal(sem.index, tabla_oni))

    # Continuidad: P_{s+1} solo si la semana siguiente existe y es consecutiva.
    sig = sem.precio.shift(-1)
    consecutiva = (sem.index.to_series().shift(-1) - sem.index.to_series()) == pd.Timedelta(weeks=1)
    sem["precio_sig"] = sig.where(consecutiva)
    sem["precio_ant"] = sem.precio.shift(1)
    ang = 2 * np.pi * sem.index.isocalendar().week.astype(float) / 52.18
    sem["sen_semana"], sem["cos_semana"] = np.sin(ang), np.cos(ang)
    return sem, clases
