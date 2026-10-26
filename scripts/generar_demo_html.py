"""Genera la demo en HTML: la prediccion de devoluciones, vista como la veria un usuario.

Usa el mismo codigo que `scripts/predecir.py` (`src/modelo_final.py`), de modo que las cifras de
la pagina son las del modelo. La pagina es autocontenida: no necesita servidor ni conexion.

    python scripts/generar_demo_html.py
    python scripts/generar_demo_html.py --panel data/processed/v6_panel_modelo.parquet

Por defecto lee el panel de muestra versionado (`docs/muestra/`), asi que cualquiera puede
regenerarla sin los datos del cliente.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.modules["bottleneck"] = None

import pandas as pd

from src import modelo_final as MF

PANEL = RAIZ / "docs" / "muestra" / "panel_modelo_muestra.csv"
SALIDA = RAIZ / "reports" / "html" / "demo_prediccion.html"
MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def datos(panel: pd.DataFrame) -> dict:
    modelo = MF.cargar_modelo()
    meses = sorted(panel[panel.mes >= MF.INICIO_PRUEBA].mes.unique())
    salida = []
    for mes in meses:
        tasas = MF.ajustar_tasas(panel, mes)
        ev = panel[panel.mes == mes]
        p = MF.predecir(ev[["marca", "en_riesgo"]], tasas).assign(real=ev.devueltas.to_numpy())
        total = float(p.prediccion.sum())
        lo, hi = MF.intervalo_quasi_poisson(total, modelo["phi_dispersion"])
        real = float(ev.devueltas.sum())
        salida.append({
            "mes": f"{mes:%Y-%m}", "etiqueta": f"{MESES_ES[mes.month - 1]} {mes:%Y}",
            "prediccion": total, "lo": float(lo), "hi": float(hi), "real": real,
            "marcas": [{"marca": r.marca, "en_riesgo": int(r.en_riesgo), "tasa": float(r.tasa),
                        "prediccion": float(r.prediccion), "real": int(r.real)}
                       for r in p[p.en_riesgo > 0].sort_values("en_riesgo", ascending=False).itertuples()]})
    ultimo = panel[panel.mes == panel.mes.max()].set_index("marca").en_riesgo
    con_historia = [m for m, u in modelo["unidades_en_riesgo_historicas"].items() if u > 0]
    return {"phi": modelo["phi_dispersion"], "z": MF.Z95, "ventana": MF.VENTANA, "k": MF.K,
            "meses": salida,
            "modelo": {"datos_hasta": modelo["datos_hasta"], "para_el_mes": modelo["tasas_para_el_mes"],
                       "tasa_global": modelo["tasa_global"],
                       "tasas": {m: modelo["tasas"][m] for m in con_historia}},
            "ejemplo": {m: int(ultimo.get(m, 0)) for m in con_historia},
            "mes_ejemplo": f"{MESES_ES[panel.mes.max().month - 1]} {panel.mes.max():%Y}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args()
    panel = pd.read_parquet(a.panel) if a.panel.suffix == ".parquet" else pd.read_csv(a.panel, parse_dates=["mes"])
    plantilla = (Path(__file__).with_name("demo_plantilla.html")).read_text(encoding="utf-8")
    html = plantilla.replace("/*DATOS*/null", json.dumps(datos(panel), ensure_ascii=False))
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(html, encoding="utf-8")
    print(f"{a.salida.relative_to(RAIZ)} · {len(html) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
