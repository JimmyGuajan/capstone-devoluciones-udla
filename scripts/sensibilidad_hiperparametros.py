"""Sensibilidad del modelo de tasa a la ventana W y al encogimiento k, medida sobre VALIDACION.

El modelo estima la tasa de cada marca con los W meses anteriores y la encoge hacia la tasa global con
peso k. Aqui se barre una rejilla (W, k) y se mide el error sobre julio-diciembre de 2025, que es el
conjunto sobre el que se eligio el modelo. La prueba (2026) no interviene.

Produce `reports/sensibilidad_wk.csv`. Usa el panel de muestra versionado, asi que corre sin los datos
del cliente.

    python scripts/sensibilidad_hiperparametros.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.modules["bottleneck"] = None

import pandas as pd

from src import modelo_final as MF
from src import panel_modelo as PM

VENTANAS = (3, 6, 9, 12)
PESOS = (0, 100, 300, 1000, 3000)


def barrido(panel: pd.DataFrame) -> pd.DataFrame:
    meses = sorted(panel[(panel.mes >= MF.INICIO_VALIDACION) & (panel.mes < MF.INICIO_PRUEBA)].mes.unique())
    filas = []
    for w in VENTANAS:
        for k in PESOS:
            pr = PM.prediccion_tasa_conversion(panel, meses, ventana=w, k=k)
            a = pr.groupby("mes")[["devueltas", "prediccion"]].sum()
            filas.append({"W": w, "k": k,
                          "MAPE_mensual_%": round(float((abs(a.devueltas - a.prediccion) / a.devueltas).mean() * 100), 2),
                          "WMAPE_marca_mes": round(float(abs(pr.devueltas - pr.prediccion).sum() / pr.devueltas.sum()), 3),
                          "sesgo_%": round(float((a.prediccion.sum() - a.devueltas.sum()) / a.devueltas.sum() * 100), 1)})
    return pd.DataFrame(filas)


def main() -> int:
    panel = pd.read_csv(RAIZ / "docs" / "muestra" / "panel_modelo_muestra.csv", parse_dates=["mes"])
    d = barrido(panel)
    d.to_csv(RAIZ / "reports" / "sensibilidad_wk.csv", index=False)
    for col in ("MAPE_mensual_%", "WMAPE_marca_mes", "sesgo_%"):
        print(f"\n{col}\n{d.pivot(index='W', columns='k', values=col).to_string()}")
    elegido = d[(d.W == MF.VENTANA) & (d.k == MF.K)].iloc[0]
    print(f"\nElegido (W={MF.VENTANA}, k={MF.K}): MAPE {elegido['MAPE_mensual_%']} % · WMAPE {elegido['WMAPE_marca_mes']}")
    print(f"Mejor MAPE mensual: {d.loc[d['MAPE_mensual_%'].idxmin()].to_dict()}")
    print(f"Mejor WMAPE:        {d.loc[d['WMAPE_marca_mes'].idxmin()].to_dict()}")
    print(f"Todas cumplen <= 15 %: {bool((d['MAPE_mensual_%'] <= 15).all())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
