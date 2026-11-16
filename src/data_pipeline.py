"""Construcción de la tabla semanal (lunes a domingo) con las variables de la propuesta.

Copia de `PAE/variables.py` más el diccionario de datos y la auditoría de la
Etapa 1. Cada fila es una semana s, etiquetada con su lunes. Las variables usan
solo información de la semana s o anterior; `precio_sig` es el objetivo P_{s+1}.
"""

from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import xm_client as xm

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
URL_ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
UMBRAL_ENOS = 0.5
TIPOS_TERMICOS = {"TERMICA", "COGENERADOR"}


# Semana de lunes a domingo ("W-SUN"). La tabla TIE usa de sábado a viernes ("W-FRI").
PERIODO_SEMANA = "W-SUN"


def _semana(fechas):
    return fechas.dt.to_period(PERIODO_SEMANA).dt.start_time


# --- Precio y demanda -------------------------------------------------------

def precio_ponderado(precio, demanda, horas=168):
    """P_s = sum(P_h D_h) / sum(D_h); solo semanas con las `horas` completas (168 por defecto)."""
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
    return sem[sem.horas == horas].drop(columns="horas")


def completar_demanda(demanda, generacion, razon_minima=0.8):
    """Estima la demanda de los días que la API publica incompletos.

    Los días más recientes pueden traer las 24 horas con solo una parte de la demanda
    (p. ej. 60 GWh frente a 220 GWh generados), y entonces pesan de menos en el precio
    ponderado. Normalmente demanda / generación está entre 1.00 y 1.05, así que los días
    bajo `razon_minima` se escalan hasta la generación total, conservando el perfil horario.
    Devuelve la demanda corregida y las fechas estimadas.
    """
    total = demanda[xm.HORAS].sum(axis=1)
    gen = demanda.fecha.map(generacion.groupby("fecha").valor.sum())
    incompletos = total < razon_minima * gen
    corregida = demanda.copy()
    if incompletos.any():
        factor = (gen[incompletos] / total[incompletos]).to_numpy()[:, None]
        corregida.loc[incompletos, xm.HORAS] = corregida.loc[incompletos, xm.HORAS].to_numpy() * factor
    return corregida, pd.DatetimeIndex(demanda.loc[incompletos, "fecha"])


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

def oni(archivo=RAW / "oni.txt"):
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


# --- Diccionario de datos y auditoría (Etapa 1) -----------------------------

# Disponibilidad supuesta al emitir el pronóstico el lunes posterior a la semana s.
# "D+1": el dato del día d se publica el día siguiente. Pendiente de confirmar con XM.
DICCIONARIO = pd.DataFrame([
    ("precio", "PrecBolsNaci", "Sistema", "horaria", "COP/kWh", "D+1/D+2 preliminar (TX1, TX2); final mensual (TXR, TXF); ajustes TX3+"),
    ("demanda", "DemaCome", "Sistema", "horaria", "kWh", "D+1"),
    ("aportes", "AporEner", "Sistema", "diaria", "kWh", "D+1"),
    ("aportes_media", "AporEnerMediHist", "Sistema", "diaria", "kWh", "D+1"),
    ("volumen_pct", "PorcVoluUtilDiar", "Sistema", "diaria", "fracción", "D+1"),
    ("volumen_kwh", "VoluUtilDiarEner", "Sistema", "diaria", "kWh", "D+1"),
    ("capacidad", "CapEfecNeta", "Recurso", "diaria", "kW", "D+1"),
    ("oferta", "PrecOferDesp", "Recurso", "horaria→diaria", "COP/kWh", "D+1"),
    ("generacion", "Gene", "Recurso", "horaria→diaria", "kWh", "D+1"),
    ("combustible", "ConsCombustibleMBTU", "Recurso", "horaria→diaria", "MBTU", "D+1"),
    ("costo_marginal", "CostMargDesp", "Sistema", "horaria", "COP/kWh", "antes del día (despacho programado; hora por confirmar)"),
    ("oni", "ONI (NOAA CPC)", "Global", "trimestral móvil", "°C", "día 14 del mes siguiente al cierre de la estación"),
], columns=["serie", "metrica", "entidad", "resolucion", "unidad", "disponibilidad"]).set_index("serie")


