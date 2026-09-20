"""Carga del modelo dimensional a SQL Server para consulta con SELECT.

Publica los parquet de data/processed como tablas en una base propia, con
tipos explicitos, indices en las llaves y vistas de negocio. No toca ninguna
otra base del servidor.

Uso:
    python -m src.warehouse            # carga completa
    python -m src.warehouse --solo dim # solo las dimensiones
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc

from .config import PROC

SERVIDOR = r"(localdb)\MSSQLLocalDB"
BASE = "DW_DEVOLUCIONES_HIST"
DRIVER = "ODBC Driver 18 for SQL Server"

# parquet -> (esquema, tabla, llaves a indexar)
TABLAS = {
    "dim_bodega":         ("dim", "bodega", ["bodega_id", "ruc"]),
    "dim_sku":            ("dim", "sku", ["sku"]),
    "dim_distribuidor":   ("dim", "distribuidor", ["ruc"]),
    "v2_despachos":       ("fact", "despachos", ["fecha", "imei", "sku", "ruc", "marca", "segmento"]),
    "v2_stock":           ("fact", "stock", ["fecha", "imei", "bodega_id", "sku", "marca"]),
    "fact_ventas":        ("fact", "ventas", ["fecha", "imei", "bodega_id", "flujo", "segmento"]),
    "v2_estadias":        ("fact", "estadias", ["imei", "bodega_id", "desde", "hasta"]),
    "v2_ciclo_unidad":    ("mart", "ciclo_unidad", ["imei", "fecha_despacho", "marca", "ruc", "sku"]),
    "v2_panel_marca_mes": ("mart", "panel_marca_mes", ["marca", "mes"]),
}


def _conectar(base: str | None = None, autocommit: bool = False):
    cs = (f"DRIVER={{{DRIVER}}};SERVER={SERVIDOR};"
          "Trusted_Connection=yes;TrustServerCertificate=yes;")
    if base:
        cs += f"DATABASE={base};"
    return pyodbc.connect(cs, timeout=30, autocommit=autocommit)


def _tipo_sql(s: pd.Series) -> str:
    """Tipo SQL ajustado al contenido real; evita NVARCHAR(MAX) en todo."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return "DATETIME2(0)" if (s.dropna().dt.time.astype(str) != "00:00:00").any() else "DATE"
    if pd.api.types.is_bool_dtype(s):
        return "BIT"
    if pd.api.types.is_integer_dtype(s):
        return "BIGINT"
    if pd.api.types.is_float_dtype(s):
        return "FLOAT"
    sin_nulos = s.dropna()
    if sin_nulos.empty:                      # columna enteramente nula
        return "NVARCHAR(50)"
    largo = int(sin_nulos.astype(str).str.len().max())
    return f"NVARCHAR({min(max(largo + 20, 20), 4000)})"


