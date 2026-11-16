"""Monto de la garantía TIE de exportación: reconstrucción del proyecto, no el cálculo oficial de XM.

Según el material de formación de XM (Reafirmación 2025, sesión 2), el monto semanal es
    MSG = Σ_h MXT_h × (PM_{s-1,h} − CEE_{s-1})
con MXT la máxima transferencia horaria del enlace. Para exportación el proyecto supone (E19) que PM
es el precio de exportación (`ExportMonedaUSD` / `ExpoEner`). Clasificación de cada pieza:

- Precio de exportación: variable reconstruida desde series oficiales de XM.
- MXT: SUPUESTO. Se toma constante, 74.25 GWh por semana (unos 442 MW), la energía del ejemplo de
  exportación de XM. No hay serie pública del MXT (pregunta 4 de docs/CONSULTA_CRM_XM.md).
- CEE: SUPUESTO. No hay serie pública. Se resta igual a lo garantizado y a lo liquidado, así que no
  cambia faltantes ni excesos; por defecto vale 0 y el monto queda en términos brutos.
- Tasa de cambio: el monto queda en USD; no se convierte.

Faltante: semanas en que lo liquidado supera lo garantizado (exposición hasta el ajuste 1).
Exceso: lo garantizado de más (recursos inmovilizados unas 2 a 3 semanas).
"""
import numpy as np
import pandas as pd

MXT_KWH_SEMANA = 74.25e6  # supuesto: energía semanal del ejemplo de exportación de XM


def monto_usd(precio_centusd, cee_centusd=0.0, mxt_kwh=MXT_KWH_SEMANA):
    """Monto semanal en USD: MXT (kWh) × (precio − CEE) (centUSD/kWh) / 100."""
    return np.asarray(mxt_kwh, dtype=float) * (np.asarray(precio_centusd, dtype=float) - cee_centusd) / 100


def faltante_exceso(real, garantizado, mxt_kwh=MXT_KWH_SEMANA):
    """Faltante y exceso semanales en USD, para precios en centUSD/kWh."""
    dif = monto_usd(real, mxt_kwh=mxt_kwh) - monto_usd(garantizado, mxt_kwh=mxt_kwh)
    return np.clip(dif, 0, None), np.clip(-dif, 0, None)


def resumen(real, garantias, mxt_kwh=MXT_KWH_SEMANA):
    """Tabla por forma de garantizar: faltante y exceso acumulados (millones de USD), semanas cortas,
    peor faltante semanal (millones de USD) y cobertura."""
    filas = []
    for nombre, g in garantias.items():
        f, e = faltante_exceso(real, g, mxt_kwh)
        filas.append({"garantia": nombre, "faltante_musd": f.sum() / 1e6, "exceso_musd": e.sum() / 1e6,
                      "semanas_cortas": int((f > 0).sum()), "peor_faltante_musd": f.max() / 1e6,
                      "cobertura": float((np.asarray(real) <= np.asarray(g)).mean())})
    return pd.DataFrame(filas).set_index("garantia")
