"""Lectores de las seis fuentes, con limpieza aplicada y cache en parquet.

Cada lector devuelve un DataFrame tipado y con nombres de columna normalizados.
Los que son costosos (ventas, stock de SIMs) cachean el resultado en
data/processed para que las iteraciones de modelado no vuelvan a leer Excel.
"""
from __future__ import annotations

import gzip
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import parsers as P
from .config import BODEGAS_INTERNAS, CRUDO, PROC, RE_RUC

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def _cache(nombre: str, fn, forzar: bool = False) -> pd.DataFrame:
    ruta = PROC / f"{nombre}.parquet"
    if ruta.exists() and not forzar:
        return pd.read_parquet(ruta)
    df = fn()
    df.to_parquet(ruta, index=False)
    return df


# --- Dimensiones -------------------------------------------------------------
def dim_bodega() -> pd.DataFrame:
    d = pd.read_excel(CRUDO / "Locations.xlsx")
    d = d.rename(columns={
        "Location Code": "bodega_id", "Description": "bodega_nombre",
        "CATEGOTIZACION": "categorizacion", "County": "region", "City": "ciudad",
        "Canal (Atrib 7)": "canal", "Distribuidor (Atrib 9)": "distribuidor_nombre",
        "Distribuidor para Cupo (Atrib 10)": "ruc",
        "Zona Courier (Atrib 12)": "provincia", "Tipo de BU": "tipo_bu",
        "Cat para Días de entrega desde el CD (Atrib 5)": "cat_entrega",
    })
    d["bodega_id"] = P.limpiar_texto(d["bodega_id"])
    d["ruc"] = P.limpiar_texto(d["ruc"])
    d = d.dropna(subset=["bodega_id"])
    d["es_distribuidor"] = d["ruc"].str.match(RE_RUC).fillna(False)
    d["es_interna"] = d["bodega_nombre"].str.contains(BODEGAS_INTERNAS, na=False)
    return d[["bodega_id", "bodega_nombre", "ruc", "es_distribuidor", "es_interna",
              "region", "provincia", "ciudad", "canal", "categorizacion",
              "tipo_bu", "cat_entrega", "distribuidor_nombre"]]


def dim_sku() -> pd.DataFrame:
    d = pd.read_excel(CRUDO / "Masterfile.xlsx")
    d.columns = ["modelo", "sku", "planning_group", "unit_cost", "unit_cube", "birth_year"]
    d["sku"] = P.limpiar_texto(d["sku"])
    d["modelo"] = d["modelo"].astype("string").str.strip()
    d["unit_cost"] = pd.to_numeric(d["unit_cost"], errors="coerce")
    # Centinelas de fecha del sistema de origen: 1990 = sin dato, 2075 = sin fin de vida.
    d["birth_year"] = d["birth_year"].replace({1990: np.nan})
    return d.drop(columns=["unit_cube"]).drop_duplicates("sku")


def dim_distribuidor() -> pd.DataFrame:
    d = pd.read_excel(CRUDO / "Cupo Disponible Distribuidores.xlsx")
    d = d.rename(columns={
        "Custom Attribute Code": "ruc", "Description": "distribuidor",
        "Valor del Cupo (en la moneda Configuración)": "cupo_valor",
        "Aplicar Cupo (0 no; 1 si)": "cupo_aplica",
        "campo CALCULADO - suma Stocks": "cupo_stock",
        "campo CALCULADO - suma Tránsitos": "cupo_transito",
        "campo CALCULADO - Cupo Neto Real": "cupo_neto",
    })
    d["ruc"] = P.limpiar_texto(d["ruc"])
    return d[["ruc", "distribuidor", "cupo_valor", "cupo_aplica",
              "cupo_stock", "cupo_transito", "cupo_neto"]].drop_duplicates("ruc")


