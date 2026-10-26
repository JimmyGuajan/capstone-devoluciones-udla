"""Unidades en riesgo del mes siguiente al ultimo dato, observadas al ultimo cierre.

Son las unidades que cumpliran 60 dias desde su despacho dentro del mes siguiente y que siguen en
el canal al cierre del ultimo mes con datos. Es lo unico que el modelo necesita para predecir ese
mes, y ya se conoce: no depende de nada que no haya ocurrido.

Requiere `data/processed/v6_periodos.parquet` (lo produce `construir_v6.py`). Guarda solo totales
por marca, sin ningun identificador, en `docs/muestra/`.

    python scripts/exposicion_siguiente.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd

from src import panel_modelo as PM
from src.config import PROC


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--salida", type=Path, default=None)
    a = ap.parse_args()

    panel = pd.read_parquet(PROC / "v6_panel_modelo.parquet", columns=["mes", "marca", "en_riesgo"])
    periodos = pd.read_parquet(PROC / "v6_periodos.parquet")
    validos = periodos[~periodos.sin_despacho]
    siguiente = panel.mes.max() + pd.offsets.MonthBegin(1)

    # control: el mismo calculo sobre el ultimo mes del panel debe reproducir su en_riesgo
    ultimo = panel.mes.max()
    control = PM.grupo_en_riesgo(validos, [ultimo]).set_index("marca").en_riesgo
    esperado = panel[panel.mes == ultimo].set_index("marca").en_riesgo
    assert (control.reindex(esperado.index).fillna(0) == esperado).all(), "el recalculo no coincide con el panel"
    print(f"Control: el recalculo de {ultimo:%Y-%m} coincide con el panel ({int(esperado.sum()):,} unidades)")

    r = PM.grupo_en_riesgo(validos, [siguiente])
    r = r[r.en_riesgo > 0].sort_values("en_riesgo", ascending=False)[["marca", "en_riesgo"]]
    salida = a.salida or RAIZ / "docs" / "muestra" / f"en_riesgo_{siguiente:%Y-%m}.csv"
    r.to_csv(salida, index=False)
    desp = validos[validos.fecha_umbral.dt.to_period("M") == siguiente.to_period("M")].fecha_despacho
    print(f"{siguiente:%Y-%m}: {int(r.en_riesgo.sum()):,} unidades en riesgo "
          f"(despachadas del {desp.min():%d-%b} al {desp.max():%d-%b}) -> {salida.relative_to(RAIZ)}")
    print(r.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
