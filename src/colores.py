"""Paleta de la app de Streamlit: la configuración visual anterior a ISA-101 (commit 0c14607).

Fondo marfil claro, texto casi negro y un color fijo por papel, el mismo en gráficos, tarjetas y tablas:
- negro: lo que pasó (precio observado), línea continua gruesa;
- gris: la regla de referencia, línea discontinua;
- naranja: el modelo principal o registrado, línea continua;
- verde: el modelo en prueba, línea punteada;
- azul: modelos alternativos y la cota estadística (techo), línea punteada;
- rojo: alerta (el precio real superó la cota) y aportes que suben el precio.

El color no afirma que un modelo esté validado: solo distingue papeles. Nunca es la única pista: cada
serie lleva nombre, trazo y símbolo propios, y las alertas llevan triángulo y texto.

Conserva los nombres de constantes de `isa101.py` (que sigue usando el informe PDF) para que la app
cambie de paleta sin cambiar su lógica.
"""

# Superficies
FONDO = "#fcfcfb"         # fondo de la página y de los gráficos (marfil claro)
FONDO_PANEL = "#f0efec"   # paneles, controles, cabeceras
REJILLA = "#e1e0d9"       # rejilla y separadores
EJE = "#c3c2b7"           # ejes y bordes

# Texto
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
TEXTO_TENUE = "#898781"

# Series
REAL = "#0b0b0b"          # precio observado: negro, continuo y grueso
REGLA = "#898781"         # regla de referencia: gris, discontinuo
MODELO = "#eb6834"        # modelo principal o registrado: naranja, continuo
PRUEBA = "#1baf7a"        # modelo en prueba: verde, punteado
ALTERNATIVO = "#2a78d6"   # modelo alternativo o de referencia: azul
ALTERNATIVOS = ["#2a78d6", "#6250d6", "#184f95", "#0e8a8a"]  # varias alternativas en un mismo gráfico
TECHO = "#2a78d6"         # cota estadística calibrada (techo): azul, punteado fino
SUBE = "#e34948"          # aporte que sube el precio: rojo
BAJA = "#2a78d6"          # aporte que baja el precio: azul

# Alertas, de mayor a menor prioridad
ALARMA_ALTA = "#e34948"   # rojo: el precio real superó la cota
ALARMA_MEDIA = "#eda100"  # ámbar: vigilancia
ALARMA_BAJA = "#f6c76e"   # ámbar claro: emisión de respaldo

TRAZO = {"real": "solid", "regla": "dash", "modelo": "solid", "prueba": "dot", "techo": "dot"}
FUENTE = "system-ui, -apple-system, Segoe UI, sans-serif"

ESTADO_COLOR = {"normal": FONDO_PANEL, "vigilancia": ALARMA_MEDIA, "respaldo": ALARMA_BAJA}
ESTADO_TEXTO = {"normal": "Normal", "vigilancia": "▲ Vigilancia", "respaldo": "◆ Respaldo"}

# Mapas de calor: escala azul legible (más oscuro = más semanas). Se conserva el nombre de isa101.
ESCALA_CALOR = [[0.0, "#f0efec"], [0.15, "#cde2fb"], [1.0, "#184f95"]]
ESCALA_GRISES = ESCALA_CALOR


def color_serie(nombre, regla, modelo, prueba=None):
    """Color y trazo de una serie según su papel: regla, modelo principal, modelo en prueba u alternativa."""
    if nombre == regla:
        return REGLA, TRAZO["regla"]
    if nombre == modelo:
        return MODELO, TRAZO["modelo"]
    if prueba is not None and nombre == prueba:
        return PRUEBA, TRAZO["prueba"]
    return ALTERNATIVO, "dashdot"
