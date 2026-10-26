"""Paso 2 de la cadena: estadias y ciclo de vida por unidad (artefactos `v2_*`).

Parte de los inventarios y despachos consolidados hasta julio de 2026 y produce:

  v2_estadias        un tramo por (unidad, bodega): donde estuvo cada IMEI y cuanto tiempo
  v2_ciclo_unidad    una fila por unidad despachada, con su desenlace (venta, retorno, 60 dias)

Entradas: `v2_stock`, `v2_despachos` y `fact_ventas` en `data/processed/`. Si no existen se
construyen desde los archivos crudos (`src/fuentes.py`, `src/sources.py`), lo que tarda varios
minutos y requiere la carpeta `Data tesis/`.

Regla que importa: del archivo de ventas solo cuentan las de **cliente final (SELL_OUT)**.
`fact_ventas` tambien trae SELL_IN, la venta del fabricante al distribuidor, que ocurre
*antes* de que la unidad llegue al local; contarla marcaria como "vendida" a una unidad que
apenas salio de bodega central (21 de 257.150 unidades).

Si el artefacto ya existe, el script lo compara y no lo sobrescribe (ver `src/artefactos.py`).

Uso::

    python scripts/construir_v2.py              # construye y verifica
    python scripts/construir_v2.py --forzar     # reemplaza los artefactos existentes
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd

from src import artefactos as A
from src import ciclo as CI
from src.config import PROC


def leer_o_construir(nombre: str, constructor) -> pd.DataFrame:
    ruta = PROC / f"{nombre}.parquet"
    return pd.read_parquet(ruta) if ruta.exists() else constructor()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--forzar", action="store_true", help="reemplaza los artefactos existentes")
    a = ap.parse_args()
    t0 = time.time()

    from src import fuentes, sources
    print("Entradas...", flush=True)
    stock = leer_o_construir("v2_stock", fuentes.fact_stock)
    despachos = leer_o_construir("v2_despachos", fuentes.fact_despachos)
    ventas = leer_o_construir("fact_ventas", sources.fact_ventas)
    print(f"  inventario {len(stock):,} filas · despachos {len(despachos):,} · ventas {len(ventas):,}")

    print("Estadias...", flush=True)
    estadias = CI.estadias(stock)
    del stock

    print("Ciclo de vida por unidad...", flush=True)
    ciclo = CI.construir(despachos, estadias, ventas[ventas.flujo.eq("SELL_OUT")])

    estados = [A.guardar_o_verificar(estadias, PROC / "v2_estadias.parquet", a.forzar),
               A.guardar_o_verificar(ciclo, PROC / "v2_ciclo_unidad.parquet", a.forzar)]
    print()
    for e in estados:
        print(" ", e)
    print(f"\n{time.time() - t0:.0f}s")
    return 1 if A.hay_diferencias(estados) else 0


if __name__ == "__main__":
    sys.exit(main())