# --- Hechos ------------------------------------------------------------------
def fact_ordenes(forzar: bool = False) -> pd.DataFrame:
    """ReporteLogistica: pedidos, devoluciones y transferencias.

    Los tres cortes diarios (pc/sc/tc) son incrementales -- verificado: 675
    filas producen 675 MOVE_ORDER_LINE_ID unicos, sin solapamiento. Aun asi se
    deduplica por la llave de linea, porque el historico podria no serlo.
    """
    def _leer():
        partes = []
        for f in sorted((CRUDO / "Reporte de pedidos").glob("*.csv")):
            # Los CSV vienen en latin-1, no en UTF-8.
            d = pd.read_csv(f, sep=";", dtype=str, encoding="latin-1")
            d["corte"] = f.name[16:18]
            d["fecha_corte"] = P.fecha_archivo_ordenes(f.name)
            partes.append(d)
        d = pd.concat(partes, ignore_index=True)

        d["fecha_hora"] = P.dt_ordenes(d["CREATED_WHEN"])   # P15: fecha del evento
        d["fecha"] = d["fecha_hora"].dt.normalize()
        d["cantidad"] = P.a_numero(d["APPROVED_QUANTITY"])  # P17: cifra contable
        d["recibido"] = P.a_numero(d["RECEIVED_QUANTITY"])
        d["despachado"] = P.a_numero(d["DISPATCHED_QUANTITY"])
        for c in ("LOCATION_FROM_ID", "LOCATION_TO_ID", "ARTICLE",
                  "EQUIPMENT_NAME", "EQUIPMENT_ID", "MO_TYPE", "MO_STATUS",
                  "TYPE_", "MOVEMENT_ORDER_ID", "MOVE_ORDER_LINE_ID"):
            d[c] = P.limpiar_texto(d[c])
        d["segmento"] = P.segmento(d["EQUIPMENT_NAME"])
        d = d.rename(columns={
            "MOVE_ORDER_LINE_ID": "linea_id", "MOVEMENT_ORDER_ID": "orden_id",
            "LOCATION_FROM_ID": "bodega_origen", "LOCATION_TO_ID": "bodega_destino",
            "LOCATION_FROM_NAME": "bodega_origen_nombre",
            "LOCATION_TO_NAME": "bodega_destino_nombre",
            "ARTICLE": "sku", "EQUIPMENT_NAME": "producto",
            "MO_TYPE": "mo_tipo", "MO_STATUS": "mo_estado", "TYPE_": "tipo_doc",
        })
        cols = ["linea_id", "orden_id", "fecha", "fecha_hora", "corte", "fecha_corte",
                "tipo_doc", "mo_tipo", "mo_estado", "producto", "sku", "segmento",
                "bodega_origen", "bodega_origen_nombre", "bodega_destino",
                "bodega_destino_nombre", "cantidad", "despachado", "recibido"]
        return d[cols].drop_duplicates("linea_id").reset_index(drop=True)

    return _cache("fact_ordenes", _leer, forzar)


def fact_ventas(forzar: bool = False) -> pd.DataFrame:
    """20 meses de movimientos serializados: sell-in a partner y sell-out.

    Solo se conserva la hoja 'Hoja1'; las demas son tablas dinamicas del
    analista. El motor calamine es ~6x mas rapido que openpyxl en estos
    archivos (8,6 s frente a 55 s cada uno).
    """
    def _leer():
        usar = ["Modelo", "IMEI  ", "ICCID", "Artículo", "Id Bodega Origen  ",
                "Bodega Origen", "Tipo de Movimiento ", "Propiedad Actual",
                "Fecha de Venta ", "Cuenta de Cliente ", "Precio de compra"]
        partes = []
        for f in sorted((CRUDO / "ventas").glob("*.xlsx")):
            # La hoja de detalle se llama 'Hoja1' casi siempre, pero en dos
            # archivos de 2024 se llama 'Data'. Se identifica por contenido:
            # es la unica que trae 'Tipo de Movimiento'.
            hojas = pd.ExcelFile(f, engine="calamine").sheet_names
            hoja = next((h for h in hojas if "Tipo de Movimiento" in
                         [str(c).strip() for c in pd.read_excel(
                             f, sheet_name=h, engine="calamine", nrows=0).columns]),
                        None)
            if hoja is None:
                print(f"    sin hoja de detalle: {f.name}")
                continue
            d = pd.read_excel(f, sheet_name=hoja, engine="calamine")
            d.columns = [c.strip() for c in d.columns]
            ren = {c.strip(): c.strip() for c in usar}
            d = d[[c for c in ren if c in d.columns]]
            d["archivo"] = f.stem
            partes.append(d)
        d = pd.concat(partes, ignore_index=True)

        d["imei"] = P.a_digitos(d["IMEI"], 14)
        d["iccid"] = P.a_digitos(d["ICCID"], 14)
        d["serie"] = d["imei"].fillna(d["iccid"])
        d["sku"] = P.limpiar_texto(d["Artículo"].astype("string")
                                   .str.replace(r"\.0$", "", regex=True))
        d["bodega_id"] = P.limpiar_texto(d["Id Bodega Origen"])
        d["cuenta"] = P.a_digitos(d["Cuenta de Cliente"], 5)
        d["fecha"] = P.dt_ventas(d["Fecha de Venta"]).dt.normalize()
        d["tipo_mov"] = d["Tipo de Movimiento"].astype("string").str.strip()
        d["precio"] = pd.to_numeric(d["Precio de compra"], errors="coerce")
        d["segmento"] = P.segmento(d["Modelo"])
        d["flujo"] = np.where(d["tipo_mov"].eq("Venta al Partner"), "SELL_IN", "SELL_OUT")
        return d[["serie", "imei", "iccid", "sku", "Modelo", "segmento", "flujo",
                  "tipo_mov", "bodega_id", "Bodega Origen", "cuenta", "fecha",
                  "precio", "archivo"]].rename(
            columns={"Modelo": "producto", "Bodega Origen": "bodega_nombre"})

    return _cache("fact_ventas", _leer, forzar)


