"""Seudonimiza los artefactos procesados que contienen identificadores.

Lee de `data/processed/` y escribe en `data/seudonimizado/`. **Nunca modifica ni borra
los originales**: retirar los archivos en claro es una decision aparte, que se toma
despues de comprobar la equivalencia con `scripts/verificar_equivalencia.py`.

Requiere la clave en la variable de entorno PRY_CLAVE_SEUDONIMIZACION. Ver
`src/seudonimizar.py` para generarla y para saber donde guardarla.

Uso::

    python scripts/seudonimizar_artefactos.py                      # todos los que tienen identificadores
    python scripts/seudonimizar_artefactos.py --archivos v6_stock v6_despachos
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd
import pyarrow.parquet as pq

from src import seudonimizar as S
from src.config import PROC

CON_IDENTIFICADORES = set(S.COLUMNAS_TOKEN) | set(S.COLUMNAS_ALIAS)


def candidatos(entrada: Path) -> list[Path]:
    return [f for f in sorted(entrada.glob("*.parquet"))
            if CON_IDENTIFICADORES & set(pq.ParquetFile(f).schema.names)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--entrada", type=Path, default=PROC)
    ap.add_argument("--salida", type=Path, default=RAIZ / "data" / "seudonimizado")
    ap.add_argument("--archivos", nargs="*", help="nombres sin extension; por defecto, todos")
    a = ap.parse_args()

    if a.salida.resolve() == a.entrada.resolve():
        print("La salida no puede ser la carpeta de entrada: no se sobrescriben los originales.")
        return 2

    clave = S.cargar_clave()
    todos = candidatos(a.entrada)
    if a.archivos:
        pedidos = set(a.archivos)
        todos = [f for f in todos if f.stem in pedidos]
        faltan = pedidos - {f.stem for f in todos}
        if faltan:
            print(f"No hay artefactos con identificadores llamados: {sorted(faltan)}")
            return 2

    a.salida.mkdir(parents=True, exist_ok=True)
    print(f"{len(todos)} artefactos -> {a.salida}\n")
    fallos = 0
    for f in todos:
        t0 = time.time()
        df = pd.read_parquet(f)
        s = S.seudonimizar(df, clave)
        restos = S.identificadores_en_claro(s)
        if restos:
            print(f"  FALLO {f.name}: quedan identificadores en claro: {restos}")
            fallos += 1
            continue
        s.to_parquet(a.salida / f.name, index=False)
        cols = sorted(CON_IDENTIFICADORES & set(df.columns))
        print(f"  ok  {f.name:<32} {len(df):>11,} filas · {', '.join(cols)} · {time.time()-t0:.0f}s")
        del df, s
    print("\nLos originales no se han tocado." if not fallos else f"\n{fallos} archivo(s) con fallos.")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
