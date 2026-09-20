"""Lectores de la entrega historica (carpeta `Data tesis`, 2024-2026).

Cambios frente a la entrega anterior:
  · Despachos  — reporte nuevo, a nivel de IMEI, con fecha y destino. 33 meses.
  · Stock      — snapshots diarios en carpetas anidadas por ano y mes. 33 meses.
  · Catalogos  — identicos a la entrega anterior.

Todos los lectores cachean en data/processed. La primera corrida sobre los
1.015 archivos de stock tarda varios minutos; las siguientes son inmediatas.
"""
from __future__ import annotations

import re
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import parsers as P
from .config import CRUDO, MARCAS, PROC

warnings.filterwarnings("ignore")

COLS_STOCK = ["modelo", "sku", "bodega_nombre", "bodega_id", "estado_logico",
              "estado_fisico", "imei", "serie", "condicion", "precio"]

# Los snapshots cambian de formato entre anos: varia el numero de filas de
# preambulo, el orden de las columnas y su cantidad (9 o 10). Lo unico estable
# son los nombres, asi que el mapeo se hace por nombre y no por posicion.
MAPA_STOCK = {
    "modelo": "modelo",
    "código del artículo": "sku",
    "codigo del articulo": "sku",
    "bodega": "bodega_nombre",
    "bodega id": "bodega_id",
    "estado lógico": "estado_logico",
    "estado logico": "estado_logico",
    "estado físico": "estado_fisico",
    "estado fisico": "estado_fisico",
    "imei": "imei",
    "número de serie": "serie",
    "numero de serie": "serie",
    "condición del equipo": "condicion",
    "condicion del equipo": "condicion",
    "precio de compra": "precio",
}


def _cache(nombre: str, fn, forzar: bool = False) -> pd.DataFrame:
    ruta = PROC / f"{nombre}.parquet"
    if ruta.exists() and not forzar:
        return pd.read_parquet(ruta)
    t = time.time()
    df = fn()
    df.to_parquet(ruta, index=False)
    print(f"  {nombre}: {len(df):,} filas en {time.time()-t:.0f}s")
    return df


def _serie_digitos(s: pd.Series, minimo: int = 14) -> pd.Series:
    """IMEI e ICCID llegan como texto, como numero o con notacion cientifica."""
    t = s.astype(str).str.replace(r"\.0$", "", regex=True)
    return t.str.extract(rf"(\d{{{minimo},}})", expand=False)


def marca_de(desc: pd.Series) -> pd.Series:
    """Extrae la marca del nombre comercial: 'LTE SAMSUNG A17 ...' -> SAMSUNG."""
    d = desc.astype(str).str.upper()
    out = pd.Series("OTRA", index=desc.index, dtype=object)
    for m in MARCAS:
        out = out.mask(out.eq("OTRA") & d.str.contains(rf"\b{m}\b", na=False), m)
    # IPHONE y los accesorios de Apple son la misma marca comercial.
    return out.replace({"IPHONE": "APPLE", "REDMI": "XIAOMI", "POCO": "XIAOMI"})


