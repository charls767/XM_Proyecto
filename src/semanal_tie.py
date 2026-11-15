"""Emisión semanal del precio para la garantía TIE, con registro inmutable.

Uso:
    python src/semanal_tie.py                          # actualiza datos, emite, registra y califica
    python src/semanal_tie.py --sin-actualizar         # usa la caché local
    python src/semanal_tie.py --fecha 2026-11-13 --seco  # prueba: no registra

Sigue la regla de la Resolución CREG 004 de 2003, art. 23: el viernes de la semana s (sábado a
viernes) se calcula la garantía de la semana s+2 con los precios horarios de la semana s-1.
- Regla XM: repetir el precio promedio horario de s-1.
- Modelo: Ridge con 11 variables de s-1 (sin ofertas) y el precio de sábado a martes de s,
  con corrección de sesgo de Duan y cota conformal del 90 % (E16).
- Respaldo: si faltan los días de s, el mismo Ridge sin ellos; si falta la semana s-1, no se emite.

Cada emisión agrega una fila a `registro/pronosticos_tie.csv` encadenada con SHA-256, y un snapshot
en `registro/snapshots_tie/`. Una semana ya registrada no se reescribe; solo se completan después
las columnas de calificación.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import backtesting as bt
import calibration as cal
import config
import data_pipeline as dp
import feature_engineering as fe
import models
import semanal

RAIZ = Path(__file__).resolve().parents[1]
REGISTRO = RAIZ / "registro"
ARCHIVO = REGISTRO / "pronosticos_tie.csv"
FECHAS = ["fecha_emision", "semana_calculo", "semana_base", "semana_objetivo", "datos_precio_hasta",
          "fecha_calificacion"]
COLUMNAS = ["fecha_emision", "semana_calculo", "semana_base", "semana_objetivo", "version_modelo", "estado",
            "motivos", "datos_precio_hasta", "precio_base", "precio_parcial", "regla_xm", "pronostico",
            "cambio_pct", "cota90", "real", "error", "error_regla", "cubierto", "fecha_calificacion", "huella"]
SELLADAS = ["fecha_emision", "semana_calculo", "semana_base", "semana_objetivo", "version_modelo", "estado",
            "motivos", "precio_base", "precio_parcial", "regla_xm", "pronostico", "cota90"]


def semanas(fecha_emision):
    """Semana de cálculo s (su sábado), semana base s-1 y semana objetivo s+2."""
    f = pd.Timestamp(fecha_emision).normalize()
    s = f - pd.Timedelta(days=(f.dayofweek - 5) % 7)
    return s, s - pd.Timedelta(weeks=1), s + pd.Timedelta(weeks=2)


def _pronosticar(d, base, variables):
    """Ridge con Duan entrenado con las filas cuyo objetivo ya se conoce, y su cota conformal."""
    modelo = models.Duan("tie", variables, models.ridge)
    completas = d.dropna(subset=variables + ["y"])
    entren = completas[completas.index < base - pd.Timedelta(weeks=dp.HORIZONTE_TIE - 1)]
    pred = float(modelo.ajustar_predecir(entren, d.loc[[base]])[0])
    # Errores fuera de muestra con el mismo esquema que E16, para calibrar la cota.
    hist = d.dropna(subset=variables + ["y"])
    r = bt.backtest(hist, [modelo], inicio=config.INICIO_BACKTEST, cada=4, embargo=dp.HORIZONTE_TIE - 1)
    w = bt.ancho(r)
    w = w[w.index < base]
    fila = pd.DataFrame({"real": [np.nan], "tie": [pred]}, index=[base])
    h = pd.concat([w[["real", "tie"]], fila])
    cota = float(cal.conformal(h.real, h.tie, nivel=config.NIVEL_COTA, ventana=config.VENTANA_CONFORMAL,
                               rezago=dp.HORIZONTE_TIE).iloc[-1])
    est = models.ridge().fit(entren[variables], entren.y)
    return pred, cota, est, len(entren)


def emitir(fecha_emision=None, actualizar=True, guardar=True):
    fecha_emision = pd.Timestamp(fecha_emision or pd.Timestamp.today()).normalize()
    if guardar and (malas := verificar_registro()):
        raise RuntimeError(f"El registro TIE fue alterado en las semanas {malas}; revísalo antes de emitir.")
    fechas = semanal.actualizar_datos() if actualizar else semanal.ultimas_fechas()
    d = fe.preparar(dp.tabla_tie(recalcular=True))
    s, base, objetivo = semanas(fecha_emision)
    if base not in d.index or pd.isna(d.at[base, "precio"]):
        raise RuntimeError(f"La semana base {base:%Y-%m-%d} aún no está completa (precio hasta "
                           f"{fechas['precio']:%Y-%m-%d}); no se emite.")

    motivos = []
    variables = config.VARIABLES_TIE
    faltan = [v for v in variables if pd.isna(d.at[base, v])]
    estado = "normal"
    if faltan:
        variables = [v for v in config.VARIABLES_TIE_RESPALDO if pd.notna(d.at[base, v])]
        estado = "respaldo"
        motivos.append(f"Faltan: {', '.join(faltan)}")
    if any(f < base + pd.Timedelta(days=6) for k, f in fechas.items() if k in ("precio", "aportes", "volumen_pct")):
        motivos.append("Series atrasadas: " + ", ".join(f"{k} {f:%Y-%m-%d}" for k, f in fechas.items()))
    pred, cota, est, n = _pronosticar(d, base, variables)
    fila = d.loc[base]
    r = {
        "fecha_emision": fecha_emision, "semana_calculo": s, "semana_base": base, "semana_objetivo": objetivo,
        "version_modelo": config.VERSION_TIE + ("-respaldo" if estado == "respaldo" else ""),
        "estado": estado, "motivos": motivos, "datos_hasta": fechas,
        "precio_base": float(fila.precio), "precio_parcial": float(fila.precio_parcial) if pd.notna(fila.precio_parcial) else None,
        "regla_xm": float(fila.precio), "pronostico": pred, "cambio_pct": (pred / fila.precio - 1) * 100, "cota90": cota,
        "variables": {v: float(fila[v]) for v in variables},
        "modelo": {"variables": variables, "intercepto": float(est[-1].intercept_),
                   "coeficientes": [float(c) for c in est[-1].coef_], "alpha": float(est[-1].alpha_),
                   "n_entrenamiento": n},
    }
    if guardar:
        registrar(r)
        calificar(d)
        if actualizar:
            # El registro a una semana ya no emite, pero sus filas se siguen calificando.
            semanal.calificar(dp.tabla_semanal(recalcular=True, corregida=True))
    return r


def _texto(v):
    return semanal._texto(v)


def huella(fila, anterior=""):
    texto = anterior + "|" + "|".join(_texto(fila.get(c)) for c in SELLADAS)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _leer_registro():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    reg = pd.read_csv(ARCHIVO, parse_dates=FECHAS).reindex(columns=COLUMNAS)
    return reg.astype({c: object for c in ("motivos", "huella", "cubierto")})


def _escribir(reg):
    reg = reg.copy()
    for c in FECHAS:
        reg[c] = pd.to_datetime(reg[c]).dt.strftime("%Y-%m-%d")
    reg[COLUMNAS].to_csv(ARCHIVO, index=False)


def verificar_registro():
    reg, anterior, malas = _leer_registro(), "", []
    for _, fila in reg.iterrows():
        h = huella(fila, anterior)
        if fila.huella != h:
            malas.append(_texto(fila.semana_base))
        anterior = h
    return malas


def registrar(r):
    REGISTRO.mkdir(exist_ok=True)
    reg = _leer_registro()
    if (reg.semana_base == r["semana_base"]).any():
        print(f"La semana base {r['semana_base']:%Y-%m-%d} ya está registrada; no se sobrescribe.")
        return False
    fila = {k: r[k] for k in ("fecha_emision", "semana_calculo", "semana_base", "semana_objetivo",
                              "version_modelo", "estado")}
    fila.update({"motivos": " | ".join(r["motivos"]), "datos_precio_hasta": r["datos_hasta"]["precio"],
                 "precio_base": round(r["precio_base"], 2),
                 "precio_parcial": round(r["precio_parcial"], 2) if r["precio_parcial"] is not None else np.nan,
                 "regla_xm": round(r["regla_xm"], 2), "pronostico": round(r["pronostico"], 2),
                 "cambio_pct": round(r["cambio_pct"], 2), "cota90": round(r["cota90"], 2)})
    anterior = reg.huella.iloc[-1] if len(reg) and pd.notna(reg.huella.iloc[-1]) else ""
    fila["huella"] = huella(fila, anterior)
    _escribir(pd.concat([reg, pd.DataFrame([fila])], ignore_index=True))
    snap = REGISTRO / "snapshots_tie" / f"{r['semana_base']:%Y-%m-%d}.json"
    snap.parent.mkdir(exist_ok=True)
    snap.write_text(json.dumps({**{k: v for k, v in r.items() if k != "datos_hasta"},
                                "datos_hasta": {k: f"{v:%Y-%m-%d}" for k, v in r["datos_hasta"].items()}},
                               ensure_ascii=False, indent=2, default=semanal._json), encoding="utf-8")
    print(f"Registrado TIE: semana objetivo {r['semana_objetivo']:%Y-%m-%d}, pronóstico {r['pronostico']:,.1f} COP/kWh")
    return True


def calificar(d=None):
    """Completa real y errores cuando la semana objetivo ya tiene sus 168 horas publicadas."""
    reg = _leer_registro()
    if reg.empty:
        return reg
    d = d if d is not None else dp.tabla_tie()
    pendientes = reg.real.isna() & reg.semana_objetivo.isin(d.index[d.precio.notna()])
    if pendientes.any():
        real = d.precio.reindex(reg.loc[pendientes, "semana_objetivo"]).to_numpy()
        reg.loc[pendientes, "real"] = np.round(real, 2)
        reg.loc[pendientes, "error"] = np.round(reg.loc[pendientes, "pronostico"] - real, 2)
        reg.loc[pendientes, "error_regla"] = np.round(reg.loc[pendientes, "regla_xm"] - real, 2)
        reg.loc[pendientes, "cubierto"] = real <= reg.loc[pendientes, "cota90"]
        reg.loc[pendientes, "fecha_calificacion"] = pd.Timestamp.today().normalize()
        _escribir(reg)
        print(f"Calificadas {int(pendientes.sum())} emisiones TIE")
    return reg


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--sin-actualizar", action="store_true")
    a.add_argument("--seco", action="store_true", help="no registra ni califica")
    a.add_argument("--fecha", help="fecha de emisión (AAAA-MM-DD); por defecto hoy")
    o = a.parse_args()
    r = emitir(o.fecha, actualizar=not o.sin_actualizar, guardar=not o.seco)
    print(f"Estado: {r['estado']}" + "".join(f"\n  - {m}" for m in r["motivos"]))
    print(f"Semana TIE {r['semana_objetivo']:%Y-%m-%d} a {r['semana_objetivo'] + pd.Timedelta(days=6):%Y-%m-%d}: "
          f"{r['pronostico']:,.1f} COP/kWh ({r['cambio_pct']:+.1f} %), cota 90 % {r['cota90']:,.1f}; "
          f"regla XM {r['regla_xm']:,.1f}")
