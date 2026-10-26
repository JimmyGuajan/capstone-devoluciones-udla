"""Modelo final de devoluciones y su evaluacion en el periodo de prueba.

El modelo seleccionado es una regresion de Poisson con offset de exposicion:

    E[devoluciones de la marca m en el mes t] = en_riesgo(m, t) x tasa(m)

donde `en_riesgo` son las unidades que cumplen 60 dias en el mes y seguian en el canal al cierre
del anterior, y `tasa(m)` es la proporcion historica que acaba devuelta, estimada con los
`VENTANA` meses anteriores y encogida hacia la tasa global con peso `K` (partial pooling
empirico-bayesiano). Es el estimador de maxima verosimilitud de ese modelo; coincide con el GLM de
statsmodels (correlacion 0,9991) pero se calcula en forma cerrada.

Random Forest y XGBoost se entrenan como comparacion, con las variables del panel y sus rezagos.
Las definiciones de aqui son las mismas que usan los cuadernos 06 y 07.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import modelo as M
from . import panel_modelo as PM
from .config import RAIZ, SEMILLA

VENTANA = 9      # meses de historia para estimar la tasa de cada marca
K = 300          # peso del encogimiento hacia la tasa global, en unidades en riesgo
Z95 = 1.96

INICIO_VALIDACION = pd.Timestamp("2025-07-01")
INICIO_PRUEBA = pd.Timestamp("2026-01-01")

FEATURES = ["marca", "en_riesgo", "r_marca", "dev_lag1", "dev_lag2", "dev_lag3",
            "desp_lag1", "desp_lag2", "dev_mm3", "mes_sin", "mes_cos"]

PARAMS_RF = dict(n_estimators=600, max_depth=8, min_samples_leaf=2,
                 random_state=SEMILLA, n_jobs=-1)
PARAMS_XGB = dict(objective="count:poisson", n_estimators=600, max_depth=4, learning_rate=.05,
                  subsample=.8, colsample_bytree=.8, min_child_weight=3,
                  base_score=1.0, max_delta_step=.7, random_state=SEMILLA,
                  enable_categorical=True, tree_method="hist")

RUTA_MODELO = RAIZ / "modelo" / "modelo_final.json"


# --- Particion temporal ----------------------------------------------------------
def particiones(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Entrenamiento, validacion y prueba, en ese orden cronologico. Sin mezclar."""
    p = panel.sort_values(["marca", "mes"])
    return {"entrenamiento": p[p.mes < INICIO_VALIDACION],
            "validacion": p[(p.mes >= INICIO_VALIDACION) & (p.mes < INICIO_PRUEBA)],
            "entrenamiento+validacion": p[p.mes < INICIO_PRUEBA],
            "prueba": p[p.mes >= INICIO_PRUEBA]}


# --- Metricas --------------------------------------------------------------------
def mape(real, pred) -> float:
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    m = real > 0
    return float(np.mean(np.abs(real[m] - pred[m]) / real[m]) * 100)


def metricas_mensuales(ev: pd.DataFrame, pred) -> dict:
    """Metricas del volumen total de cada mes y WMAPE a nivel marca x mes."""
    a = ev.assign(p=np.asarray(pred, float)).groupby("mes")[["devueltas", "p"]].sum()
    return {"MAPE %": round(mape(a.devueltas, a.p), 1),
            "MAE": round(float(np.abs(a.devueltas - a.p).mean()), 1),
            "RMSE": round(float(np.sqrt(((a.devueltas - a.p) ** 2).mean())), 1),
            "WMAPE": round(float(M.wmape(ev.devueltas, pred)), 4)}


# --- Modelo seleccionado ---------------------------------------------------------
def ajustar_tasas(panel: pd.DataFrame, antes_de: pd.Timestamp,
                  ventana: int = VENTANA, k: int = K) -> dict:
    """Tasa de devolucion por marca usando solo los meses anteriores a `antes_de`."""
    h = panel[(panel.mes < antes_de) & (panel.mes >= antes_de - pd.DateOffset(months=ventana))]
    tasa_global = float(h.devueltas.sum() / max(h.en_riesgo.sum(), 1))
    a = h.groupby("marca")[["devueltas", "en_riesgo"]].sum()
    tasas = (a.devueltas + k * tasa_global) / (a.en_riesgo + k)
    return {"tasa_global": tasa_global, "tasas": {m: float(t) for m, t in tasas.items()},
            "unidades_en_riesgo_historicas": {m: int(v) for m, v in a.en_riesgo.items()}}


