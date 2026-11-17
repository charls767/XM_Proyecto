"""Textos compartidos por la app y el informe PDF: estado metodológico, nombres legibles y avisos.

Así la app y el PDF muestran el mismo estado de la evidencia. No cambia modelos ni cifras: solo cómo se
presentan. Las cifras se calculan siempre con los resultados de results/app/.
"""
import re

import config

# Orden de presentación de los tres objetivos (ver config.OBJETIVOS).
ORDEN = ("principal", "referencia", "complementario")

OBJETIVO = {
    "principal": {"nombre": "Compras TIE en bolsa", "experimento": "E26", "unidad": "COP/kWh", "decimales": 1,
                  "variable": "CompBolsaTIEMoneda / CompBolsaTIEEner",
                  "funcion": "precio de las compras TIE en bolsa; podría estar relacionado con el componente económico "
                             "de las obligaciones TIE, sin confirmación pública de que sea la variable que usa XM",
                  "estado": "Indicio favorable; evidencia débil"},
    "referencia": {"nombre": "Precio nacional de bolsa", "experimento": "E16 y E24", "unidad": "COP/kWh", "decimales": 1,
                   "variable": "PrecBolsNaci",
                   "funcion": "precio general del mercado eléctrico colombiano; referencia y apoyo analítico. No equivale "
                              "automáticamente al valor usado en la garantía ni al precio de las compras TIE o de "
                              "exportación",
                   "estado": "Evidencia estadística favorable frente a la regla base"},
    "complementario": {"nombre": "Precio realizado de exportación", "experimento": "E19 y E20", "unidad": "centUSD/kWh",
                       "variable": "ExportMonedaUSD / ExpoEner",
                       "decimales": 2,
                       "funcion": "lo cobrado por exportar entre la energía exportada; reconstruido, no es una cifra "
                                  "oficial de XM",
                       "estado": "No concluyente; evidencia débil"},
}

NO_VALIDADO = ("Ningún modelo está validado para fijar garantías. Las cifras salen de un backtest simulado; "
               "el registro de pronósticos empieza con la primera emisión prevista (viernes 20 de noviembre de 2026).")

REGLA_ATRIBUIDA = ("Según el material de formación de XM revisado por el proyecto (Reafirmación 2025, sesión 2), el "
                   "viernes de la semana s se calcula la garantía de la semana s+2 (sábado a viernes) con valores de "
                   "la semana s-1. El proyecto adopta ese calendario como supuesto; su vigencia actual es una pregunta "
                   "abierta no resuelta con la información pública disponible.")

AVISOS_DISPONIBILIDAD = (
    "Compras TIE en bolsa: la API pública de XM no tiene datos desde el 1 de agosto de 2026 (y de febrero a julio de "
    "2026 fueron de 1 GWh o menos al mes). Por eso hoy no se puede emitir el pronóstico de E26; es una falta de datos, "
    "no una falla del modelo.",
    "Exportaciones: desde mediados de septiembre de 2026 son mínimas o intermitentes (0.1 a 1.1 GWh por semana, con "
    "semanas de 5 a 7 GWh en noviembre). Sin exportaciones en la semana base no hay precio realizado que pronosticar.",
)

TITULO_E22 = "Monto monetario aproximado bajo supuestos de transferencia y disponibilidad del MXT"
NOTA_E22 = ("E22 estima un monto monetario aproximado bajo supuestos: máxima transferencia constante de 74.25 GWh "
            "por semana (sin serie pública) y el CEE oficial, que no cambia faltantes ni excesos. No es el monto "
            "oficial de la garantía, ni un cálculo de XM, ni un valor aplicable directamente a un contrato.")

# --- Términos comunes de la app y el PDF (los dos los toman de aquí) ---------------------------------------
ETIQUETA = {"principal": "Objetivo principal", "referencia": "Objetivo de referencia",
            "complementario": "Objetivo complementario"}
EVIDENCIA_DEBIL = "Evidencia débil"
NO_CONCLUYENTE = "Resultado no concluyente"
EMISION = "Emisión ilustrativa"
REGISTRO = "Registro prospectivo"
EJEMPLO = "Ejemplo de emisión simulada"
RETROSPECTIVO = "Cálculo retrospectivo; no pertenece todavía al registro prospectivo"
AVISO_REGISTRO = ("Registro prospectivo aún no consolidado. La primera emisión prospectiva está prevista para el viernes "
                  "20 de noviembre de 2026. Hasta acumular semanas calificadas, los resultados provienen del backtest "
                  "histórico.")

# Series de los gráficos y filas de las tablas.
OBSERVADO = "Valor observado"
REGLA_CORTA = "Regla de referencia"
MODELO = "Modelo registrado"
PRUEBA = "Modelo en prueba"
SUPERA = "Semanas que superaron la cota"

