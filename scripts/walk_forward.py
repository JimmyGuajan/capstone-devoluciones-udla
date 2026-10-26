"""Paso 4 de la cadena: validacion walk-forward y lineas base (artefacto `v7_walkforward`).

Reentrena cada modelo en cada mes de evaluacion usando solo el pasado y predice ese mes. Produce:

  data/processed/v7_walkforward.parquet     21 origenes x 4 modelos; lo lee el cuaderno 07
  reports/walkforward_con_lineas_base.csv   resumen de los 4 modelos mas dos referencias simples:
                                            "Cero" (no anticipa nada) y "Media movil 3 meses"

Entrada: `data/processed/v6_panel_modelo.parquet` (lo produce `construir_v6.py`).

Si `v7_walkforward` ya existe, el script lo compara y no lo sobrescribe. Random Forest se compara con
tolerancia (el paralelismo no garantiza igualdad bit a bit); el resto debe coincidir exactamente.

Uso::

    python scripts/walk_forward.py
    python scripts/walk_forward.py --forzar
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.modules["bottleneck"] = None      # evita un conflicto de versiones con pandas

import pandas as pd

from src import artefactos as A
from src import validacion as V
from src.config import PROC, REPORTES


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--forzar", action="store_true", help="reemplaza v7_walkforward si existe")
    a = ap.parse_args()
    t0 = time.time()

    panel = pd.read_parquet(PROC / "v6_panel_modelo.parquet")
    print(f"Panel: {len(panel)} filas · {panel.mes.nunique()} meses. "
          f"Origenes: {len(V.origenes(panel))}", flush=True)

    print("Walk-forward (reentrena en cada origen)...", flush=True)
    w = V.walk_forward(panel)
    estado = A.guardar_o_verificar(w, PROC / "v7_walkforward.parquet", a.forzar, tolerancia=1e-9)
    print(f"  {estado}   [{time.time() - t0:.0f}s]")

    ref = REPORTES / "walkforward.csv"
    if ref.exists():
        previo = pd.read_csv(ref, index_col=0)
        nuevo = V.resumen(w).loc[previo.index]
        ok = (nuevo - previo).abs().max().max() < 0.015
        print(f"  resumen frente a reports/walkforward.csv: {'coincide' if ok else 'DIFIERE'}")
        if not ok:
            estado = "DIFIERE resumen"

    print("Lineas base...", flush=True)
    todo = pd.concat([w, V.lineas_base(panel)], ignore_index=True)
    r = V.resumen(todo)
    r.to_csv(REPORTES / "walkforward_con_lineas_base.csv")
    print(r.to_string())
    print(f"\n{time.time() - t0:.0f}s")
    return 1 if A.hay_diferencias([estado]) else 0


if __name__ == "__main__":
    sys.exit(main())