def auditar(datos):
    """Cobertura, días faltantes, duplicados y negativos de cada serie descargada."""
    filas = []
    for nombre, df in datos.items():
        valores = df[xm.HORAS] if "Hour01" in df.columns else df[["valor"]]
        dias = pd.date_range(df.fecha.min(), df.fecha.max(), freq="D")
        filas.append({
            "serie": nombre,
            "desde": df.fecha.min().date(), "hasta": df.fecha.max().date(),
            "filas": len(df),
            "dias_faltantes": len(dias.difference(df.fecha.unique())),
            "duplicados": int(df.duplicated(["fecha", "codigo"]).sum()),
            "nulos_%": float(valores.isna().mean().mean() * 100),
            "negativos": int((valores < 0).sum().sum()),
            "recursos": df.codigo.nunique(),
        })
    return pd.DataFrame(filas).set_index("serie")


def tabla_semanal(recalcular=False, corregida=False):
    """Tabla semanal desde la caché local (`data/processed/semanal.parquet`).

    `corregida=True` elimina las filas repetidas (fecha, recurso) de CapEfecNeta que
    la API entrega para algunas térmicas (ene-2010, ene-2011 y días sueltos); en el
    baseline esas filas duplican la capacidad en el FUT y el peso de su oferta.
    """
    archivo = PROCESSED / ("semanal_corregida.parquet" if corregida else "semanal.parquet")
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    datos = {n: xm.descargar(n) for n in xm.SERIES}
    estimados = pd.DatetimeIndex([])
    if corregida:
        datos["capacidad"] = datos["capacidad"].drop_duplicates(["fecha", "codigo"], keep="last")
        datos["demanda"], estimados = completar_demanda(datos["demanda"], datos["generacion"])
    sem, clases = construir(datos, xm.listado_recursos())
    # Días de cada semana con demanda estimada: esas semanas aún no se pueden calificar.
    sem["dias_demanda_estimada"] = pd.Series(1, index=estimados).groupby(estimados.to_period("W-SUN").start_time).sum().reindex(sem.index).fillna(0).astype(int)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    sem.to_parquet(archivo)
    clases.to_csv(PROCESSED / "clasificacion_recursos.csv")
    auditar(datos).to_csv(PROCESSED / "auditoria.csv")
    DICCIONARIO.to_csv(PROCESSED / "diccionario_datos.csv")
    return sem


# --- Tabla alineada con la garantía TIE (E16) -----------------------------

HORIZONTE_TIE = 3  # semana base s-1 → semana objetivo s+2 (CREG 004 de 2003, art. 23)
DIAS_PARCIALES_TIE = 4  # sábado a martes de la semana s: publicados el viernes de cálculo
DIAS_HIDRO_TIE = 6  # sábado a jueves de la semana s: la hidrología se publica con un día de rezago
DIAS_CMG_TIE = 3  # miércoles a viernes de la semana s: costo marginal programado, publicado la víspera