# --- Despachos ---------------------------------------------------------------
def fact_despachos(forzar: bool = False) -> pd.DataFrame:
    """Un registro por unidad despachada, con fecha, destino y distribuidor.

    Es la fuente que faltaba: da la fecha de salida de cada IMEI hacia un local
    concreto, que es lo que permite medir la antiguedad del inventario en poder
    del distribuidor.

    Tres variantes de esquema en los 33 archivos: 'PRECIO LISTA 4' frente a
    'PRECIO', y un archivo con una hoja extra al inicio. Se normalizan leyendo
    siempre la hoja 'MOVISTAR'.
    """
    def _leer():
        partes = []
        for f in sorted((CRUDO / "Despachos").glob("*.xlsx")):
            d = pd.read_excel(f, sheet_name="MOVISTAR", engine="calamine")
            d.columns = [str(c).strip().upper() for c in d.columns]
            d = d.rename(columns={"PRECIO LISTA 4": "PRECIO"})
            partes.append(d)
        d = pd.concat(partes, ignore_index=True)

        d["fecha"] = pd.to_datetime(d["FECHA"], dayfirst=True, errors="coerce")
        d["imei"] = _serie_digitos(d["IMEI"])
        d["iccid"] = _serie_digitos(d["ICC"])
        d["sku"] = d["CODIGO SCL"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        d["producto"] = d["DESCRIPCION"].astype(str).str.strip()
        d["marca"] = marca_de(d["producto"])
        d["ruc"] = d["RUC"].astype(str).str.extract(r"(\d{10,13})", expand=False)
        d["destino"] = d["CLIENTE"].astype(str).str.strip()
        d["destino_cod"] = d["CODIGO DA"].astype(str).str.strip()
        d["cantidad"] = pd.to_numeric(d["CANTIDAD"], errors="coerce").fillna(1)
        d["precio"] = pd.to_numeric(d["PRECIO"], errors="coerce")
        d["tipo_articulo"] = d["TIPO ARTICULO"].astype(str).str.strip().str.upper()
        d["canal"] = d["CANAL"].astype(str).str.strip().str.upper()
        d["ciudad"] = d["CIUDAD"].astype(str).str.strip().str.upper()
        d["pedido"] = d["PEDIDO"].astype(str).str.strip()
        # Un TERMINAL siempre lleva IMEI; una SIMCARD lleva ICCID.
        d["segmento"] = np.where(d["tipo_articulo"].str.startswith("TERMINAL"),
                                 "EQUIPO",
                                 np.where(d["tipo_articulo"].eq("SIMCARD"), "SIM", "OTRO"))
        cols = ["fecha", "pedido", "imei", "iccid", "sku", "producto", "marca",
                "segmento", "tipo_articulo", "canal", "ruc", "destino",
                "destino_cod", "ciudad", "cantidad", "precio"]
        return d[cols]

    return _cache("v2_despachos", _leer, forzar)


# --- Stock diario ------------------------------------------------------------
def _leer_snapshot(f: Path) -> pd.DataFrame | None:
    """Lee un snapshot detectando la fila de cabecera.

    El preambulo del reporte cambia entre anos: en 2024 los datos empiezan en
    la fila 0, en 2025-2026 hay tres filas de encabezado. Buscar la celda
    'Modelo' es mas robusto que fijar skiprows.
    """
    # Algunos archivos traen primero una hoja con los filtros del reporte y los
    # datos en la segunda. Se recorre hasta encontrar la hoja que tenga la
    # cabecera; buscar solo en la primera pierde esos cortes.
    d = fila = None
    for hoja in pd.ExcelFile(f, engine="calamine").sheet_names:
        h = pd.read_excel(f, sheet_name=hoja, engine="calamine", header=None)
        # La cabecera es la primera fila con la celda 'Modelo', en cualquier
        # columna: en 2024 el IMEI va primero, desde 2025 va el Modelo.
        # Se exigen 'Modelo' e 'IMEI' en la misma fila. Con 'Modelo' a secas se
        # cuela la tabla dinamica que algunos archivos traen al inicio, cuya
        # celda A1 dice exactamente eso.
        def _cabecera(fila_):
            v = set(fila_.astype(str).str.strip().str.lower())
            return {"modelo", "imei"} <= v

        i = next((k for k in range(min(10, len(h))) if _cabecera(h.iloc[k])), None)
        if i is not None:
            d, fila = h, i
            break
    if fila is None:
        return None
    cab = d.iloc[fila].astype(str).str.strip().str.lower()
    cuerpo = d.iloc[fila + 1:].reset_index(drop=True)
    cuerpo.columns = [MAPA_STOCK.get(c, f"_ignorar_{i}") for i, c in enumerate(cab)]
    cuerpo = cuerpo.loc[:, ~cuerpo.columns.str.startswith("_ignorar_")]
    if "imei" not in cuerpo.columns or "bodega_id" not in cuerpo.columns:
        return None
    for c in COLS_STOCK:                       # columnas ausentes en el formato viejo
        if c not in cuerpo.columns:
            cuerpo[c] = pd.NA
    return cuerpo[COLS_STOCK]


def _fecha_snapshot(nombre: str) -> pd.Timestamp | None:
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", nombre)   # MM-DD-AAAA
    if not m:
        return None
    mm, dd, aaaa = m.groups()
    try:
        return pd.Timestamp(f"{aaaa}-{mm}-{dd}")
    except ValueError:
        return None


def fact_stock(forzar: bool = False) -> pd.DataFrame:
    """Snapshot diario de IMEI en bodega, 2024-2026 (~1.000 archivos).

    Se descarta la subcarpeta EAE, que contiene checklists y no inventario.
    """
    def _leer():
        archivos = [f for f in sorted((CRUDO / "Stock de equipos").rglob("*.xlsx"))
                    if "EAE" not in f.parts and not f.name.startswith("~$")]
        partes, fallidos = [], []
        for i, f in enumerate(archivos, 1):
            fecha = _fecha_snapshot(f.name)
            if fecha is None:
                fallidos.append((f.name, "sin fecha")); continue
            try:
                d = _leer_snapshot(f)
            except Exception as e:                       # archivo corrupto
                fallidos.append((f.name, str(e)[:40])); continue
            if d is None:
                fallidos.append((f.name, "sin cabecera")); continue
            d["fecha"] = fecha
            partes.append(d)
            if i % 200 == 0:
                print(f"    {i}/{len(archivos)} snapshots...")
        d = pd.concat(partes, ignore_index=True)
        if fallidos:
            print(f"    {len(fallidos)} archivos omitidos, p.ej. {fallidos[:3]}")

        d["imei"] = _serie_digitos(d["imei"])
        d["sku"] = d["sku"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        d["bodega_id"] = d["bodega_id"].astype(str).str.strip()
        d["bodega_nombre"] = d["bodega_nombre"].astype(str).str.strip()
        d["precio"] = pd.to_numeric(d["precio"], errors="coerce")
        d["marca"] = marca_de(d["modelo"])
        d = d[d["imei"].notna()]
        # Datos de prueba que el sistema dejo en los primeros snapshots de 2024.
        d = d[~d["modelo"].astype(str).str.upper().str.startswith("PRUEBA")]
        # Los campos de texto llegan con tipos mezclados segun el ano.
        for c in ("modelo", "sku", "bodega_nombre", "bodega_id",
                  "estado_logico", "estado_fisico", "condicion", "serie"):
            d[c] = d[c].astype(str).str.strip().replace({"nan": None, "None": None})
        return d.reset_index(drop=True)

    return _cache("v2_stock", _leer, forzar)


# --- Catalogos (identicos a la entrega anterior) ------------------------------
def dim_bodega() -> pd.DataFrame:
    from .sources import dim_bodega as _d
    return _d()


def dim_sku() -> pd.DataFrame:
    from .sources import dim_sku as _d
    return _d()


def dim_distribuidor() -> pd.DataFrame:
    from .sources import dim_distribuidor as _d
    return _d()
