"""Entrega complementaria de agosto y septiembre de 2026 (carpeta `data 3`).

Dos diferencias frente a la entrega historica que obligan a un lector aparte:

1. **La hoja ya no se llama MOVISTAR.** Telefonica Ecuador pasa a operar como
   Tigo, y el consolidado de septiembre trae la hoja `TIGO`. `fuentes.py` fija
   la hoja a `MOVISTAR`, asi que fallaria. Aqui se toma la primera hoja que
   tenga las columnas esperadas, sea cual sea su nombre.

2. **Las rutas son distintas**: `despachos/` y `stock/<n>. <Mes>/` en minuscula,
   frente a `Despachos/` y `Stock de equipos/` de la entrega original.

La limpieza es **identica** a la de `fuentes.py`: se reutilizan sus funciones
para que una fila leida aqui sea indistinguible de una leida alli.

Que aporta realmente la entrega, comprobado contra lo que ya habia:

    inventario agosto      ya estaba completo (30 de 31 dias)
    inventario septiembre  13 dias nuevos, del 18 al 30
    despachos agosto       equivalente a lo que habia (3.915 vs 3.908)
    despachos septiembre   mes completo, 6.199 equipos frente a 2.364 parciales

Es decir: **agosto ya era medible** y se habia excluido por precaucion.
Septiembre es lo que esta entrega desbloquea de verdad.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import RAIZ
from .fuentes import (COLS_STOCK, _fecha_snapshot, _leer_snapshot,
                      _serie_digitos, marca_de)

CRUDO3 = RAIZ / "data 3"
CORTE_NUEVO = pd.Timestamp("2026-08-01")     # desde aqui manda la entrega nueva

COLS_DESP = ["FECHA", "PEDIDO", "IMEI", "ICC", "CODIGO SCL", "DESCRIPCION",
             "CANTIDAD", "PRECIO", "CODIGO DA", "CLIENTE", "RUC", "CIUDAD",
             "CANAL", "TIPO ARTICULO"]


def _hoja_de_despachos(f: Path) -> pd.DataFrame:
    """Devuelve la hoja del consolidado, sin depender de como se llame.

    La entrega historica siempre traia `MOVISTAR`; esta trae `TIGO`. Se busca
    por contenido —las columnas FECHA e IMEI— en vez de por nombre.
    """
    xl = pd.ExcelFile(f, engine="calamine")
    for hoja in xl.sheet_names:
        d = pd.read_excel(f, sheet_name=hoja, engine="calamine")
        cols = {str(c).strip().upper() for c in d.columns}
        if {"FECHA", "IMEI", "TIPO ARTICULO"} <= cols:
            d.columns = [str(c).strip().upper() for c in d.columns]
            return d.rename(columns={"PRECIO LISTA 4": "PRECIO"})
    raise ValueError(f"{f.name}: ninguna hoja tiene las columnas esperadas")


def despachos_nuevos() -> pd.DataFrame:
    """Despachos de agosto y septiembre, con el mismo esquema que `fuentes`."""
    partes = []
    for f in sorted((CRUDO3 / "despachos").glob("*.xlsx")):
        if f.name.startswith("~$"):
            continue
        partes.append(_hoja_de_despachos(f))
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
    d["segmento"] = np.where(d["tipo_articulo"].str.startswith("TERMINAL"), "EQUIPO",
                      np.where(d["tipo_articulo"].eq("SIMCARD"), "SIM", "OTRO"))
    cols = ["fecha", "pedido", "imei", "iccid", "sku", "producto", "marca",
            "segmento", "tipo_articulo", "canal", "ruc", "destino",
            "destino_cod", "ciudad", "cantidad", "precio"]
    return d[cols]


def stock_nuevo() -> pd.DataFrame:
    """Snapshots diarios de agosto y septiembre."""
    archivos = [f for f in sorted((CRUDO3 / "stock").rglob("*.xlsx"))
                if not f.name.startswith("~$")]
    partes, fallidos = [], []
    for f in archivos:
        fecha = _fecha_snapshot(f.name)
        if fecha is None:
            fallidos.append((f.name, "sin fecha")); continue
        try:
            d = _leer_snapshot(f)
        except Exception as e:
            fallidos.append((f.name, str(e)[:40])); continue
        if d is None:
            fallidos.append((f.name, "sin cabecera")); continue
        d["fecha"] = fecha
        partes.append(d)
    if fallidos:
        print(f"    {len(fallidos)} archivos omitidos: {fallidos[:3]}")
    d = pd.concat(partes, ignore_index=True)

    d["imei"] = _serie_digitos(d["imei"])
    d["sku"] = d["sku"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    d["bodega_id"] = d["bodega_id"].astype(str).str.strip()
    d["bodega_nombre"] = d["bodega_nombre"].astype(str).str.strip()
    d["precio"] = pd.to_numeric(d["precio"], errors="coerce")
    d["marca"] = marca_de(d["modelo"])
    d = d[d["imei"].notna()]
    d = d[~d["modelo"].astype(str).str.upper().str.startswith("PRUEBA")]
    for c in ("modelo", "sku", "bodega_nombre", "bodega_id",
              "estado_logico", "estado_fisico", "condicion", "serie"):
        d[c] = d[c].astype(str).str.strip().replace({"nan": None, "None": None})
    return d.reset_index(drop=True)


def despachos_extendido(v2: pd.DataFrame) -> pd.DataFrame:
    """Historico hasta julio + entrega nueva para agosto y septiembre.

    Se corta en agosto y no se mezcla: la entrega nueva trae esos dos meses
    completos, mientras que el historico tenia septiembre a medias (hasta el
    11). Concatenar sin cortar duplicaria las filas que aparecen en ambas.
    """
    nuevo = despachos_nuevos()
    viejo = v2[v2.fecha < CORTE_NUEVO]
    return pd.concat([viejo, nuevo[nuevo.fecha >= CORTE_NUEVO]],
                     ignore_index=True).sort_values("fecha").reset_index(drop=True)


def stock_extendido(v2: pd.DataFrame) -> pd.DataFrame:
    """Historico + los dias de inventario que el historico no tenia.

    A diferencia de los despachos, aqui no se reemplaza nada: se anaden solo
    las fechas ausentes. Agosto ya estaba completo en el historico y volver a
    cargarlo no aporta, solo cuesta memoria.
    """
    ya = set(v2.fecha.unique())
    nuevo = stock_nuevo()
    faltan = nuevo[~nuevo.fecha.isin(ya)]
    print(f"    dias de inventario anadidos: {faltan.fecha.nunique()} "
          f"({faltan.fecha.min():%d-%b} a {faltan.fecha.max():%d-%b-%Y})"
          if len(faltan) else "    sin dias nuevos")
    return pd.concat([v2, faltan], ignore_index=True).reset_index(drop=True)