def tabla_tie(recalcular=False):
    """Tabla semanal de sábado a viernes para la garantía TIE, desde la caché local.

    La regla calcula el viernes de la semana s el monto de la semana s+2 con los precios
    horarios de la semana s-1. Cada fila es una semana base s-1 (etiquetada con su sábado):
    - `precio`: promedio horario simple del precio de bolsa. La garantía pondera por la máxima
      transferencia horaria del enlace, que se aproxima como constante.
    - `precio_sig`: el mismo precio en la semana s+2, tres semanas después.
    - `parcial_rel`: log del precio de sábado a martes de la semana s frente a s-1, lo que
      ya está publicado el viernes de cálculo con el rezago observado de unos 3 días.
    Las demás variables son las de siempre, calculadas sobre semanas de sábado a viernes.
    """
    global PERIODO_SEMANA
    archivo = PROCESSED / "semanal_tie.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    datos = {n: xm.leer_cache(n) for n in xm.SERIES}
    datos["capacidad"] = datos["capacidad"].drop_duplicates(["fecha", "codigo"], keep="last")
    # Demanda constante: el precio queda como promedio horario simple.
    uno = datos["demanda"][["fecha", "codigo"]].copy()
    uno[xm.HORAS] = 1.0
    datos_tie = {**datos, "demanda": uno}
    previo, PERIODO_SEMANA = PERIODO_SEMANA, "W-FRI"
    try:
        sem, _ = construir(datos_tie, xm.listado_recursos())
    finally:
        PERIODO_SEMANA = previo

    s = sem.index.to_series()
    consecutiva = (s.shift(-HORIZONTE_TIE) - s) == pd.Timedelta(weeks=HORIZONTE_TIE)
    sem["precio_sig"] = sem.precio.shift(-HORIZONTE_TIE).where(consecutiva)

    h = xm.a_horario(datos["precio"])
    diario = h.groupby(h.index.normalize()).mean()
    inicio_s = sem.index + pd.Timedelta(weeks=1)
    parcial = [diario.reindex(pd.date_range(i, periods=DIAS_PARCIALES_TIE)).mean() for i in inicio_s]
    completos = [diario.reindex(pd.date_range(i, periods=DIAS_PARCIALES_TIE)).notna().all() for i in inicio_s]
    sem["precio_parcial"] = np.where(completos, parcial, np.nan)
    sem["parcial_rel"] = np.log(sem.precio_parcial / sem.precio)
    # Candidato TIE: martes frente a sábado-martes, y la hidrología de sábado a jueves de s
    # (la hidrología se publica con un día de rezago, así que el viernes llega al jueves).
    martes = diario.reindex(inicio_s + pd.Timedelta(days=DIAS_PARCIALES_TIE - 1)).to_numpy()
    sem["parcial_ultimo_rel"] = np.log(martes / sem.precio_parcial)
    a = datos["aportes"].groupby("fecha").valor.sum()
    m = datos["aportes_media"].groupby("fecha").valor.sum()
    v = datos["volumen_pct"].groupby("fecha").valor.mean()
    aportes_s, embalse_s = [], []
    for i in inicio_s:
        dias = pd.date_range(i, periods=DIAS_HIDRO_TIE)
        aa, mm, vv = a.reindex(dias), m.reindex(dias), v.reindex(dias)
        aportes_s.append(aa.sum() / mm.sum() if aa.notna().all() and mm.notna().all() else np.nan)
        embalse_s.append(vv.iloc[-1])
    sem["aportes_s"] = aportes_s
    sem["embalse_s_cambio"] = np.array(embalse_s, dtype=float) - sem.embalse_cierre
    # E24: costo marginal del despacho programado de miércoles a viernes de s. XM lo publica la víspera,
    # así que el viernes de cálculo ya están los tres días. Mide hacia dónde va la semana en curso.
    cm = xm.a_horario(datos["costo_marginal"])
    cm_dia = cm.groupby(cm.index.normalize()).mean()
    cmg = [cm_dia.reindex(pd.date_range(i + pd.Timedelta(days=4), periods=DIAS_CMG_TIE)) for i in inicio_s]
    sem["cmg_s"] = [x.mean() if x.notna().all() else np.nan for x in cmg]
    sem["cmg_s_rel"] = np.log(sem.cmg_s / sem.precio)
    sem.to_parquet(archivo)
    return sem


# --- Precio de exportación TIE (E19) -----------------------------------------

ENERGIA_MINIMA_EXPO_KWH = 1e6  # semanas con menos de 1 GWh exportado no tienen un precio representativo
# Reglas especiales de exportación (Ministerio de Minas y Energía), publicadas antes de aplicarse, así que
# se conocen el viernes de cálculo. En ellas el precio de exportación queda muy por encima del nacional.
REGIMENES_EXPORTACION = [
    ("2023-10-16", "2024-11-15", "Res. MME 40619 y 40718 de 2023, 40115, 40330 y 40410 de 2024: exportar solo con "
                                 "térmicas, por alternativas definidas por circular o suspender; la 40494 de 2024 "
                                 "reactivó con cualquier planta desde el 16-nov-2024"),
    ("2026-07-31", "2027-05-31", "Marco permanente de medidas de 2026 (proyecto MME de junio de 2026: exportar con "
                                 "térmicas) y CREG 101 127 de 2026 en el período de riesgo; fechas por confirmar"),
]
ENERGIA_MINIMA_PARCIAL_KWH = 3e5
# Series de exportación que la emisión debe descargar (precio = USD cobrados / energía exportada).
SERIES_EXPO = ("expo_energia", "expo_usd", "expo_cop")
SERIES_EXPO_TODAS = SERIES_EXPO + ("tie_venta_energia", "tie_venta_cop")


