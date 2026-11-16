"""Paleta y reglas de estilo según ANSI/ISA-101.01 (interfaces humano-máquina de alto desempeño).

Principios que se aplican a las gráficas de la app y del informe PDF:
- Fondo gris neutro y de bajo contraste, no blanco ni negro: la vista descansa y lo anormal resalta.
- Lo normal se dibuja en escala de grises. El color no decora: tiene un significado fijo.
- Los colores saturados se reservan para condiciones anormales, con prioridad:
  rojo (alta: el precio real superó el techo), amarillo (media: vigilancia), naranja (respaldo).
- Un solo acento sobrio (azul pizarra) para destacar el dato principal: nuestro modelo.
- La identidad nunca depende solo del color: también cambian el trazo (continuo, discontinuo,
  punteado) y el grosor, y las alarmas llevan símbolo y texto.
- Sin 3D, sin degradados, sin sombras; rejilla tenue; texto gris oscuro.
"""

# Superficies
FONDO = "#E0E0E0"         # fondo de la página y del gráfico
FONDO_PANEL = "#D3D3D3"   # paneles, controles, cabeceras de tabla
REJILLA = "#C6C6C6"       # rejilla y separadores
EJE = "#9A9A9A"           # ejes y marcas

# Texto
TEXTO = "#1F1F1F"
TEXTO_2 = "#4A4A4A"
TEXTO_TENUE = "#707070"

# Datos en condición normal
REAL = "#1F1F1F"          # lo que pasó: negro, trazo grueso
REGLA = "#7A7A7A"         # la referencia: gris medio, discontinuo
MODELO = "#2F4F6F"        # el dato principal: azul pizarra sobrio
PRUEBA = "#5C5C5C"        # alternativas: gris oscuro, punteado
TECHO = "#A8A8A8"         # techo (cota): gris claro, punteado fino
SUBE = "#4A4A4A"          # barras que empujan hacia arriba
BAJA = "#A0A0A0"          # barras que empujan hacia abajo

# Condiciones anormales (alarmas), de mayor a menor prioridad
ALARMA_ALTA = "#D40000"   # rojo: el precio real superó el techo
ALARMA_MEDIA = "#F2C200"  # amarillo: estado de vigilancia
ALARMA_BAJA = "#E87722"   # naranja: estado de respaldo

TRAZO = {"real": "solid", "regla": "dash", "modelo": "solid", "prueba": "dot", "techo": "dot"}
FUENTE = "Arial, Helvetica, sans-serif"

ESTADO_COLOR = {"normal": FONDO_PANEL, "vigilancia": ALARMA_MEDIA, "respaldo": ALARMA_BAJA}
ESTADO_TEXTO = {"normal": "Normal", "vigilancia": "▲ Vigilancia", "respaldo": "◆ Respaldo"}

# Escala de grises para mapas de calor (más oscuro = más semanas)
ESCALA_GRISES = [[0.0, "#E8E8E8"], [1.0, "#3A3A3A"]]


def color_serie(nombre, regla, modelo):
    """Color y trazo de una serie según su papel: regla, nuestro modelo u otra alternativa."""
    if nombre == regla:
        return REGLA, TRAZO["regla"]
    if nombre == modelo:
        return MODELO, TRAZO["modelo"]
    return PRUEBA, TRAZO["prueba"]
