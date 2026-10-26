"""Comprueba que seudonimizar no altera ningun resultado.

Reconstruye la cadena completa --estadias, periodos de permanencia y panel-- a partir
de los inventarios y despachos **seudonimizados**, y la compara con la construida desde
los datos originales. Si las dos coinciden, la seudonimizacion no perjudica el analisis.

Comprueba, en orden:

  1. que en los datos seudonimizados no quede ningun identificador en claro;
  2. que los periodos de permanencia coincidan en numero, eventos y equipos distintos;
  3. que el panel marca x mes sea identico, celda por celda;
  4. que las predicciones del modelo final y su MAPE no cambien.

Uso::

    python scripts/verificar_equivalencia.py
    python scripts/verificar_equivalencia.py --seudonimizado data/seudonimizado_prueba
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import numpy as np
import pandas as pd

from src import panel_modelo as PM
from src import seudonimizar as S
from src.config import PROC

COMPROBACIONES: list[tuple[str, bool, str]] = []


def comprobar(nombre: str, ok: bool, detalle: str = "") -> None:
    COMPROBACIONES.append((nombre, bool(ok), detalle))
    print(f"  {'OK   ' if ok else 'FALLA'} {nombre}" + (f"  ({detalle})" if detalle else ""), flush=True)


def mape_mensual(real: pd.Series, pred: pd.Series) -> float:
    return float(np.mean(np.abs(real - pred) / real) * 100)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seudonimizado", type=Path, default=RAIZ / "data" / "seudonimizado")
    ap.add_argument("--originales", type=Path, default=PROC)
    a = ap.parse_args()
    t0 = time.time()

    print("Cargando datos seudonimizados...", flush=True)
    stock = pd.read_parquet(a.seudonimizado / "v6_stock.parquet")
    desp = pd.read_parquet(a.seudonimizado / "v6_despachos.parquet")

    print("\n1 · Identificadores en claro", flush=True)
    for nombre, df in (("inventario", stock), ("despachos", desp)):
        restos = S.identificadores_en_claro(df)
        comprobar(f"{nombre}: sin identificadores en claro", not restos, str(restos) if restos else "")
    comprobar("despachos: se conserva el tipo de RUC", "ruc_tipo" in desp.columns)

    print("\n2 · Periodos de permanencia", flush=True)
    per_nuevo = PM.construir_periodos(stock, desp)
    del stock
    per_ref = pd.read_parquet(a.originales / "v6_periodos.parquet")
    vn, vr = per_nuevo[~per_nuevo.sin_despacho], per_ref[~per_ref.sin_despacho]
    comprobar("periodos totales", len(per_nuevo) == len(per_ref), f"{len(per_nuevo):,} frente a {len(per_ref):,}")
    comprobar("periodos con despacho", len(vn) == len(vr), f"{len(vn):,} frente a {len(vr):,}")
    comprobar("eventos que cumplen el umbral", int(vn.cumple.sum()) == int(vr.cumple.sum()),
              f"{int(vn.cumple.sum()):,} frente a {int(vr.cumple.sum()):,}")
    comprobar("equipos distintos", per_nuevo.imei.nunique() == per_ref.imei.nunique(),
              f"{per_nuevo.imei.nunique():,} frente a {per_ref.imei.nunique():,}")
    comprobar("dias totales de permanencia", int(vn.dias_totales.sum()) == int(vr.dias_totales.sum()),
              f"{int(vn.dias_totales.sum()):,} frente a {int(vr.dias_totales.sum()):,}")

    print("\n3 · Panel marca x mes", flush=True)
    panel_nuevo = PM.construir_panel(per_nuevo)
    panel_ref = pd.read_parquet(a.originales / "v6_panel_modelo.parquet")
    comprobar("mismas dimensiones", panel_nuevo.shape == panel_ref.shape,
              f"{panel_nuevo.shape} frente a {panel_ref.shape}")
    cols = [c for c in panel_ref.columns if c in panel_nuevo.columns]
    claves = ["marca", "mes"]
    n = panel_nuevo[cols].sort_values(claves).reset_index(drop=True)
    r = panel_ref[cols].sort_values(claves).reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(n, r, check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-12)
        comprobar("panel identico celda por celda", True, f"{len(r)} filas · {len(cols)} columnas")
    except AssertionError as e:
        comprobar("panel identico celda por celda", False, str(e).splitlines()[0][:90])

    print("\n4 · Predicciones y metrica final", flush=True)
    meses = sorted(panel_ref[panel_ref.mes >= "2026-01-01"].mes.unique())
    pn = PM.prediccion_tasa_conversion(panel_nuevo, meses).groupby("mes")[["devueltas", "prediccion"]].sum()
    pr = PM.prediccion_tasa_conversion(panel_ref, meses).groupby("mes")[["devueltas", "prediccion"]].sum()
    comprobar("predicciones idénticas a las originales", np.allclose(pn.prediccion, pr.prediccion, rtol=1e-12),
              f"diferencia maxima {np.abs(pn.prediccion - pr.prediccion).max():.2e} unidades")
    mn, mr = mape_mensual(pn.devueltas, pn.prediccion), mape_mensual(pr.devueltas, pr.prediccion)
    comprobar("MAPE del volumen mensual", abs(mn - mr) < 1e-9, f"{mn:.4f} % frente a {mr:.4f} %")
    ref_informe = RAIZ / "reports" / "cuadro_v6.csv"
    if ref_informe.exists():
        c = pd.read_csv(ref_informe)
        redondeo = np.round(pn.prediccion.to_numpy()).astype(int)
        comprobar("coincide con reports/cuadro_v6.csv (lo que se ha reportado)",
                  np.all(np.abs(redondeo - c.predicho.to_numpy()) <= 1),
                  f"MAPE reportado {mn:.1f} %")

    fallos = [c for c in COMPROBACIONES if not c[1]]
    print(f"\n{len(COMPROBACIONES) - len(fallos)} de {len(COMPROBACIONES)} comprobaciones superadas "
          f"en {time.time() - t0:.0f}s")
    print("Resultado: la seudonimizacion NO altera ningun resultado." if not fallos
          else "Resultado: HAY DIFERENCIAS. No retire los datos en claro.")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
