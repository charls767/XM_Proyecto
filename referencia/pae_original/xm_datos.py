"""Descarga de series del MEM desde la API de XM (servapibi.xm.com.co).

Usa el mismo servicio que pydataxm (`ReadDB.request_data`), pero con peticiones
síncronas: en Python 3.14 la ruta asíncrona de pydataxm (nest_asyncio + aiohttp)
falla con "Timeout context manager should be used inside a task".

Cada mes descargado se guarda en `datos/xm/` y no se vuelve a pedir, salvo el
mes en curso.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import pandas as pd
import requests

URL = "https://servapibi.xm.com.co/{}"
CACHE = Path(__file__).parent / "datos" / "xm"
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


def _mes(nombre, inicio_mes):
    metrica, entidad, base = SERIES[nombre]
    fin_mes = inicio_mes + pd.offsets.MonthEnd(0)
    hoy = pd.Timestamp.today().normalize()
    archivo = CACHE / nombre / f"{inicio_mes:%Y-%m}.parquet"
    mes_cerrado = fin_mes < hoy - pd.Timedelta(days=7)
    if archivo.exists() and mes_cerrado:
        return pd.read_parquet(archivo)
    df = consultar(metrica, entidad, inicio_mes.date(), min(fin_mes, hoy).date(), base)
    if not df.empty and base == "hourly" and entidad == "Recurso":
        df = _resumir_recurso(df, nombre)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(archivo, index=False)
    return df


def descargar(nombre, inicio="2010-01-01", fin=None, hilos=4):
    """Serie completa entre `inicio` y `fin`, mes a mes y con caché."""
    fin = pd.Timestamp(fin or pd.Timestamp.today())
    meses = pd.date_range(pd.Timestamp(inicio).replace(day=1), fin, freq="MS")
    with ThreadPoolExecutor(hilos) as ex:
        partes = list(ex.map(lambda m: _mes(nombre, m), meses))
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