def _semanal_expo(fechas_ini, dias, e, u, c, corte=None):
    """Precio de exportación (centUSD/kWh y COP/kWh) y energía de `dias` días desde cada fecha.

    Un día sin fila antes de `corte` (última fecha publicada) es un día sin exportación y cuenta 0.
    Si el periodo pasa de `corte`, aún no está publicado completo y no tiene precio ni energía:
    así una semana a la que le faltan días no se calcula como si estuviera completa.
    """
    h = pd.DataFrame({"e": e, "u": u, "c": c}).fillna(0.0)
    diario = h.groupby(h.index.normalize()).sum()
    filas = []
    for i in fechas_ini:
        rango = pd.date_range(i, periods=dias)
        if corte is not None and rango[-1] > corte:
            filas.append((np.nan, np.nan, np.nan))
            continue
        x = diario.reindex(rango).fillna(0.0).sum()
        ok = x.e > 0 and x.u > 0 and x.c > 0  # sin liquidación en moneda no hay precio
        filas.append((x.e, x.u / x.e * 100 if ok else np.nan, x.c / x.e if ok else np.nan))
    return pd.DataFrame(filas, index=fechas_ini, columns=["energia", "usd", "cop"])


def tabla_expo(recalcular=False):
    """Tabla TIE (sábado a viernes) con el precio de exportación, desde la caché local.

    Según el ejemplo de XM (Reafirmación 2025, garantías TIE), la garantía de exportación usa el
    "Precio Medio Total − CEE": lo cobrado por exportar en USD entre la energía exportada. Para la
    semana base del 18 al 24 de enero de 2025, ExportMonedaUSD/ExpoEner da 24.32 centUSD/kWh y XM
    proyectó 22.75 tras restar el CEE. El CEE es un valor conocido al calcular, así que se pronostica
    el precio total.

    - `precio_expo`: centUSD/kWh de la semana base s-1 (NaN si se exportó menos de 1 GWh).
    - `precio_expo_sig`: el de la semana s+2; `y_expo` = log(sig/base).
    - `spread`: log del precio de exportación en COP frente al nacional (promedio horario).
    - `precio_expo_parcial`: sábado a martes de la semana s, ya liquidado el viernes.
    """
    archivo = PROCESSED / "semanal_expo.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    t = tabla_tie(recalcular=recalcular)
    h = lambda n: xm.a_horario(xm.leer_cache(n)).fillna(0.0)
    e, u, c = h("expo_energia"), h("expo_usd"), h("expo_cop")
    ve, vc = h("tie_venta_energia"), h("tie_venta_cop")
    # Última fecha publicada en las tres series: lo posterior aún no se conoce.
    corte = min(xm.ultima_fecha_en_cache(n) for n in SERIES_EXPO)
    corte_tie = min(xm.ultima_fecha_en_cache(n) for n in ("tie_venta_energia", "tie_venta_cop"))
    base = _semanal_expo(t.index, 7, e, u, c, corte)
    hay = base.energia >= ENERGIA_MINIMA_EXPO_KWH
    t["energia_expo_gwh"] = base.energia / 1e6
    t["precio_expo"] = base.usd.where(hay)
    t["precio_expo_cop"] = base.cop.where(hay)
    t["trm"] = (t.precio_expo_cop / t.precio_expo * 100)
    tie = _semanal_expo(t.index, 7, ve, vc * 0, vc, corte_tie)
    t["precio_bolsa_tie"] = tie.cop.where(tie.energia >= ENERGIA_MINIMA_EXPO_KWH)
    parcial = _semanal_expo(t.index + pd.Timedelta(weeks=1), DIAS_PARCIALES_TIE, e, u, c, corte)
    t["precio_expo_parcial"] = parcial.usd.where(parcial.energia >= ENERGIA_MINIMA_PARCIAL_KWH).to_numpy()

    s = t.index.to_series()
    consecutiva = (s.shift(-HORIZONTE_TIE) - s) == pd.Timedelta(weeks=HORIZONTE_TIE)
    t["precio_expo_sig"] = t.precio_expo.shift(-HORIZONTE_TIE).where(consecutiva)
    t["y_expo"] = np.log(t.precio_expo_sig / t.precio_expo)
    # Variables propias de la exportación, todas conocidas el viernes de la semana s.
    t["log_precio_expo"] = np.log(t.precio_expo)
    t["spread"] = np.log(t.precio_expo_cop / t.precio)
    t["spread_4s"] = t.spread.rolling(4, min_periods=1).mean()
    t["spread_13s"] = t.spread.rolling(13, min_periods=1).mean()
    t["expo_momentum"] = np.log(t.precio_expo / t.precio_expo.shift(1))
    t["log_energia_expo"] = np.log1p(t.energia_expo_gwh)
    t["trm_cambio"] = np.log(t.trm / t.trm.ffill().shift(4))
    t["expo_parcial_rel"] = np.log(t.precio_expo_parcial / t.precio_expo)
    t["regimen_expo"] = regimen_exportacion(t.index)
    t.to_parquet(archivo)
    return t


