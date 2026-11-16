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
# Segundo candidato (E12): Ridge 14 + costo marginal del despacho programado del lunes y el
# martes de la semana objetivo, publicado antes de cada día. Con la emisión del miércoles se
# conocen esos dos días; el del miércoles aún no estaba publicado el martes a las 21:19.
# Solo puede reemplazar al oficial si XM confirma que la garantía se fija con la semana ya iniciada.
VERSION_CANDIDATO_CMG = "ridge14-cmg2d-conformal104-v1"
# Objetivos del proyecto (semana TIE de sábado a viernes; cálculo el viernes de s; objetivo s+2; base s-1):
# - PRINCIPAL: precio de exportación (centUSD/kWh, `ExportMonedaUSD` / `ExpoEner`, variable reconstruida),
#   que según E19 es el que entra en la garantía de exportación (supuesto pendiente de confirmar con XM).
#   Modelo: VERSION_EXPO. Solo existe en semanas con exportación.
# - SECUNDARIO: precio de bolsa nacional promedio horario (COP/kWh): referencia del mercado y pronóstico
#   disponible aunque no haya exportación. Modelo: VERSION_TIE.
# Los dos se registran cada viernes junto a la regla de XM, y los dos pueden poner la emisión en vigilancia.
#
# Precio de bolsa TIE (E16): semana sábado a viernes, base s-1, objetivo s+2. Sin ofertas (no aportan a
# tres semanas y XM puede publicarlas con semanas de atraso) y con los días de sábado a martes de s.
VERSION_TIE = "tie-ridge11-parcial-cmg-duan-conformal104-v1"
# Hasta el 16-nov-2026 (E16): sin el costo marginal. Se conserva para el modelo de exportación y la comparación.
VARIABLES_TIE_SIN_CMG = [v for v in VARIABLES if v not in fe.GRUPOS["ofertas"]] + ["parcial_rel"]
# E24: más el costo marginal programado de miércoles a viernes de s (−4.6 % de error, p = 0.008).
VARIABLES_TIE = VARIABLES_TIE_SIN_CMG + ["cmg_s_rel"]
VARIABLES_TIE_RESPALDO = [v for v in VARIABLES if v not in fe.GRUPOS["ofertas"]]
# Candidato en paralelo desde el 20-nov-2026: más la hidrología de sábado a jueves de s y el precio
# del martes. En el backtest erró 94.2 frente a 98.3 (p = 0.02), pero no ganó en todos los periodos:
# lo decide el registro con la misma regla de 26 semanas que los candidatos anteriores.
VERSION_TIE_CANDIDATO = "tie-ridge11-parcial-cmg-hidro-martes-duan-conformal104-v1"
VARIABLES_TIE_CANDIDATO = VARIABLES_TIE + ["aportes_s", "embalse_s_cambio", "parcial_ultimo_rel"]
# Precio de exportación TIE (E19), el que entra en la garantía: promedio de un Huber sobre el cambio
# del precio de exportación y la regla de XM. Se eligió por el periodo de selección 2022–2024.
VERSION_EXPO = "expo-huber-mitad-regla-conformal104-regimen-v1"
# Cota del precio de exportación calibrada por régimen regulatorio (E20): con regla especial de exportación
# usa los errores de ese régimen si hay al menos este número de semanas calificadas en él.
MINIMO_GRUPO_REGIMEN = 8
# El modelo de exportación no usa el costo marginal: en E24 solo mejoró 1.4 %, sin significancia.
VARIABLES_EXPO = VARIABLES_TIE_SIN_CMG + fe.VARIABLES_EXPO
DIAS_CMG_CANDIDATO = 2
VARIABLES_CANDIDATO_CMG = VARIABLES + [f"cmg_{DIAS_CMG_CANDIDATO}d_rel", "cmg_brecha"]
REVISION_CANDIDATO = 12  # semanas calificadas para una primera lectura
DECISION_CANDIDATO = 26  # semanas calificadas para decidir si reemplaza al oficial

# Umbrales del monitoreo (semanas recientes ya calificadas).
VENTANA_MONITOREO = 26
RAZON_MAE_MAXIMA = 1.0     # MAE modelo / MAE ingenuo por encima de esto: el modelo no aporta
COBERTURA_MINIMA = 0.80    # la cota al 90 % cubriendo menos que esto: subcubre
EMBALSE_BAJO = 0.45        # bajo este nivel la mejora frente al ingenuo es 3.5 %, IC 95 % de −16 % a +21 % (44 semanas)
ATRASO_MAXIMO_DIAS = 14    # semana base más vieja que esto respecto a la emisión: datos atrasados
# Sesgo reciente: vigilancia si |sesgo| supera esta fracción del precio medio y es significativo
# (HAC, p < SESGO_P). Hasta oct-2026: −52.9 COP/kWh en 26 semanas (−7.6 % del precio, p = 0.04).
SESGO_MAXIMO = 0.05
SESGO_P = 0.05
# Series que alimentan las 14 variables: deben llegar al domingo de la semana base.
# Faltar 1 día de ofertas cambia la predicción 0.15 % en promedio (p95 0.44 %); 2 días, 0.30 % (p95 0.88 %).
SERIES_SEMANA_BASE = ["precio", "demanda", "aportes", "aportes_media", "volumen_pct", "capacidad", "oferta"]
DIAS_FALTANTES_AVISO = 2   # desde aquí la falta pide vigilancia; con menos queda como nota

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
    "parcial_rel": "Precio de sábado a martes de la semana en curso",
    "parcial_ultimo_rel": "Precio del martes frente a sábado-martes",
    "aportes_s": "Aportes de sábado a jueves frente a la media",
    "embalse_s_cambio": "Cambio del embalse hasta el jueves",
}
