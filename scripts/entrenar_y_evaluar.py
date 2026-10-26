"""Paso 5 de la cadena: entrena el modelo final, lo evalua en el periodo de prueba y lo guarda.

Entrena con mayo-2024 a diciembre-2025, evalua con enero a septiembre de 2026 y compara los tres
modelos: tasa de conversion (el seleccionado), Random Forest y XGBoost. Comprueba el resultado
contra lo ya reportado en `reports/metricas_v6.csv` y guarda el modelo final en
`modelo/modelo_final.json` (tasas por marca, ventana, encogimiento y dispersion).

Entradas: `v6_panel_modelo` (lo produce `construir_v6.py`) y `v7_walkforward` (lo produce
`walk_forward.py`; da la dispersion φ del intervalo de prediccion).

Uso::

    python scripts/entrenar_y_evaluar.py
    python scripts/entrenar_y_evaluar.py --sin-ensambles     # solo el modelo seleccionado
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

from src import modelo_final as MF
from src.config import PROC, REPORTES


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sin-ensambles", action="store_true", help="omite Random Forest y XGBoost")
    a = ap.parse_args()
    t0 = time.time()

    panel = pd.read_parquet(PROC / "v6_panel_modelo.parquet")
    p = MF.particiones(panel)
    print(f"Panel: {len(panel)} filas · {panel.mes.nunique()} meses ({panel.mes.min():%Y-%m} a {panel.mes.max():%Y-%m})")
    for nombre in ("entrenamiento", "validacion", "prueba"):
        d = p[nombre]
        print(f"  {nombre:<14} {len(d):>4} filas · {d.mes.min():%Y-%m} a {d.mes.max():%Y-%m}")

    print("\nEvaluacion en el periodo de prueba", flush=True)
    r = MF.evaluar_prueba(panel, con_ensambles=not a.sin_ensambles)
    print(r.to_string())

    ref = REPORTES / "metricas_v6.csv"
    fallos = 0
    if ref.exists():
        previo = pd.read_csv(ref).set_index("modelo")
        print(f"\nFrente a {ref.relative_to(RAIZ)} (lo reportado):")
        for m in r.index:
            for col in ("MAPE %", "MAE", "RMSE", "WMAPE"):
                ok = abs(r.loc[m, col] - previo.loc[m, col]) <= (0.05 if col != "WMAPE" else 0.0005)
                fallos += not ok
                if not ok:
                    print(f"  DIFIERE {m} · {col}: {r.loc[m, col]} frente a {previo.loc[m, col]}")
        print("  todo coincide" if not fallos else f"  {fallos} diferencias")

    wf = PROC / "v7_walkforward.parquet"
    doc = MF.guardar_modelo(panel, pd.read_parquet(wf) if wf.exists() else None)
    print(f"\nModelo guardado en {MF.RUTA_MODELO.relative_to(RAIZ)}")
    print(f"  tasas para {doc['tasas_para_el_mes']} · ventana {doc['ventana_meses']} m · k={doc['k_encogimiento']} · "
          f"φ={doc['phi_dispersion']} · {len(doc['tasas'])} marcas")
    print(f"\n{time.time() - t0:.0f}s")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
