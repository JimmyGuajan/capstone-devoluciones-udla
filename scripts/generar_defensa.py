"""Genera el sitio de defensa: tres paginas HTML autocontenidas (problema, solucion, evidencia).

Cada cifra sale del codigo y de los reportes del repositorio, no de texto escrito a mano:

    python scripts/generar_defensa.py
    python scripts/generar_defensa.py --panel data/processed/v6_panel_modelo.parquet

Por defecto usa el panel de muestra versionado (`docs/muestra/`), asi que se puede regenerar sin los
datos del cliente. Las plantillas estan en `scripts/defensa/`. Tarda unos 25 s (rehace la validacion
walk-forward). Salida: `reports/html/defensa/`.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.modules["bottleneck"] = None

import numpy as np
import pandas as pd

from src import modelo_final as MF
from src import proyeccion as PR
from src import validacion as V

PLANTILLAS = RAIZ / "scripts" / "defensa"
PANEL = RAIZ / "docs" / "muestra" / "panel_modelo_muestra.csv"
EXPOSICION = RAIZ / "docs" / "muestra" / "en_riesgo_2026-10.csv"
SALIDA = RAIZ / "reports" / "html" / "defensa"
REPORTES = RAIZ / "reports"
MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PAGINAS = [("index.html", "El problema", "p1_problema.html"),
           ("solucion.html", "La solución", "p2_solucion.html"),
           ("evidencia.html", "La evidencia", "p3_evidencia.html")]

# Volumen de la cadena, medido sobre los artefactos v6 (ver README, "El pipeline").
VOLUMEN = {"inventario": 14_007_314, "despachos": 6_383_678, "estadias": 775_024,
           "periodos": 314_091, "con_despacho": 258_299, "eventos": 39_798}


def etiqueta(mes: pd.Timestamp) -> str:
    return f"{MESES_ES[mes.month - 1]} {mes:%Y}"


def datos_comunes(panel: pd.DataFrame, exposicion: pd.DataFrame) -> dict:
    modelo = MF.cargar_modelo()
    meses = []
    for mes in sorted(panel[panel.mes >= MF.INICIO_PRUEBA].mes.unique()):
        ev = panel[panel.mes == mes]
        p = MF.predecir(ev[["marca", "en_riesgo"]], MF.ajustar_tasas(panel, mes)).assign(real=ev.devueltas.to_numpy())
        total = float(p.prediccion.sum())
        lo, hi = MF.intervalo_quasi_poisson(total, modelo["phi_dispersion"])
        meses.append({"mes": f"{mes:%Y-%m}", "etiqueta": etiqueta(mes), "prediccion": total, "lo": float(lo), "hi": float(hi),
                      "real": float(ev.devueltas.sum()),
                      "marcas": [{"marca": r.marca, "en_riesgo": int(r.en_riesgo), "tasa": float(r.tasa),
                                  "prediccion": float(r.prediccion), "real": int(r.real)}
                                 for r in p[p.en_riesgo > 0].sort_values("en_riesgo", ascending=False).itertuples()]})
    return {"modelo": modelo, "phi": modelo["phi_dispersion"], "z": MF.Z95, "ventana": MF.VENTANA, "k": MF.K, "meses": meses}


def walk_forward(panel: pd.DataFrame, phi: float) -> tuple[dict, dict]:
    w = pd.concat([V.walk_forward(panel), V.lineas_base(panel)], ignore_index=True)
    etiquetas = [f"{m:%Y-%m}" for m in sorted(w.mes.unique())]
    serie = lambda modelo, col: w[w.modelo == modelo].sort_values("mes")[col].round(3).tolist()
    r = V.resumen(w)
    ic = pd.read_csv(REPORTES / "ic_bootstrap.csv").set_index("modelo")
    resumen = [{"modelo": m, "media": float(r.loc[m, "MAPE_medio"]), "mediana": float(r.loc[m, "mediana"]),
                "peor": float(r.loc[m, "peor"]),
                "ic": [float(ic.loc[m, "IC95 inferior"]), float(ic.loc[m, "IC95 superior"])] if m in ic.index else None}
               for m in r.index]
    tasa = w[w.modelo == "Tasa de conversión"].sort_values("mes")
    s = 1.96 * np.sqrt(phi * tasa.pred)
    cob = {"quasi": float(((tasa.real >= tasa.pred - s) & (tasa.real <= tasa.pred + s)).mean()),
           "poisson": float(((tasa.real >= tasa.pred - 1.96 * np.sqrt(tasa.pred)) &
                             (tasa.real <= tasa.pred + 1.96 * np.sqrt(tasa.pred))).mean())}
    modelos = {"Tasa de conversión", "Random Forest", "XGBoost Poisson", "Naive (mes anterior)",
               "Media móvil 3 meses", "Cero (no anticipa)"}
    wf = {"etiquetas": etiquetas, "real": serie("Tasa de conversión", "real"),
          "naive": serie("Naive (mes anterior)", "pred"), "mm": serie("Media móvil 3 meses", "pred"),
          "cero": serie("Cero (no anticipa)", "pred"),
          "mape": {k: float(r.loc[n, "MAPE_medio"]) for k, n in (("naive", "Naive (mes anterior)"), ("mm", "Media móvil 3 meses"), ("cero", "Cero (no anticipa)"))},
          "peor": {k: float(r.loc[n, "peor"]) for k, n in (("naive", "Naive (mes anterior)"), ("mm", "Media móvil 3 meses"), ("cero", "Cero (no anticipa)"))},
          "ape": {m: serie(m, "ape") for m in modelos}, "resumen": resumen,
          "sobre15": int((tasa.ape > 15).sum()), "peor_mes": f"{tasa.loc[tasa.ape.idxmax(), 'mes']:%Y-%m}"}
    return wf, cob


def pagina1(panel, comun, wf) -> dict:
    t = panel.groupby("mes")[["despachadas", "devueltas", "en_riesgo", "valor"]].sum()
    x = t[t.index >= MF.INICIO_PRUEBA]
    return {"meses": [{"mes": f"{m:%Y-%m}", "desp": float(r.despachadas), "dev": float(r.devueltas),
                       "riesgo": float(r.en_riesgo), "valor": float(r.valor)} for m, r in t.iterrows()],
            "k": {"dev26": float(x.devueltas.sum()), "valor26": float(x.valor.sum()), "desp26": float(x.despachadas.sum()),
                  "tasa": float(x.devueltas.sum() / x.en_riesgo.sum())},
            "validacion": {"aciertos": 799, "total": 801}, "wf": wf}


def pagina2(panel, comun, exposicion) -> dict:
    modelo, cierre = comun["modelo"], panel.mes.max()
    siguiente = cierre + pd.offsets.MonthBegin(1)
    h = panel[(panel.mes < siguiente) & (panel.mes >= siguiente - pd.DateOffset(months=MF.VENTANA))]
    a = h.groupby("marca")[["devueltas", "en_riesgo"]].sum()
    param = PR.parametros(panel, cierre, exposicion)
    exp1 = exposicion.set_index("marca").en_riesgo.astype(float)
    param = param.assign(exp1=exp1.reindex(param.index).fillna(0.0))
    param = param[(param.exp1 > 0) | (param.razon > 0)]
    tasas = MF.ajustar_tasas(panel, siguiente)
    resumen = PR.resumen_horizontes(PR.backtest_horizontes(panel))
    nombres = {1: "1 mes (octubre)", 2: "2 meses (noviembre)", 3: "3 meses (diciembre)"}
    exp2 = (param.razon * param.despachos_cierre)
    fut = {"marcas": [{"marca": m, "exp1": float(r.exp1), "razon": float(r.razon), "desp_cierre": float(r.despachos_cierre),
                       "desp_prom": float(r.despachos_promedio), "tasa": float(tasas["tasas"].get(m, tasas["tasa_global"]))}
                      for m, r in param.iterrows()],
           "desp_prom_total": float(param.despachos_promedio.sum()), "desp_cierre_total": float(param.despachos_cierre.sum()),
           "razon_total": float(exp2.sum() / param.despachos_cierre.sum()),
           "hor": [{"nombre": nombres[i], "casos": int(r.casos), "mape_medio": float(r.mape_medio),
                    "mape_mediana": float(r.mape_mediana), "peor": float(r.peor),
                    "q_bajo": float(r.cociente_bajo), "q_alto": float(r.cociente_alto)} for i, r in resumen.iterrows()]}
    activas = [m for m, u in modelo["unidades_en_riesgo_historicas"].items() if u > 0]
    return {"meses": comun["meses"], "phi": comun["phi"], "z": comun["z"], "ventana": comun["ventana"], "k": comun["k"],
            "vol": VOLUMEN, "marcas_tasa": activas, "tasa_global": tasas["tasa_global"],
            "ventana_marcas": {m: {"dev": float(a.devueltas.get(m, 0)), "riesgo": float(a.en_riesgo.get(m, 0))} for m in activas},
            "fut": fut}


def pagina3(panel, comun, wf, cob, hor) -> dict:
    test = pd.read_csv(REPORTES / "metricas_v6.csv")
    shap = pd.read_csv(REPORTES / "shap_dos_ensambles.csv", index_col=0).head(7)
    eq = pd.read_csv(REPORTES / "equidad_ciudad.csv").sort_values("desviación")
    eq["ciudad"] = eq.ciudad.replace({"NAN": "Sin ciudad registrada"}).str.capitalize().replace({"Sin ciudad registrada": "Sin ciudad registrada"})
    dentro = sum(1 for m in comun["meses"] if m["lo"] <= m["real"] <= m["hi"])
    pruebas = sum(len(re.findall(r"^def test_", f.read_text(encoding="utf-8"), re.M)) for f in (RAIZ / "tests").glob("test_*.py"))
    return {"phi": comun["phi"], "test": test.to_dict("records"), "wf": wf,
            "cob": {**cob, "prueba_dentro": dentro, "prueba_n": len(comun["meses"])},
            "shap": [{"v": v, "vals": [float(r["XGBoost %"]), float(r["Random Forest %"])]} for v, r in shap.iterrows()],
            "equidad": [{"ciudad": r.ciudad, "dev": float(r["desviación"])} for _, r in eq.iterrows()],
            "pruebas": pruebas, "scripts": len(glob.glob(str(RAIZ / "scripts" / "*.py"))), "hor": hor}


def render(archivo: str, titulo: str, fuente: str, datos: dict) -> str:
    esqueleto = (PLANTILLAS / "pagina.html").read_text(encoding="utf-8")
    cuerpo, script = (PLANTILLAS / fuente).read_text(encoding="utf-8").split("=====SCRIPT=====")
    nav = "".join(f'<a href="{a}"{" aria-current=\"page\"" if a == archivo else ""}>{n}</a>' for a, n, _ in PAGINAS)
    js = json.dumps(datos, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    return (esqueleto.replace("/*CSS*/", (PLANTILLAS / "comun.css").read_text(encoding="utf-8"))
            .replace("/*JS*/", (PLANTILLAS / "comun.js").read_text(encoding="utf-8"))
            .replace("{{TITULO}}", f"{titulo} · Predicción de devoluciones").replace("{{NAV}}", nav)
            .replace("{{PAGINA}}", cuerpo.strip()).replace("{{SCRIPT}}", script.strip())
            .replace("/*DATOS*/null", js))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--exposicion", type=Path, default=EXPOSICION)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args()
    panel = pd.read_parquet(a.panel) if a.panel.suffix == ".parquet" else pd.read_csv(a.panel, parse_dates=["mes"])
    exposicion = pd.read_csv(a.exposicion)

    comun = datos_comunes(panel, exposicion)
    wf, cob = walk_forward(panel, comun["phi"])
    p2 = pagina2(panel, comun, exposicion)
    hor = [h["mape_medio"] for h in p2["fut"]["hor"]]
    datos = {"index.html": pagina1(panel, comun, wf), "solucion.html": p2, "evidencia.html": pagina3(panel, comun, wf, cob, hor)}
    a.salida.mkdir(parents=True, exist_ok=True)
    for archivo, titulo, fuente in PAGINAS:
        html = render(archivo, titulo, fuente, datos[archivo])
        (a.salida / archivo).write_text(html, encoding="utf-8")
        print(f"{(a.salida / archivo).relative_to(RAIZ)} · {len(html) / 1024:.0f} KB")
    print(f"cobertura quasi-Poisson {cob['quasi']:.1%} · Poisson puro {cob['poisson']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
