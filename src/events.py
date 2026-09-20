"""Clasificacion de eventos logisticos: el nucleo del proyecto.

La regla esta gobernada por la DIRECCION del movimiento (bodega origen y
destino), no por la etiqueta MO_TYPE. Verificado empiricamente: las 154 lineas
que entran a PK llevan las 154 la etiqueta 'Movimiento entre bodegas de TFN',
de modo que excluir esa etiqueta en bloque dejaria el target en cero.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CENTRAL

PEDIDO = "PEDIDO"
DEVOLUCION = "DEVOLUCION"
INTRA = "INTRA_DISTRIBUIDOR"
TIENDA_PROPIA = "TIENDA_PROPIA"
INTERNO = "INTERNO_TELEFONICA"
OTRO = "OTRO"


def clasificar(ordenes: pd.DataFrame, bodegas: pd.DataFrame) -> pd.DataFrame:
    """Anade columnas clase, ruc y bandera de catalogo a las lineas de orden."""
    distrib = bodegas.loc[bodegas.es_distribuidor].set_index("bodega_id")["ruc"]
    internas = set(bodegas.loc[bodegas.es_interna, "bodega_id"])
    conocidas = set(bodegas["bodega_id"])

    d = ordenes.copy()
    d["ruc_origen"] = d["bodega_origen"].map(distrib)
    d["ruc_destino"] = d["bodega_destino"].map(distrib)

    o_central = d["bodega_origen"].isin(CENTRAL)
    d_central = d["bodega_destino"].isin(CENTRAL)
    o_distrib = d["ruc_origen"].notna()
    d_distrib = d["ruc_destino"].notna()
    o_interna = d["bodega_origen"].isin(internas) | o_central
    d_interna = d["bodega_destino"].isin(internas) | d_central

    d["clase"] = np.select(
        [
            o_distrib & d_central,              # ★ TARGET
            o_central & d_distrib,              # sell-in
            o_distrib & d_distrib,              # excluido (hallazgo N5)
            o_interna & d_interna,              # logistica interna
            o_central & ~d_distrib & ~d_central,
        ],
        [DEVOLUCION, PEDIDO, INTRA, INTERNO, TIENDA_PROPIA],
        default=OTRO,
    )

    # El distribuidor al que se imputa el evento.
    d["ruc"] = d["ruc_origen"].fillna(d["ruc_destino"])

    # Trazabilidad de la calidad del catalogo: una linea "sin catalogo" no es un
    # error de la regla, es una bodega que el cliente todavia no entrego.
    d["bodega_sin_catalogo"] = ~(d["bodega_origen"].isin(conocidas)
                                 & d["bodega_destino"].isin(conocidas))
    return d


def resumen_clasificacion(d: pd.DataFrame) -> pd.DataFrame:
    r = (d.groupby("clase")
           .agg(lineas=("cantidad", "size"), unidades=("cantidad", "sum"),
                sin_catalogo=("bodega_sin_catalogo", "sum"))
           .sort_values("lineas", ascending=False))
    r["pct_lineas"] = (r["lineas"] / r["lineas"].sum() * 100).round(1)
    return r


def diagnostico_censura(d: pd.DataFrame) -> pd.DataFrame:
    """Hallazgo N11: las ordenes en Submitted no se han consumado.

    Si el target se contabiliza por CREATED_WHEN, los periodos mas recientes
    contienen una proporcion mayor de ordenes sin desenlace y quedan
    sistematicamente subestimados. Esta tabla mide la magnitud del sesgo.
    """
    dev = d[d.clase == DEVOLUCION]
    r = (dev.groupby("mo_estado")
            .agg(lineas=("cantidad", "size"), unidades=("cantidad", "sum")))
    r["pct"] = (r["lineas"] / r["lineas"].sum() * 100).round(1)
    return r