def fact_stock_equipos(forzar: bool = False) -> pd.DataFrame:
    """Snapshot diario de IMEI en bodega. Cabecera en la fila 3 (skiprows=2)."""
    def _leer():
        partes = []
        for f in sorted((CRUDO / "Stock de equipos").glob("*.xlsx")):
            d = pd.read_excel(f, skiprows=2, engine="calamine")
            d.columns = ["producto", "sku", "bodega_nombre", "bodega_id", "estado_logico",
                         "estado_fisico", "imei", "serie", "condicion", "precio"]
            d["fecha"] = P.fecha_archivo_stock_equipos(f.name)
            partes.append(d)
        d = pd.concat(partes, ignore_index=True)
        d = d[d["imei"].notna() & d["bodega_id"].notna()]
        d["imei"] = P.a_digitos(d["imei"], 14)
        d["sku"] = P.limpiar_texto(d["sku"].astype("string")
                                   .str.replace(r"\.0$", "", regex=True))
        d["bodega_id"] = P.limpiar_texto(d["bodega_id"])
        d["precio"] = pd.to_numeric(d["precio"], errors="coerce")
        d["segmento"] = "EQUIPO"
        return d.dropna(subset=["imei"]).reset_index(drop=True)

    return _cache("fact_stock_equipos", _leer, forzar)


def fact_stock_sims(dias: int | None = None, forzar: bool = False) -> pd.DataFrame:
    """Snapshot diario de SIMs, ~2,3 M de filas por dia.

    Se agrega en la lectura a (fecha, bodega_nombre, producto, estado) porque el
    grano unitario no cabe en memoria y el modelo no lo necesita.

    Nota: el archivo trae el NOMBRE de la bodega, no su Location Code, de modo
    que el cruce con dim_bodega no es directo (0,1 % de coincidencia).
    """
    nombre = f"fact_stock_sims{'' if dias is None else f'_{dias}d'}"

    def _leer():
        cols = ["imsi", "iccid", "producto", "serie_larga", "estado_logico",
                "estado_fisico", "propiedad", "c8", "bodega_nombre", "autorizacion",
                "c11", "c12", "precio", "c14", "lote"]
        partes = []
        archivos = sorted((CRUDO / "Stock de simcards").glob("*.txt.gz"))
        if dias:
            archivos = archivos[-dias:]
        for f in archivos:
            with gzip.open(f, "rt", encoding="latin-1") as fh:
                d = pd.read_csv(fh, sep="|", header=None, names=cols,
                                dtype=str, na_values=["NULL"])
            d["fecha"] = P.fecha_archivo_stock_sims(f.name)
            d["precio"] = pd.to_numeric(d["precio"], errors="coerce")
            g = (d.groupby(["fecha", "bodega_nombre", "producto", "estado_logico",
                            "propiedad", "lote"], dropna=False)
                   .agg(unidades=("iccid", "size"), valor=("precio", "sum"))
                   .reset_index())
            partes.append(g)
        return pd.concat(partes, ignore_index=True)

    return _cache(nombre, _leer, forzar)
