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
    # E13: segundo armónico anual (ciclo de 26 semanas, las dos temporadas de lluvia).
    semana_iso = d.index.isocalendar().week.to_numpy()
    d["sen2_semana"] = np.sin(4 * np.pi * semana_iso / 52.18)
    d["cos2_semana"] = np.cos(4 * np.pi * semana_iso / 52.18)
    return d


def bandas_stft(serie_diaria, semanas, largo=28, prefijo="p"):
    """E13: último cuadro de una STFT causal de una serie diaria.

    Ventana Hann de `largo` días que termina el domingo de cada semana base, así que
    solo usa datos conocidos al emitir. Devuelve la potencia total (log), la fracción
    (log) en la banda lenta (períodos > 10 días, sin la media) y en la banda semanal
    (7 y 3,5 días), y el cambio de la fracción semanal frente a la semana anterior.
    """
    import pandas as pd

    x = serie_diaria.asfreq("D").interpolate(limit=3)
    f = np.fft.rfftfreq(largo, d=1.0)
    ventana = np.hanning(largo)
    lenta = (f > 0) & (f < 1 / 10)
    semanal = np.isin(np.round(f * largo).astype(int), [largo // 7, 2 * largo // 7])
    filas = {}
    for s in semanas:
        fin = s + pd.Timedelta(days=6)
        v = x.loc[fin - pd.Timedelta(days=largo - 1):fin].to_numpy()
        if len(v) < largo or np.isnan(v).any():
            continue
        pw = np.abs(np.fft.rfft((v - v.mean()) * ventana)) ** 2
        total = pw[1:].sum() + 1e-12
        filas[s] = {f"stft_{prefijo}_tot": np.log(total),
                    f"stft_{prefijo}_lenta": np.log(pw[lenta].sum() / total + 1e-6),
                    f"stft_{prefijo}_sem": np.log(pw[semanal].sum() / total + 1e-6)}
    t = pd.DataFrame.from_dict(filas, orient="index").reindex(semanas)
    t[f"stft_{prefijo}_sem_cambio"] = t[f"stft_{prefijo}_sem"].diff()
    return t


def agregar_stft(d, diaria):
    """Añade a la tabla semanal las bandas STFT del precio, los aportes y la demanda diarios."""
    for serie, prefijo in ((diaria.precio, "p"), (diaria.aportes, "a"), (diaria.demanda, "d")):
        d = d.join(bandas_stft(np.log(serie.clip(lower=1)), d.index, prefijo=prefijo))
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

GRUPOS_E13 = {
    "armonico2": ["sen2_semana", "cos2_semana"],
    "stft_precio": ["stft_p_tot", "stft_p_lenta", "stft_p_sem", "stft_p_sem_cambio"],
    "stft_aportes": ["stft_a_tot", "stft_a_lenta"],
    "stft_demanda": ["stft_d_sem", "stft_d_sem_cambio"],
}
