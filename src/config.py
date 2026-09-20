"""Rutas, constantes y reglas de dominio del proyecto."""
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[1]
CRUDO = RAIZ / "Data tesis"   # entrega con historico 2024-2026
PROC = RAIZ / "data" / "processed"
REPORTES = RAIZ / "reports"

for _d in (PROC, REPORTES, REPORTES / "figuras"):
    _d.mkdir(parents=True, exist_ok=True)

# --- Dominio -----------------------------------------------------------------
# P18: la bodega central tiene un unico codigo.
CENTRAL = {"PK"}

# Bodegas internas de Telefonica que NO son distribuidores. Sin este filtro el
# 99,7% del volumen que entra a PK viene de produccion y contamina el target.
BODEGAS_INTERNAS = re.compile(r"BODEGA|PRODUCCI|SCRAP|MATERIA PRIMA", re.I)

# El RUC ecuatoriano tiene 10-13 digitos. En Locations.xlsx la columna
# "Distribuidor para Cupo" trae el RUC para bodegas de distribuidor y un
# centinela de texto (OTRAS, TIENDAS PROPIAS, B2B...) para el resto.
RE_RUC = re.compile(r"^\d{10,13}$")

# Tokens de nulo que llegan como texto desde los sistemas de origen.
NULOS = {"?", "NULL", "", "nan", "None", "-"}

# Segmentacion de producto. El capstone separa 19 SKU de SIM y 250 de equipos;
# son negocios distintos (USD 0,45 vs USD 325 por unidad).
RE_SIM = re.compile(r"\b(SIM|ESIM|USIM|SIMCARD)\b", re.I)

# Campanas comerciales (respuesta P11): Dia de la Madre = 2do domingo de mayo,
# Navidad = 24 de diciembre. Ventana de campana = 30 dias previos.
CAMPANIAS = {
    "madre_2024": ("2024-04-12", "2024-05-12"),
    "navidad_2024": ("2024-11-24", "2024-12-24"),
    "madre_2025": ("2025-04-11", "2025-05-11"),
    "navidad_2025": ("2025-11-24", "2025-12-24"),
    "madre_2026": ("2026-04-10", "2026-05-10"),
    "navidad_2026": ("2026-11-24", "2026-12-24"),
}

# Regla de negocio para el target de envejecimiento (definida con el cliente):
# una unidad que lleva UMBRAL_DIAS o mas en la bodega del distribuidor sin
# venderse se considera devolucion esperada.
UMBRAL_DIAS = 60

# Inicio de la ventana con datos completos. El reporte de ventas de 2024 solo
# cubre cinco meses (marzo, abril, agosto, septiembre y diciembre); en los
# demas las unidades no quedan marcadas como vendidas y la regla de
# envejecimiento las contaria como devueltas. Desde enero de 2025 la cobertura
# es continua.
VENTANA_LIMPIA = "2025-01-01"

# Marcas reconocibles en el campo DESCRIPCION del reporte de despachos.
MARCAS = ["SAMSUNG", "XIAOMI", "HONOR", "MOTOROLA", "IPHONE", "APPLE", "OPPO",
          "REALME", "TECNO", "INFINIX", "ZTE", "HUAWEI", "NOKIA", "ALCATEL",
          "LG", "VIVO", "POCO", "REDMI", "STARLINK", "TCL"]

SEMILLA = 42
