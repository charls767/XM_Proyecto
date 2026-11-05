"""Descarga de series del MEM desde la API de XM (servapibi.xm.com.co).

Usa la librería oficial `pydataxm` (`ReadDB.request_data`) cuando está instalada y
funciona; requiere Python 3.11, porque en 3.12+ su ruta asíncrona (nest_asyncio +
aiohttp) falla con "Timeout context manager should be used inside a task". Si no
está disponible, hace las mismas peticiones al mismo servicio de forma síncrona.

Cada mes descargado se guarda en `data/raw/xm/` y no se vuelve a pedir, salvo los
meses de las últimas semanas.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import pandas as pd
import requests

URL = "https://servapibi.xm.com.co/{}"
CACHE = Path(__file__).resolve().parents[1] / "data" / "raw" / "xm"
HORAS = [f"Hour{h:02d}" for h in range(1, 25)]

# (métrica, entidad, granularidad) que usa el modelo; ver README.md.
SERIES = {
    "precio": ("PrecBolsNaci", "Sistema", "hourly"),
    "demanda": ("DemaCome", "Sistema", "hourly"),
    "aportes": ("AporEner", "Sistema", "daily"),
    "aportes_media": ("AporEnerMediHist", "Sistema", "daily"),
    "volumen_pct": ("PorcVoluUtilDiar", "Sistema", "daily"),
    "volumen_kwh": ("VoluUtilDiarEner", "Sistema", "daily"),
    "capacidad": ("CapEfecNeta", "Recurso", "daily"),
    "oferta": ("PrecOferDesp", "Recurso", "hourly"),
    "generacion": ("Gene", "Recurso", "hourly"),
    "combustible": ("ConsCombustibleMBTU", "Recurso", "hourly"),
    # Datos nuevos (E8)
    "precio_tx1": ("PrecBolsNaciTX1", "Sistema", "hourly"),
    "dispo_declarada": ("DispoDeclarada", "Recurso", "hourly"),
    "dispo_real": ("DispoReal", "Recurso", "hourly"),
    "precio_escasez": ("PrecEsca", "Sistema", "daily"),
    # E9: despacho programado (publicado el día anterior)
    "gene_programada": ("GeneProgDesp", "Recurso", "hourly"),
}


def _post(base, cuerpo, intentos=4):
    for i in range(intentos):
        try:
            r = requests.post(URL.format(base), json=cuerpo, timeout=180)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


def consultar(metrica, entidad, inicio, fin, base):
    """Una petición (máx. 31 días). Devuelve formato largo por día."""
    cuerpo = {"MetricId": metrica, "Entity": entidad, "StartDate": str(inicio),
              "EndDate": str(fin), "Filter": []}
    items = _post(base, cuerpo).get("Items") or []
    clave = "HourlyEntities" if base == "hourly" else "DailyEntities"
    filas = []
    for item in items:
        for ent in item.get(clave, []):
            if base == "hourly":
                v = ent["Values"]
                fila = {"fecha": item["Date"], "codigo": v.get("code", ent["Id"])}
                fila.update({h: v.get(h) for h in HORAS})
            else:
                fila = {"fecha": item["Date"], "codigo": ent.get("Code", ent["Id"]),
                        "valor": ent.get("Value")}
            filas.append(fila)
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["fecha"] = pd.to_datetime(df["fecha"])
    num = HORAS if base == "hourly" else ["valor"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    return df


_LECTOR = None


def _lector():
    """Instancia única de pydataxm.ReadDB, o False si la librería no está o no funciona."""
    global _LECTOR
    if _LECTOR is None:
        try:
            from pydataxm.pydataxm import ReadDB
            _LECTOR = ReadDB()
        except Exception:
            _LECTOR = False
    return _LECTOR


def usa_pydataxm():
    return bool(_lector())


def consultar_pydataxm(metrica, entidad, inicio, fin, base):
    """Rango completo con pydataxm (que divide en meses y los pide en paralelo),
    normalizado al mismo formato largo que `consultar`."""
    crudo = _lector().request_data(metrica, entidad, pd.Timestamp(inicio).date(), pd.Timestamp(fin).date())
    if crudo is None or crudo.empty:
        return pd.DataFrame()
    df = pd.DataFrame({"fecha": pd.to_datetime(crudo["Date"])})
    if base == "hourly":
        df["codigo"] = crudo["Values_code"] if "Values_code" in crudo else crudo["Id"]
        for h in HORAS:
            df[h] = pd.to_numeric(crudo.get(f"Values_{h}"), errors="coerce")
    else:
        df["codigo"] = crudo["Code"] if "Code" in crudo else crudo["Id"]
        df["valor"] = pd.to_numeric(crudo["Value"], errors="coerce")
    return df.reset_index(drop=True)


def _resumir_recurso(df, nombre):
    """Series horarias por recurso se reducen a valor diario para ahorrar espacio.

    El precio de oferta en el MEM es único por recurso y día, así que el promedio
    de las 24 horas lo recupera; generación y combustible se suman.
    """
    if nombre == "oferta":
        df["valor"] = df[HORAS].mean(axis=1)
    else:
        df["valor"] = df[HORAS].sum(axis=1, min_count=1)
    return df[["fecha", "codigo", "valor"]]


def _archivo(nombre, inicio_mes):
    return CACHE / nombre / f"{inicio_mes:%Y-%m}.parquet"


def _en_cache(nombre, inicio_mes):
    """Un mes cerrado hace más de 7 días ya no cambia; los recientes se vuelven a pedir."""
    fin_mes = inicio_mes + pd.offsets.MonthEnd(0)
    cerrado = fin_mes < pd.Timestamp.today().normalize() - pd.Timedelta(days=7)
    return cerrado and _archivo(nombre, inicio_mes).exists()


def _guardar(nombre, inicio_mes, df):
    _, entidad, base = SERIES[nombre]
    if not df.empty and base == "hourly" and entidad == "Recurso":
        df = _resumir_recurso(df, nombre)
    archivo = _archivo(nombre, inicio_mes)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(archivo, index=False)
    return df


def _mes_directo(nombre, inicio_mes):
    metrica, entidad, base = SERIES[nombre]
    fin_mes = min(inicio_mes + pd.offsets.MonthEnd(0), pd.Timestamp.today().normalize())
    return _guardar(nombre, inicio_mes, consultar(metrica, entidad, inicio_mes.date(), fin_mes.date(), base))


def _faltantes_pydataxm(nombre, faltan):
    """Pide con pydataxm el rango que cubre los meses faltantes y lo reparte por mes."""
    metrica, entidad, base = SERIES[nombre]
    fin = min(faltan[-1] + pd.offsets.MonthEnd(0), pd.Timestamp.today().normalize())
    df = consultar_pydataxm(metrica, entidad, faltan[0], fin, base)
    mes = df.fecha.dt.to_period("M").dt.start_time if not df.empty else pd.Series(dtype="datetime64[ns]")
    return [_guardar(nombre, m, df[mes == m].reset_index(drop=True) if not df.empty else df) for m in faltan]


def descargar(nombre, inicio="2010-01-01", fin=None, hilos=4):
    """Serie completa entre `inicio` y `fin`, con caché mensual."""
    fin = pd.Timestamp(fin or pd.Timestamp.today())
    meses = pd.date_range(pd.Timestamp(inicio).replace(day=1), fin, freq="MS")
    faltan = [m for m in meses if not _en_cache(nombre, m)]
    if faltan and usa_pydataxm():
        try:
            _faltantes_pydataxm(nombre, faltan)
            faltan = []
        except Exception as e:
            print(f"pydataxm falló para {nombre} ({e}); uso la consulta directa", flush=True)
    if faltan:
        with ThreadPoolExecutor(hilos) as ex:
            list(ex.map(lambda m: _mes_directo(nombre, m), faltan))
    partes = [pd.read_parquet(_archivo(nombre, m)) for m in meses]
    df = pd.concat([p for p in partes if not p.empty], ignore_index=True)
    return df[(df.fecha >= pd.Timestamp(inicio)) & (df.fecha <= fin)]


def a_horario(df):
    """Formato ancho (fecha + Hour01..Hour24) a serie horaria indexada por timestamp."""
    largo = df.melt(id_vars=["fecha", "codigo"], value_vars=HORAS, var_name="hora", value_name="valor")
    largo["ts"] = largo["fecha"] + pd.to_timedelta(largo["hora"].str[4:].astype(int) - 1, unit="h")
    return largo.set_index("ts")["valor"].sort_index()


def listado_recursos():
    """Atributos actuales de los recursos (tipo, fuente, despacho)."""
    archivo = CACHE / "listado_recursos.parquet"
    if archivo.exists():
        return pd.read_parquet(archivo)
    hoy = pd.Timestamp.today().date()
    js = _post("lists", {"MetricId": "ListadoRecursos", "Entity": "Sistema",
                         "StartDate": str(hoy), "EndDate": str(hoy), "Filter": []})
    df = pd.json_normalize(js["Items"], "ListEntities", sep="_")
    df.columns = [c.replace("Values_", "") for c in df.columns]
    df = df.drop_duplicates("Code")
    archivo.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(archivo, index=False)
    return df


def descargar_todo(inicio="2010-01-01", fin=None):
    datos = {}
    for nombre in SERIES:
        t = time.time()
        datos[nombre] = descargar(nombre, inicio, fin)
        print(f"{nombre:14s} {len(datos[nombre]):>9,d} filas  {time.time() - t:6.1f} s", flush=True)
    return datos


if __name__ == "__main__":
    descargar_todo()
    listado_recursos()