def regimen_exportacion(semanas_base):
    """1 si el viernes de cálculo (semana base + 13 días) cae dentro de una regla especial de exportación."""
    calculo = pd.DatetimeIndex(semanas_base) + pd.Timedelta(days=13)
    r = np.zeros(len(calculo))
    for ini, fin, _ in REGIMENES_EXPORTACION:
        r[(calculo >= ini) & (calculo <= fin)] = 1.0
    return r


# --- Datos nuevos (E8) ------------------------------------------------------

def disponibilidad_y_escasez(datos, listado, sem):
    """Variables semanales de disponibilidad del parque y distancia al precio de escasez.

    - margen_reserva: disponibilidad declarada (kWh) sobre demanda comercial − 1.
      La declarada acompaña la oferta del día anterior, así que se conoce al emitir.
    - indisponibilidad: 1 − disponibilidad real / (capacidad efectiva neta · 24 h),
      total y solo térmica. Recoge mantenimientos y salidas forzadas.
    - precio_vs_escasez y oferta_nt_vs_escasez: log del precio de bolsa y de la oferta
      no térmica sobre el precio de escasez vigente al cierre de la semana.
    """
    codigos = set(datos["dispo_declarada"].codigo) | set(datos["dispo_real"].codigo) | set(datos["capacidad"].codigo)
    clases = clasificar_recursos(listado, datos["combustible"], codigos)
    termicos = set(clases.index[clases.termico])
    cap = datos["capacidad"].drop_duplicates(["fecha", "codigo"], keep="last")

    def semanal(df, filtro=None):
        if filtro is not None:
            df = df[df.codigo.isin(filtro)]
        diario = df.groupby("fecha").valor.sum()
        return diario.groupby(_semana(diario.index.to_series())).sum()

    decl = semanal(datos["dispo_declarada"])
    real, real_t = semanal(datos["dispo_real"]), semanal(datos["dispo_real"], termicos)
    cap24, cap24_t = semanal(cap) * 24, semanal(cap, termicos) * 24
    esc = datos["precio_escasez"].groupby("fecha").valor.mean()
    esc = esc.groupby(_semana(esc.index.to_series())).last()

    v = pd.DataFrame(index=sem.index)
    v["margen_reserva"] = decl.reindex(v.index) / (sem.demanda_gwh * 1e6) - 1
    v["margen_cambio"] = v.margen_reserva.diff()
    v["indisponibilidad"] = 1 - real.reindex(v.index) / cap24.reindex(v.index)
    v["indisp_termica"] = 1 - real_t.reindex(v.index) / cap24_t.reindex(v.index)
    v["precio_escasez"] = esc.reindex(v.index)
    v["precio_vs_escasez"] = np.log(sem.precio / v.precio_escasez)
    v["oferta_nt_vs_escasez"] = np.log(sem.oferta_no_termica / v.precio_escasez)
    return v


