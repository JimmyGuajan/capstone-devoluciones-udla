"""Guardar o verificar los artefactos que producen los scripts de la cadena.

Cada script construye un artefacto y lo pasa por `guardar_o_verificar`:

  * si el archivo todavia no existe, lo escribe;
  * si ya existe, **no lo sobrescribe**: compara el recien construido con el que hay y
    dice si coinciden. Asi, volver a ejecutar la cadena sobre los mismos datos es una
    prueba de reproducibilidad y no un riesgo para los resultados ya reportados;
  * con `forzar=True` lo reemplaza.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def comparar(nuevo: pd.DataFrame, existente: pd.DataFrame, tolerancia: float = 0.0) -> list[str]:
    """Lista de diferencias entre dos tablas; vacia si coinciden.

    `tolerancia` > 0 admite diferencias relativas en las columnas numericas
    (se usa solo para modelos con paralelismo, que no son identicos bit a bit).
    """
    if len(nuevo) != len(existente):
        return [f"filas: {len(nuevo):,} frente a {len(existente):,}"]
    faltan = [c for c in existente.columns if c not in nuevo.columns]
    if faltan:
        return [f"faltan columnas: {faltan}"]
    a = nuevo[list(existente.columns)].reset_index(drop=True)
    b = existente.reset_index(drop=True)
    distintas = []
    for c in b.columns:
        try:
            pd.testing.assert_series_equal(a[c], b[c], check_dtype=False, check_names=False,
                                           rtol=tolerancia or 1e-5, atol=tolerancia or 1e-8,
                                           check_exact=tolerancia == 0)
        except AssertionError:
            distintas.append(c)
    return [f"columnas distintas: {distintas}"] if distintas else []


def guardar_o_verificar(df: pd.DataFrame, ruta: Path, forzar: bool = False,
                        tolerancia: float = 0.0) -> str:
    """Escribe `df` si no hay archivo; si lo hay, verifica. Devuelve un estado legible."""
    if not ruta.exists() or forzar:
        existia = ruta.exists()
        df.to_parquet(ruta, index=False)
        return f"{'REEMPLAZADO' if existia else 'escrito'}  {ruta.name} ({len(df):,} filas)"
    diferencias = comparar(df, pd.read_parquet(ruta), tolerancia)
    if diferencias:
        return f"DIFIERE   {ruta.name}: {'; '.join(diferencias)}"
    return f"identico  {ruta.name} ({len(df):,} filas)"


def hay_diferencias(estados: list[str]) -> bool:
    return any(e.startswith("DIFIERE") for e in estados)
