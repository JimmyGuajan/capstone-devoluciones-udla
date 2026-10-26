"""Pronostico de octubre, noviembre y diciembre de 2026, con la medicion de su incertidumbre.

Octubre se predice con las unidades en riesgo observadas al 30 de septiembre y lleva el intervalo
quasi-Poisson de siempre. Noviembre y diciembre dependen de despachos que aun no ocurren, asi que
son escenarios: su rango sale de lo que paso al repetir este ejercicio desde cada cierre historico
(`src/proyeccion.py`).

Produce:
  reports/pronostico_horizontes.csv    el backtest: cada pronostico pasado frente a lo ocurrido
  reports/pronostico_oct_dic_2026.csv  el pronostico por mes, con su rango

    python scripts/pronostico_trimestre.py
    python scripts/pronostico_trimestre.py --factor-despachos 0.8     # menos despachos de los esperados
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.modules["bottleneck"] = None

import pandas as pd

from src import modelo_final as MF
from src import proyeccion as PR
from src.config import REPORTES

PANEL = RAIZ / "docs" / "muestra" / "panel_modelo_muestra.csv"
EXPOSICION = RAIZ / "docs" / "muestra" / "en_riesgo_2026-10.csv"


def pronostico_con_rangos(panel: pd.DataFrame, exposicion: pd.DataFrame, factor: float = 1.0):
    modelo = MF.cargar_modelo()
    bt = PR.backtest_horizontes(panel)
    res = PR.resumen_horizontes(bt)
    p = PR.pronosticar(panel, exposicion, factor)
    filas = []
    for h, g in p.groupby("horizonte"):
        total = float(g.prediccion.sum())
        if h == 1:
            lo, hi = (float(x) for x in MF.intervalo_quasi_poisson(total, modelo["phi_dispersion"]))
            metodo = "quasi-Poisson 95 %"
        else:
            lo, hi = total * res.loc[h, "cociente_bajo"], total * res.loc[h, "cociente_alto"]
            metodo = "empirico 80 % (backtest)"
        filas.append({"mes": g.mes.iloc[0], "horizonte": h, "origen": g.origen.iloc[0],
                      "en_riesgo": float(g.en_riesgo.sum()), "prediccion": total, "rango_bajo": lo,
                      "rango_alto": hi, "rango": metodo, "mape_historico": float(res.loc[h, "mape_medio"]),
                      "factor_despachos": factor if h == 3 else None})
    return p, pd.DataFrame(filas), bt, res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--exposicion", type=Path, default=EXPOSICION)
    ap.add_argument("--factor-despachos", type=float, default=1.0)
    a = ap.parse_args()
    panel = pd.read_parquet(a.panel) if a.panel.suffix == ".parquet" else pd.read_csv(a.panel, parse_dates=["mes"])
    exposicion = pd.read_csv(a.exposicion)

    detalle, resumen, bt, res = pronostico_con_rangos(panel, exposicion, a.factor_despachos)
    bt.to_csv(REPORTES / "pronostico_horizontes.csv", index=False)
    resumen.to_csv(REPORTES / "pronostico_oct_dic_2026.csv", index=False)

    print("Backtest por horizonte (cada cierre pasado):")
    print(res.round(2).to_string())
    print("\nPronostico:")
    for r in resumen.itertuples():
        print(f"  {r.mes:%Y-%m}  {r.prediccion:7,.0f} unidades  [{r.rango_bajo:,.0f} a {r.rango_alto:,.0f}]  "
              f"({r.origen}; {r.rango}; MAPE historico del horizonte {r.mape_historico:.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
