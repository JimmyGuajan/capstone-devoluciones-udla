"""Limpieza de tipos y parseo de fechas.

El proyecto convive con cuatro convenciones de fecha en nombres de archivo y
dos en campos internos. La inferencia automatica de pandas sobre estas reglas
produce errores silenciosos de hasta once meses, asi que todo parseo aqui es
explicito por fuente y por campo.
"""
from __future__ import annotations

import re
import pandas as pd

from .config import NULOS, RE_SIM

# Excel coacciona a texto envolviendo el valor: ="356487402815749", ="".
RE_EXCEL = re.compile(r'^\s*=\s*"?(.*?)"?\s*$')


def limpiar_texto(s: pd.Series) -> pd.Series:
    """Quita el envoltorio ="..." de Excel y normaliza tokens de nulo."""
    out = s.astype("string").str.strip()
    out = out.str.replace(RE_EXCEL, r"\1", regex=True).str.strip()
    return out.mask(out.isin(NULOS) | out.isna())


def a_digitos(s: pd.Series, minimo: int = 10) -> pd.Series:
    """Extrae el identificador numerico (IMEI, ICCID, RUC) conservando ceros."""
    return limpiar_texto(s).str.extract(rf"(\d{{{minimo},}})", expand=False)


def a_numero(s: pd.Series) -> pd.Series:
    return pd.to_numeric(limpiar_texto(s), errors="coerce")


# --- Fechas ------------------------------------------------------------------
def dt_ordenes(s: pd.Series) -> pd.Series:
    """CREATED_WHEN de ReporteLogistica: DD/MM/AAAA HH:MM:SS."""
    return pd.to_datetime(s, format="%d/%m/%Y %H:%M:%S", errors="coerce")


def dt_ventas(s: pd.Series) -> pd.Series:
    """Fechas internas del reporte de ventas: MM-DD-AAAA HH-MM."""
    return pd.to_datetime(limpiar_texto(s), format="%m-%d-%Y %H-%M", errors="coerce")


def fecha_archivo_ordenes(nombre: str) -> pd.Timestamp:
    """ReporteLogistica{pc|sc|tc}DDMMAAAA.csv

    Verificado empiricamente: el archivo ...04092026.csv contiene movimientos
    del 3 y 4 de septiembre, de modo que la convencion es DDMMAAAA. El plan v4
    (hallazgo N15) la declaraba como MMDDAAAA; es incorrecto.
    """
    m = re.search(r"(\d{2})(\d{2})(\d{4})\.csv$", nombre)
    if not m:
        raise ValueError(f"nombre de archivo de ordenes no reconocido: {nombre}")
    dd, mm, aaaa = m.groups()
    return pd.Timestamp(f"{aaaa}-{mm}-{dd}")


def fecha_archivo_stock_equipos(nombre: str) -> pd.Timestamp:
    """...Serial-MM-DD-AAAA+HH-MM.xlsx"""
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", nombre)
    mm, dd, aaaa = m.groups()
    return pd.Timestamp(f"{aaaa}-{mm}-{dd}")


def fecha_archivo_stock_sims(nombre: str) -> pd.Timestamp:
    """Bodegas_AAAAMMDD.txt.gz"""
    m = re.search(r"(\d{4})(\d{2})(\d{2})", nombre)
    aaaa, mm, dd = m.groups()
    return pd.Timestamp(f"{aaaa}-{mm}-{dd}")


# --- Dominio -----------------------------------------------------------------
def segmento(nombre_producto: pd.Series) -> pd.Series:
    """SIM o EQUIPO a partir del nombre comercial del producto."""
    es_sim = nombre_producto.astype("string").str.contains(RE_SIM, na=False)
    return pd.Series(["SIM" if x else "EQUIPO" for x in es_sim],
                     index=nombre_producto.index, dtype="string")