def predecir(en_riesgo: pd.DataFrame, tasas: dict) -> pd.DataFrame:
    """Prediccion por marca: unidades en riesgo x tasa. Una marca sin historia usa la global."""
    t = en_riesgo.marca.map(tasas["tasas"]).fillna(tasas["tasa_global"])
    return en_riesgo.assign(tasa=t.to_numpy(), prediccion=en_riesgo.en_riesgo.to_numpy() * t.to_numpy())


def dispersion_phi(real, pred) -> float:
    """Dispersion de Pearson: chi-cuadrado / grados de libertad. Poisson puro daria 1."""
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    return float(((real - pred) ** 2 / pred).sum() / (len(real) - 1))


def intervalo_quasi_poisson(pred, phi: float, z: float = Z95):
    """Intervalo del volumen mensual: pred +- z x raiz(phi x pred)."""
    pred = np.asarray(pred, float)
    s = np.sqrt(phi * pred)
    return np.maximum(pred - z * s, 0), pred + z * s


# --- Comparacion en el periodo de prueba ----------------------------------------
def evaluar_prueba(panel: pd.DataFrame, con_ensambles: bool = True) -> pd.DataFrame:
    """Los tres modelos entrenados hasta dic-2025 y evaluados en ene-sep 2026."""
    p = particiones(panel)
    trv, te = p["entrenamiento+validacion"], p["prueba"]
    pred = {"Tasa de conversión":
            PM.prediccion_tasa_conversion(panel, sorted(te.mes.unique()))
            .set_index(["marca", "mes"]).prediccion.reindex(pd.MultiIndex.from_frame(te[["marca", "mes"]]))
            .to_numpy()}
    if con_ensambles:
        from sklearn.ensemble import RandomForestRegressor
        from xgboost import XGBRegressor
        x1, x2 = M.preparar_X_one_hot(trv, [te], FEATURES)
        pred["Random Forest"] = RandomForestRegressor(**PARAMS_RF).fit(x1, trv.devueltas).predict(x2)
        pred["XGBoost Poisson"] = (XGBRegressor(**PARAMS_XGB)
                                   .fit(M.preparar_X(trv, FEATURES), trv.devueltas)
                                   .predict(M.preparar_X(te, FEATURES)))
    out = pd.DataFrame([{"modelo": n, **metricas_mensuales(te, v)} for n, v in pred.items()])
    out["cumple ≤ 15 %"] = np.where(out["MAPE %"] <= 15, "sí", "no")
    return out.set_index("modelo")


# --- Modelo guardado -------------------------------------------------------------
def guardar_modelo(panel: pd.DataFrame, walkforward: pd.DataFrame | None = None,
                   ruta: Path = RUTA_MODELO) -> dict:
    """Guarda las tasas con las que se predeciria el mes siguiente al ultimo del panel."""
    siguiente = panel.mes.max() + pd.offsets.MonthBegin(1)
    ajuste = ajustar_tasas(panel, siguiente)
    phi = None
    if walkforward is not None:
        w = walkforward[walkforward.modelo == "Tasa de conversión"]
        phi = dispersion_phi(w.real, w.pred)
    doc = {"modelo": "Poisson con offset de exposicion: en_riesgo x tasa(marca)",
           "ventana_meses": VENTANA, "k_encogimiento": K, "nivel_confianza": 0.95,
           "datos_hasta": f"{panel.mes.max():%Y-%m}", "tasas_para_el_mes": f"{siguiente:%Y-%m}",
           "phi_dispersion": None if phi is None else round(phi, 2),
           "intervalo": "pred +- 1.96 * sqrt(phi * pred), sobre el volumen mensual",
           **ajuste}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def cargar_modelo(ruta: Path = RUTA_MODELO) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))