def tabla_semanal_e8(recalcular=False):
    """Tabla corregida más las variables de disponibilidad y escasez."""
    archivo = PROCESSED / "semanal_e8.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    sem = tabla_semanal(corregida=True)
    datos = {n: xm.descargar(n) for n in ("dispo_declarada", "dispo_real", "precio_escasez", "capacidad", "combustible")}
    sem = sem.join(disponibilidad_y_escasez(datos, xm.listado_recursos(), sem))
    sem.to_parquet(archivo)
    return sem


def tabla_semanal_tx1(recalcular=False):
    """Tabla E8 con las variables de precio de la semana s calculadas con la versión TX1.

    Reproduce lo que se sabe el lunes de emisión: el precio de la semana s y de las
    anteriores en su versión preliminar. El objetivo `precio_sig` se mantiene en la
    versión vigente, que es la que se evalúa. Las semanas sin las 168 horas de TX1
    conservan el precio vigente (se marcan en `precio_es_tx1`).
    """
    archivo = PROCESSED / "semanal_tx1.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    sem = tabla_semanal_e8().copy()
    tx1 = precio_ponderado(xm.descargar("precio_tx1"), xm.descargar("demanda"))
    cols = ["precio", "precio_max_h", "precio_ultimo_dia", "precio_std_diaria"]
    hay = sem.index.isin(tx1.index)
    sem.loc[hay, cols] = tx1.loc[sem.index[hay], cols].to_numpy()
    sem["precio_es_tx1"] = hay
    sem["precio_ant"] = sem.precio.shift(1)
    sem["precio_vs_escasez"] = np.log(sem.precio / sem.precio_escasez)
    sem.to_parquet(archivo)
    return sem


# Columnas de la semana s que dependen de datos con rezago de publicación de unos 3 días
# (precio, demanda, ofertas, generación). Hidrología y ONI se publican a tiempo.
COLUMNAS_CON_REZAGO = ["precio", "precio_max_h", "precio_ultimo_dia", "precio_std_diaria", "demanda_gwh",
                       "oferta_termica", "oferta_no_termica", "fut", "participacion_termica"]


def tabla_semanal_corte(ultimo_dia=4, recalcular=False):
    """Tabla corregida con la semana s cortada en `ultimo_dia` (0 = lunes, 6 = domingo).

    Las columnas con rezago se recalculan solo con los días lunes..ultimo_dia de cada
    semana, que es lo publicado el lunes de emisión. El objetivo `precio_sig`, el precio
    de la semana anterior `precio_ant` y la hidrología siguen con la semana completa.
    """
    archivo = PROCESSED / f"semanal_corte{ultimo_dia}.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    completa = tabla_semanal(corregida=True)
    if ultimo_dia >= 6:
        return completa
    datos = {n: xm.descargar(n) for n in ("precio", "demanda", "oferta", "capacidad", "generacion", "combustible")}
    datos["capacidad"] = datos["capacidad"].drop_duplicates(["fecha", "codigo"], keep="last")
    datos["demanda"], _ = completar_demanda(datos["demanda"], datos["generacion"])
    parcial = {n: df[df.fecha.dt.weekday <= ultimo_dia] for n, df in datos.items()}
    precio = precio_ponderado(parcial["precio"], parcial["demanda"], horas=24 * (ultimo_dia + 1))
    codigos = set(datos["oferta"].codigo) | set(datos["generacion"].codigo) | set(datos["capacidad"].codigo)
    clases = clasificar_recursos(xm.listado_recursos(), datos["combustible"], codigos)
    oferta = oferta_y_utilizacion(parcial["oferta"], parcial["capacidad"], parcial["generacion"], clases)
    nueva = completa.copy()
    for c in COLUMNAS_CON_REZAGO:
        fuente = precio if c in precio.columns else oferta
        nueva[c] = fuente[c].reindex(nueva.index)
    nueva["precio_ant"] = completa.precio.shift(1)
    nueva.to_parquet(archivo)
    return nueva


# --- E9: información diaria ---------------------------------------------------

