"""Paso 3 de la cadena: extension a agosto-septiembre de 2026 y panel del modelo (`v6_*`).

Parte de `v2_stock` y `v2_despachos` (hasta julio) y de la entrega complementaria `data 3/`
(agosto y septiembre), y produce:

  v6_stock          inventario diario hasta el 30-sep-2026
  v6_despachos      despachos hasta el 30-sep-2026
  v6_estadias       tramos (unidad, bodega) sobre el inventario extendido
  v6_periodos       permanencia en canal de cada unidad, con su fecha de umbral de 60 dias
  v6_panel_modelo   panel marca x mes con el grupo en riesgo y las variables rezagadas

Es la entrada de los cuadernos 06, 07 y 08. La logica esta en `src/extension.py` (lectura de la
entrega nueva) y `src/panel_modelo.py` (estadias -> periodos -> panel).

Si el artefacto ya existe, el script lo compara y no lo sobrescribe (ver `src/artefactos.py`).

Uso::

    python scripts/construir_v6.py              # construye y verifica
    python scripts/construir_v6.py --forzar     # reemplaza los artefactos existentes
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
from src import extension as X
from src import panel_modelo as PM
from src.config import PROC


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--forzar", action="store_true", help="reemplaza los artefactos existentes")
    a = ap.parse_args()
    t0 = time.time()
    estados: list[str] = []

    def paso(df: pd.DataFrame, nombre: str) -> None:
        e = A.guardar_o_verificar(df, PROC / f"{nombre}.parquet", a.forzar)
        estados.append(e)
        print(f"  {e}   [{time.time() - t0:.0f}s]", flush=True)

    print("Extension con la entrega de agosto-septiembre...", flush=True)
    stock = X.stock_extendido(pd.read_parquet(PROC / "v2_stock.parquet"))
    despachos = X.despachos_extendido(pd.read_parquet(PROC / "v2_despachos.parquet"))
    paso(stock, "v6_stock")
    paso(despachos, "v6_despachos")

    print("Estadias, periodos y panel...", flush=True)
    estadias = CI.estadias(stock)
    del stock
    paso(estadias, "v6_estadias")
    periodos = PM.periodos_desde_estadias(estadias, despachos)
    paso(periodos, "v6_periodos")
    paso(PM.construir_panel(periodos), "v6_panel_modelo")

    print(f"\n{time.time() - t0:.0f}s")
    return 1 if A.hay_diferencias(estados) else 0


if __name__ == "__main__":
    sys.exit(main())