# Cota: nunca "garantía" ni "techo". Nivel nominal, cobertura observada y exceso se muestran por separado.
NIVEL_NOMINAL = 90
COTA = "Cota estadística calibrada"
COTA_DEFINICION = f"Cota estadística conformal con nivel nominal del {NIVEL_NOMINAL} %"
COTA_LEYENDA = f"{COTA} (conformal, nivel nominal {NIVEL_NOMINAL} %)"
COTA_EXPLICACION = (f"{COTA_DEFINICION}: calibrada con los errores de las últimas 104 semanas ya calificadas. "
                    "«Cobertura observada»: porcentaje de semanas en que el valor observado no la superó. «Exceso "
                    "promedio»: cuánto quedó por encima del valor observado, en promedio, en las semanas cubiertas. "
                    "No es una cota oficial de XM.")


def medidas_cota(real, cota):
    """Cobertura observada y exceso promedio (%), con la definición de experimentos.py (exceso_cota_%)."""
    import numpy as np
    import pandas as pd
    d = pd.DataFrame({"real": real, "cota": cota}).dropna()
    if d.empty:
        return np.nan, np.nan
    cubre = d.real <= d.cota
    return cubre.mean() * 100, ((d.cota - d.real) / d.real)[cubre].mean() * 100


# La regla con la que se compara todo: nombre y advertencia (vigencia no confirmada).
REGLA_NOMBRE = "Regla de referencia basada en material público de formación de XM"
NOTA_REGLA = ("La regla se utiliza como referencia de comparación: repite el valor de la semana s-1. Su vigencia exacta "
              "y su relación con la fórmula vigente de la garantía siguen siendo preguntas abiertas.")

# Notas cortas de disponibilidad o advertencia por objetivo (tarjetas del panel).
NOTA_CORTA = {
    "principal": "Sin datos públicos suficientes para una emisión actual: no hay compras TIE publicadas desde el "
                 "1 de agosto de 2026. Es una limitación de datos, no una falla del modelo.",
    "referencia": "No equivale automáticamente al valor usado en la garantía; se usa como referencia y apoyo analítico.",
    "complementario": "Exportaciones mínimas o intermitentes en el periodo reciente; evidencia débil por el tamaño "
                      "de la muestra y los cambios regulatorios.",
}

FUENTES = ("API pública de XM: CompBolsaTIEMoneda y CompBolsaTIEEner (compras TIE en bolsa), PrecBolsNaci (precio "
           "de bolsa nacional), ExportMonedaUSD y ExpoEner (exportaciones), CEE (costo equivalente de energía, "
           "mensual), además de demanda, aportes, embalses, ofertas y costo marginal programado.")

# Nombres legibles de variables técnicas que no están en config.NOMBRES.
NOMBRES_EXTRA = {
    "cmg_s_rel": "Costo marginal programado de miércoles a viernes de la semana en curso",
    "log_precio_expo": "Nivel del precio de exportación",
    "spread": "Diferencia entre el precio de exportación y el nacional",
    "spread_4s": "Diferencia exportación–nacional, promedio de 4 semanas",
    "spread_13s": "Diferencia exportación–nacional, promedio de 13 semanas",
    "expo_momentum": "Cambio del precio de exportación frente a la semana anterior",
    "log_energia_expo": "Energía exportada",
    "trm_cambio": "Cambio de la tasa de cambio implícita",
    "expo_parcial_rel": "Precio de exportación de sábado a martes de la semana en curso",
    "expo_parcial_falta": "Faltan los días recientes de exportación",
    "spread_compra": "Diferencia entre las compras TIE y el precio nacional",
}
NOMBRES = {**config.NOMBRES, **NOMBRES_EXTRA}

# Frases que la app y el PDF no deben mostrar, ni siquiera negadas (tests/test_presentacion.py).
FRASES_PROHIBIDAS = ("precio de la garantía", "precio oficial de la garantía", "el precio que usa xm",
                     "pendiente de confirmar con xm", "cuadra con los 22.75", "sí, es real", "casi seguro",
                     "regla actual de xm", "lo que usa xm actualmente", "precio oficial de xm", "precio de garantía",
                     "techo de garantía", "el modelo predice la garantía", "xm calcula exactamente",
                     "garantía calculada")


# Para mostrar documentos del repositorio (p. ej. docs/SUPUESTOS.md) sin las frases prohibidas, aunque estén negadas.
REEMPLAZOS = {"el precio oficial de la garantía": "una cifra oficial del depósito",
              "el precio de la garantía": "una cifra oficial del depósito",
              "precio oficial de la garantía": "cifra oficial del depósito",
              "precio de la garantía": "cifra oficial del depósito"}


def sin_frases(texto):
    """Reescribe las frases prohibidas de un texto ajeno a la app antes de mostrarlo (sin cambiar su sentido)."""
    for viejo, nuevo in REEMPLAZOS.items():
        texto = re.sub(re.escape(viejo), nuevo, texto, flags=re.IGNORECASE)
    return texto


def legible(texto):
    """Reemplaza nombres técnicos de variables por su nombre legible (p. ej. en los motivos de una emisión)."""
    for clave in sorted(NOMBRES, key=len, reverse=True):
        texto = re.sub(rf"\b{re.escape(clave)}\b", NOMBRES[clave].lower(), texto)
    return texto


def valor_p(p):
    """Valor p de Diebold-Mariano en texto."""
    if p != p:  # NaN
        return "sin dato"
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}" if p < 0.10 else f"p = {p:.2f}"
