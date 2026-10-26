"""Demo: predice las devoluciones de un mes, con su intervalo de incertidumbre.

Dos usos:

1. Repetir la prediccion de un mes ya observado, usando solo lo que se sabia antes de ese mes
   (es lo que el modelo habria dicho en su momento), y compararla con lo ocurrido::

       python scripts/predecir.py --mes 2026-09

2. Predecir un mes futuro a partir de las unidades en riesgo de cada marca (las que cumpliran 60
   dias ese mes y siguen en el canal). Se entregan en un CSV con columnas `marca,en_riesgo` y se
   aplican las tasas guardadas en `modelo/modelo_final.json`::

       python scripts/predecir.py --en-riesgo docs/muestra/en_riesgo_2026-10.csv

La demo no necesita los datos del cliente: sin `data/processed/v6_panel_modelo.parquet` usa el panel
de muestra `docs/muestra/panel_modelo_muestra.csv`, que solo trae totales por marca y mes.

El intervalo es del volumen mensual total: prediccion ± 1,96·√(φ·prediccion), con φ = 8,9 medido en
el walk-forward (la varianza real es unas nueve veces la de un Poisson puro).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd

from src import modelo_final as MF
from src.config import PROC

PANEL = PROC / "v6_panel_modelo.parquet"
PANEL_MUESTRA = RAIZ / "docs" / "muestra" / "panel_modelo_muestra.csv"


def cargar_panel(ruta: Path | None) -> pd.DataFrame:
    if ruta is None:
        ruta = PANEL if PANEL.exists() else PANEL_MUESTRA
    print(f"Panel: {ruta.relative_to(RAIZ) if ruta.is_relative_to(RAIZ) else ruta}")
    panel = pd.read_parquet(ruta) if ruta.suffix == ".parquet" else pd.read_csv(ruta, parse_dates=["mes"])
    return panel


def mostrar(tabla: pd.DataFrame, phi: float, real: float | None = None) -> None:
    total = float(tabla.prediccion.sum())
    lo, hi = MF.intervalo_quasi_poisson(total, phi)
    t = tabla[tabla.en_riesgo > 0][["marca", "en_riesgo", "tasa", "prediccion"]].copy()
    t["tasa"] = t.tasa.map("{:.3f}".format)
    t["prediccion"] = t.prediccion.round(1)
    print("\n" + t.to_string(index=False))
    print(f"\n  Prediccion del mes : {total:,.0f} unidades")
    print(f"  Intervalo 95 %     : {float(lo):,.0f} a {float(hi):,.0f}   (φ = {phi})")
    if real is not None:
        print(f"  Lo ocurrido        : {real:,.0f} unidades   "
              f"(error {(total - real) / real * 100:+.1f} %, "
              f"{'dentro' if lo <= real <= hi else 'FUERA'} del intervalo)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--mes", help="mes ya observado a repetir, AAAA-MM")
    g.add_argument("--en-riesgo", type=Path, help="CSV con columnas marca,en_riesgo para un mes futuro")
    ap.add_argument("--panel", type=Path, help="panel alternativo (parquet o csv)")
    ap.add_argument("--modelo", type=Path, default=MF.RUTA_MODELO)
    a = ap.parse_args()

    modelo = MF.cargar_modelo(a.modelo)
    phi = modelo["phi_dispersion"]

    if a.mes:
        panel = cargar_panel(a.panel)
        mes = pd.Timestamp(a.mes + "-01")
        ev = panel[panel.mes == mes]
        if ev.empty:
            print(f"El panel no tiene el mes {a.mes}. Meses disponibles: "
                  f"{panel.mes.min():%Y-%m} a {panel.mes.max():%Y-%m}")
            return 2
        tasas = MF.ajustar_tasas(panel, mes)
        print(f"Mes {a.mes}: tasas estimadas con los {MF.VENTANA} meses anteriores, k={MF.K}")
        mostrar(MF.predecir(ev[["marca", "en_riesgo"]], tasas), phi, real=float(ev.devueltas.sum()))
    else:
        er = pd.read_csv(a.en_riesgo)
        if not {"marca", "en_riesgo"} <= set(er.columns):
            print("El CSV debe tener las columnas marca y en_riesgo.")
            return 2
        print(f"Tasas guardadas: datos hasta {modelo['datos_hasta']}, validas para {modelo['tasas_para_el_mes']}")
        mostrar(MF.predecir(er[["marca", "en_riesgo"]], modelo), phi)
    return 0


if __name__ == "__main__":
    sys.exit(main())