def rasgos_diarios(precio, demanda, ultimo_dia=6):
    """Dinámica diaria del precio dentro de la semana s, con los días lunes..ultimo_dia.

    - pendiente_diaria: pendiente de log(precio diario) frente al día de la semana.
    - ultimos2_rel: log del promedio de los dos últimos días conocidos sobre el promedio de la semana.
    """
    p, d = xm.a_horario(precio), xm.a_horario(demanda)
    h = pd.DataFrame({"p": p, "d": d}).dropna()
    h = h[h.index.weekday <= ultimo_dia]
    h["pd"] = h.p * h.d
    dia = h.index.normalize()
    diario = (h.groupby(dia).pd.sum() / h.groupby(dia).d.sum()).to_frame("p")
    diario["semana"] = _semana(diario.index.to_series())
    diario["x"] = diario.index.weekday

    def resumen(g):
        if len(g) < 2:
            return pd.Series({"pendiente_diaria": np.nan, "ultimos2_rel": np.nan})
        return pd.Series({"pendiente_diaria": np.polyfit(g.x, np.log(g.p), 1)[0],
                          "ultimos2_rel": np.log(g.p.iloc[-2:].mean() / g.p.mean())})

    return diario.groupby("semana")[["p", "x"]].apply(resumen)


def despacho_programado(datos, clases, ultimo_dia=6):
    """Generación térmica programada para el lunes de la semana s+1 (publicada el domingo)
    frente a la térmica real promedio de los días conocidos de la semana s.

    - termica_prog_rel: log(térmica programada del lunes / térmica real diaria media de s).
    - part_termica_prog: participación térmica en la generación programada del lunes.
    """
    term = set(clases.index[clases.termico])
    gp = datos["gene_programada"]
    prog_t = gp[gp.codigo.isin(term)].groupby("fecha").valor.sum()
    prog_tot = gp.groupby("fecha").valor.sum()
    gen = datos["generacion"]
    gen = gen[gen.fecha.dt.weekday <= ultimo_dia]
    real_t = gen[gen.codigo.isin(term)].groupby("fecha").valor.sum()
    real_sem = real_t.groupby(_semana(real_t.index.to_series())).mean()
    lunes_sig = real_sem.index + pd.Timedelta(days=7)
    v = pd.DataFrame(index=real_sem.index)
    v["termica_prog_rel"] = np.log(prog_t.reindex(lunes_sig).to_numpy() / real_sem.to_numpy())
    v["part_termica_prog"] = (prog_t / prog_tot).reindex(lunes_sig).to_numpy()
    return v


def tabla_e9(ultimo_dia=6, recalcular=False):
    """Tabla con corte de información en `ultimo_dia` más las variables diarias de E9."""
    archivo = PROCESSED / f"semanal_e9_corte{ultimo_dia}.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    sem = tabla_semanal_corte(ultimo_dia).copy()
    datos = {n: xm.descargar(n) for n in ("precio", "demanda", "generacion", "gene_programada",
                                          "oferta", "capacidad", "combustible")}
    codigos = set(datos["gene_programada"].codigo) | set(datos["generacion"].codigo) | set(datos["capacidad"].codigo)
    clases = clasificar_recursos(xm.listado_recursos(), datos["combustible"], codigos)
    sem = sem.join(rasgos_diarios(datos["precio"], datos["demanda"], ultimo_dia))
    sem = sem.join(despacho_programado(datos, clases, ultimo_dia))
    sem.to_parquet(archivo)
    return sem


# --- E12: costo marginal del despacho programado -------------------------------

DIAS_CMG = (1, 2, 3, 4)  # días conocidos de la semana objetivo: lunes, lunes-martes, ...


def costo_marginal(cmg, dias=DIAS_CMG):
    """Costo marginal programado (`CostMargDesp`) de la semana base s y de los primeros
    días de la semana objetivo s+1. XM lo publica el día anterior, así que con la emisión
    del miércoles de s+1 se conocen el lunes, el martes y el miércoles; el jueves depende
    de la hora en que se corra.

    - cmg_brecha: log(costo marginal medio de s / precio de bolsa de s). Se une a la tabla después.
    - cmg_{k}d_rel: log(costo marginal medio de los primeros k días de s+1 / el de s).
    """
    h = xm.a_horario(cmg).dropna()
    dia = h.groupby(h.index.normalize()).agg(["mean", "size"])
    dia = dia[dia["size"] == 24]["mean"]
    semana = _semana(dia.index.to_series())
    g = dia.groupby(semana)
    base = g.mean().where(g.size() == 7)
    v = pd.DataFrame({"cmg_semana": base})
    for k in dias:
        primeros = dia[dia.index.weekday < k]
        gk = primeros.groupby(_semana(primeros.index.to_series()))
        sig = gk.mean().where(gk.size() == k)
        sig.index = sig.index - pd.Timedelta(days=7)  # se asigna a la semana base s
        v[f"cmg_{k}d_rel"] = np.log(sig.reindex(v.index) / v.cmg_semana)
    return v


