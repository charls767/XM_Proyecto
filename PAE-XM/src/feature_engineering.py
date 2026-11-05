"""Variables del modelo a partir de la tabla semanal.

`VARIABLES` y `GRUPOS` son idénticos a `PAE/modelo.py` para poder reproducir el
baseline; las columnas añadidas aquí no entran al modelo salvo que un
experimento las pida.
"""

import numpy as np

GRUPOS = {
    "precio": ["log_precio", "momentum", "cv_diario", "ultimo_dia_rel", "max_h_rel"],
    "hidrologia": ["embalse_cierre", "embalse_cambio", "aportes_pct_media", "aportes_pct_media_4s"],
    "ofertas": ["log_oferta_termica", "log_oferta_no_termica", "brecha_oferta_nt"],
    "termica": ["fut", "participacion_termica"],
    "enos": ["oni", "oni_rezago", "fase_enos"],
    "calendario": ["sen_semana", "cos_semana"],
}
VARIABLES = [v for g in GRUPOS.values() for v in g]


def preparar(sem):
    d = sem.copy()
    d["log_precio"] = np.log(d.precio)
    d["momentum"] = np.log(d.precio / d.precio_ant)
    d["cv_diario"] = d.precio_std_diaria / d.precio
    d["ultimo_dia_rel"] = np.log(d.precio_ultimo_dia / d.precio)
    d["max_h_rel"] = np.log(d.precio_max_h / d.precio)
    d["log_oferta_termica"] = np.log(d.oferta_termica)
    d["log_oferta_no_termica"] = np.log(d.oferta_no_termica)
    d["brecha_oferta_nt"] = np.log(d.oferta_no_termica / d.precio)
    d["y"] = np.log(d.precio_sig / d.precio)

    # Fuera del baseline: referencia estacional y volatilidad conocida al emitir.
    d["precio_hace_51"] = d.precio.shift(51)  # P_{s-51}: misma semana del año anterior a s+1
    d["volatilidad_4s"] = d.momentum.rolling(4).std()

    # Etapa 3: candidatas nuevas, todas conocidas al cierre de la semana s.
    for k in (2, 3):
        d[f"rezago_{k}_rel"] = np.log(d.precio.shift(k) / d.precio)
    for k in (4, 8, 13):
        d[f"tendencia_{k}s"] = np.log(d.precio / d.precio.rolling(k).mean())
    d["volatilidad_13s"] = d.momentum.rolling(13).std()
    d["demanda_crec_anual"] = np.log(d.demanda_gwh / d.demanda_gwh.shift(52))
    d["demanda_cambio"] = np.log(d.demanda_gwh / d.demanda_gwh.shift(1))
    # Anomalía del embalse frente a la misma semana de años anteriores (solo años previos).
    # La semana ISO 53 se compara con la 52; si no, su primera aparición queda sin referencia.
    semana_anio = np.minimum(d.index.isocalendar().week.to_numpy(), 52)
    d["embalse_anomalia"] = d.embalse_cierre - d.groupby(semana_anio).embalse_cierre.transform(
        lambda s: s.shift().expanding().mean())
    d["oni_cambio_3m"] = d.oni - d.oni_rezago
    return d


GRUPOS_NUEVOS = {
    "precio_ext": ["rezago_2_rel", "rezago_3_rel", "tendencia_4s", "tendencia_8s", "tendencia_13s",
                   "volatilidad_4s", "volatilidad_13s"],
    "demanda": ["demanda_crec_anual", "demanda_cambio"],
    "hidro_ext": ["embalse_anomalia"],
    "enos_ext": ["oni_cambio_3m"],
}

GRUPOS_E8 = {
    "disponibilidad": ["margen_reserva", "margen_cambio"],
    "indisponibilidad": ["indisponibilidad", "indisp_termica"],
    "escasez": ["precio_vs_escasez", "oferta_nt_vs_escasez"],
}

GRUPOS_E9 = {
    "diario": ["pendiente_diaria", "ultimos2_rel"],
    "programado": ["termica_prog_rel", "part_termica_prog"],
}