def _preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza tipos de pandas a algo que el driver ODBC acepte."""
    d = df.copy()
    d.columns = [c.strip().replace(" ", "_") for c in d.columns]
    for c in d.columns:
        if str(d[c].dtype) in ("string", "object", "category"):
            d[c] = d[c].astype(object).where(d[c].notna(), None)
        elif pd.api.types.is_bool_dtype(d[c]):
            d[c] = d[c].astype(object).where(d[c].notna(), None)
        elif pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].astype(object).where(d[c].notna(), None)
        elif pd.api.types.is_integer_dtype(d[c]):
            d[c] = d[c].astype(object).where(d[c].notna(), None)
        elif pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.to_pydatetime()
            d[c] = pd.Series(d[c], dtype=object).where(df[c].notna().values, None)
    return d


def crear_base() -> None:
    with _conectar(autocommit=True) as c:
        cur = c.cursor()
        cur.execute(f"IF DB_ID('{BASE}') IS NULL CREATE DATABASE [{BASE}]")
    with _conectar(BASE, autocommit=True) as c:
        cur = c.cursor()
        for esq in ("dim", "fact", "mart"):
            cur.execute(
                f"IF SCHEMA_ID('{esq}') IS NULL EXEC('CREATE SCHEMA [{esq}]')")


def cargar_tabla(nombre_parquet: str, esquema: str, tabla: str,
                 indices: list[str], lote: int = 50_000) -> int:
    ruta = PROC / f"{nombre_parquet}.parquet"
    if not ruta.exists():
        print(f"  · {nombre_parquet:26s} no existe, se omite")
        return 0

    crudo = pd.read_parquet(ruta)
    crudo.columns = [c.strip().replace(" ", "_") for c in crudo.columns]
    tipos = {c: _tipo_sql(crudo[c]) for c in crudo.columns}   # tipos del dato original
    df = _preparar(crudo)                                     # valores listos para ODBC
    cols = list(df.columns)

    ddl = ", ".join(f"[{c}] {tipos[c]}" for c in cols)
    full = f"[{esquema}].[{tabla}]"

    with _conectar(BASE) as c:
        cur = c.cursor()
        cur.fast_executemany = True
        cur.execute(f"IF OBJECT_ID('{full}') IS NOT NULL DROP TABLE {full}")
        cur.execute(f"CREATE TABLE {full} ({ddl})")
        c.commit()

        marcas = ", ".join("?" * len(cols))
        sql = f"INSERT INTO {full} ([{'], ['.join(cols)}]) VALUES ({marcas})"
        datos = df.where(pd.notna(df), None).values.tolist()
        for i in range(0, len(datos), lote):
            cur.executemany(sql, datos[i:i + lote])
            c.commit()

        for col in indices:
            col = col.strip().replace(" ", "_")
            if col in cols:
                cur.execute(
                    f"CREATE INDEX [ix_{tabla}_{col}] ON {full} ([{col}])")
        c.commit()
    return len(df)


def crear_vistas() -> None:
    """Vistas de negocio: lo que se consulta a diario, ya resuelto."""
    vistas = {
        "mart.vw_devoluciones": """
            SELECT c.imei, c.marca, c.sku, c.producto, c.ruc, c.destino, c.ciudad,
                   c.canal, c.fecha_despacho, c.llegada_local, c.dias_en_local,
                   c.fecha_retorno, c.devuelta_60d, c.devuelta_real, c.vendida,
                   c.precio_despacho AS valor_usd,
                   c.mes_dev_60d, c.mes_dev_real, c.bodega_final_nombre, c.condicion
            FROM mart.ciclo_unidad c
            WHERE c.madura = 1 AND (c.devuelta_60d = 1 OR c.devuelta_real = 1)
        """,
        "mart.vw_resumen_marca": """
            SELECT marca,
                   COUNT(*)                                  AS despachadas,
                   SUM(CAST(vendida AS INT))                 AS vendidas,
                   SUM(CAST(devuelta_60d AS INT))            AS dev_regla_60d,
                   SUM(CAST(devuelta_real AS INT))           AS dev_retorno_fisico,
                   CAST(AVG(CAST(devuelta_60d AS FLOAT)) AS DECIMAL(6,4)) AS tasa_60d,
                   AVG(CAST(dias_en_local AS FLOAT))         AS dias_medios,
                   SUM(precio_despacho)                      AS valor_despachado
            FROM mart.ciclo_unidad WHERE madura = 1
            GROUP BY marca
        """,
        "mart.vw_resumen_distribuidor": """
            SELECT c.ruc, d.distribuidor, c.ciudad, c.canal,
                   COUNT(*)                                  AS despachadas,
                   SUM(CAST(c.devuelta_60d AS INT))          AS devueltas,
                   CAST(AVG(CAST(c.devuelta_60d AS FLOAT)) AS DECIMAL(6,4)) AS tasa,
                   AVG(CAST(c.dias_en_local AS FLOAT))       AS dias_medios,
                   SUM(c.precio_despacho)                    AS valor_despachado
            FROM mart.ciclo_unidad c
            LEFT JOIN dim.distribuidor d ON d.ruc = c.ruc
            WHERE c.madura = 1
            GROUP BY c.ruc, d.distribuidor, c.ciudad, c.canal
        """,
        "mart.vw_estacionalidad": """
            SELECT marca, MONTH(mes) AS mes_num, YEAR(mes) AS anio,
                   SUM(despachadas) AS despachadas, SUM(devueltas) AS devueltas,
                   SUM(valor_devuelto) AS valor_devuelto
            FROM mart.panel_marca_mes
            GROUP BY marca, MONTH(mes), YEAR(mes)
        """,
        "mart.vw_obsolescencia": """
            SELECT fecha, COUNT(*) AS unidades,
                   SUM(CASE WHEN condicion = 'Obsoleto' THEN 1 ELSE 0 END) AS obsoletas,
                   CAST(100.0 * SUM(CASE WHEN condicion = 'Obsoleto' THEN 1 ELSE 0 END)
                        / COUNT(*) AS DECIMAL(6,3)) AS pct_obsoleto,
                   SUM(precio) AS valor_usd
            FROM fact.stock
            GROUP BY fecha
        """,
    }
    with _conectar(BASE, autocommit=True) as c:
        cur = c.cursor()
        for nombre, sql in vistas.items():
            cur.execute(f"IF OBJECT_ID('{nombre}') IS NOT NULL DROP VIEW {nombre}")
            try:
                cur.execute(f"CREATE VIEW {nombre} AS {sql}")
                print(f"  · vista {nombre}")
            except pyodbc.ProgrammingError as err:
                # Falta alguna tabla base: se omite la vista en vez de abortar.
                print(f"  · vista {nombre} omitida ({str(err)[:60]}...)")


def materializar_dimensiones() -> None:
    """Las dimensiones se calculan al vuelo en sources.py; aqui se persisten."""
    from . import sources as S
    for nombre, fn in (("dim_bodega", S.dim_bodega),
                       ("dim_sku", S.dim_sku),
                       ("dim_distribuidor", S.dim_distribuidor)):
        ruta = PROC / f"{nombre}.parquet"
        if not ruta.exists():
            fn().to_parquet(ruta, index=False)


def main(solo: str | None = None) -> None:
    t0 = time.time()
    print(f"Servidor : {SERVIDOR}")
    print(f"Base     : {BASE}\n")
    materializar_dimensiones()
    crear_base()
    total = 0
    for parquet, (esq, tabla, idx) in TABLAS.items():
        if solo and not parquet.startswith(solo):
            continue
        t = time.time()
        n = cargar_tabla(parquet, esq, tabla, idx)
        if n:
            print(f"  · {esq}.{tabla:<18s} {n:>9,} filas  ({time.time()-t:5.1f}s)")
        total += n
    print()
    crear_vistas()
    print(f"\n{total:,} filas cargadas en {time.time()-t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", help="prefijo de tabla a cargar")
    main(**vars(ap.parse_args()))