def tabla_e12(recalcular=False):
    """Tabla con la semana base completa (emisión del miércoles) más el costo marginal programado."""
    archivo = PROCESSED / "semanal_e12.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    sem = tabla_semanal(corregida=True).copy()
    sem = sem.join(costo_marginal(xm.descargar("costo_marginal")))
    sem["cmg_brecha"] = np.log(sem.cmg_semana / sem.precio)
    sem.to_parquet(archivo)
    return sem


# --- E11: tabla diaria para LEAR ----------------------------------------------

def tabla_diaria(recalcular=False):
    """Una fila por día con los insumos de LEAR, sin rezagar todavía.

    Precio y demanda salen de las series horarias (precio del día ponderado por demanda).
    `prog_t` es la generación térmica programada de ese día, que se publica el día anterior.
    """
    archivo = PROCESSED / "diaria.parquet"
    if archivo.exists() and not recalcular:
        return pd.read_parquet(archivo)
    datos = {n: xm.descargar(n) for n in ("precio", "demanda", "aportes", "aportes_media", "volumen_pct", "oferta",
                                          "capacidad", "generacion", "gene_programada", "combustible")}
    demanda, _ = completar_demanda(datos["demanda"], datos["generacion"])
    p, d = xm.a_horario(datos["precio"]), xm.a_horario(demanda)
    h = pd.DataFrame({"p": p, "d": d}).dropna()
    h["pd"] = h.p * h.d
    dia = h.index.normalize()
    g = h.groupby(dia)
    t = pd.DataFrame({"precio": g.pd.sum() / g.d.sum(), "demanda": g.d.sum(), "precio_max": g.p.max(), "precio_std": g.p.std()})
    t = t[g.size() == 24]
    t.index.name = "fecha"

    t["aportes"] = datos["aportes"].groupby("fecha").valor.sum()
    t["aportes_media"] = datos["aportes_media"].groupby("fecha").valor.sum()
    t["embalse"] = datos["volumen_pct"].groupby("fecha").valor.mean()

    cap = datos["capacidad"].drop_duplicates(["fecha", "codigo"], keep="last").rename(columns={"valor": "cap"})
    codigos = set(datos["oferta"].codigo) | set(datos["generacion"].codigo) | set(cap.codigo) | set(datos["gene_programada"].codigo)
    clases = clasificar_recursos(xm.listado_recursos(), datos["combustible"], codigos)
    termicos = set(clases.index[clases.termico])

    of = datos["oferta"].merge(cap, on=["fecha", "codigo"]).dropna(subset=["valor", "cap"])
    of = of[of.cap > 0]
    of["termico"] = of.codigo.isin(termicos)
    of["pc"] = of.valor * of.cap
    o = of.groupby(["fecha", "termico"])
    pond = (o.pc.sum() / o.cap.sum()).unstack()
    t["oferta_t"], t["oferta_nt"] = pond[True], pond[False]

    gen = datos["generacion"]
    t["gen_t"] = gen[gen.codigo.isin(termicos)].groupby("fecha").valor.sum()
    t["gen_total"] = gen.groupby("fecha").valor.sum()
    t["cap_t"] = cap[cap.codigo.isin(termicos)].groupby("fecha").cap.sum()
    gp = datos["gene_programada"]
    t["prog_t"] = gp[gp.codigo.isin(termicos)].groupby("fecha").valor.sum()
    # Huecos puntuales (p. ej. sin ofertas el 2021-02-17): se usa el último valor conocido.
    t = t.ffill()
    t.to_parquet(archivo)
    return t
