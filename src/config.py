"""Configuración del modelo en operación.

Modelo principal: Ridge con 14 variables (E1 sin ENOS ni utilización térmica).
Mismo error que E1 en 2018–2026 (MAE 54.1 frente a 54.3, diferencia no
significativa), coeficientes más estables entre reentrenamientos anuales
(`results/estabilidad_coef_14.csv`) y cada variable con lectura física directa.
"""

import feature_engineering as fe

VARIABLES = [v for v in fe.VARIABLES if v not in fe.GRUPOS["enos"] + fe.GRUPOS["termica"]]
NIVEL_COTA = 0.9
VENTANA_CONFORMAL = 104  # semanas de errores fuera de muestra para el margen
INICIO_BACKTEST = "2014-01-01"
VERSION_MODELO = "ridge14-conformal104-v1"

# Modelo candidato: se emite y califica en paralelo, sin cambiar el pronóstico oficial.
VERSION_CANDIDATO = "ens-ridge14-lear-directo-v1"
REVISION_CANDIDATO = 12  # semanas calificadas para una primera lectura
DECISION_CANDIDATO = 26  # semanas calificadas para decidir si reemplaza al oficial

# Umbrales del monitoreo (semanas recientes ya calificadas).
VENTANA_MONITOREO = 26
RAZON_MAE_MAXIMA = 1.0     # MAE modelo / MAE ingenuo por encima de esto: el modelo no aporta
COBERTURA_MINIMA = 0.80    # la cota al 90 % cubriendo menos que esto: subcubre
ATRASO_MAXIMO_DIAS = 14    # semana base más vieja que esto respecto a la emisión: datos atrasados

# Nombres legibles para explicaciones y tablero.
NOMBRES = {
    "log_precio": "Nivel del precio",
    "momentum": "Cambio frente a la semana anterior",
    "cv_diario": "Variación diaria del precio",
    "ultimo_dia_rel": "Precio del último día frente al promedio semanal",
    "max_h_rel": "Pico horario frente al promedio",
    "embalse_cierre": "Nivel del embalse",
    "embalse_cambio": "Cambio semanal del embalse",
    "aportes_pct_media": "Aportes de la semana frente a la media",
    "aportes_pct_media_4s": "Aportes de 4 semanas frente a la media",
    "log_oferta_termica": "Precio de oferta térmico",
    "log_oferta_no_termica": "Precio de oferta no térmico",
    "brecha_oferta_nt": "Oferta no térmica frente al precio",
    "sen_semana": "Época del año (seno)",
    "cos_semana": "Época del año (coseno)",
}
