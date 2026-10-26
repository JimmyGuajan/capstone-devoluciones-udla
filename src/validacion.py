"""Validacion walk-forward (origen rodante) y lineas base.

En cada mes de evaluacion el modelo se reentrena solo con los meses anteriores y predice ese
mes, igual que se haria en produccion. Con el panel actual hay 21 origenes, de ene-2025 a
sep-2026. Es la validacion que sustenta el MAPE medio y su intervalo de confianza.

`walk_forward` produce los cuatro modelos que usa el cuaderno 07 (tasa de conversion, Random
Forest, XGBoost y naive del mes anterior). `lineas_base` anade dos referencias mas simples, en
tabla aparte para no alterar la que consume el cuaderno:

  * Cero              no anticipa ninguna devolucion (el equivalente a no tener metodo);
  * Media movil 3m    el promedio de los tres meses anteriores de cada marca.

Los hiperparametros de Random Forest y XGBoost aqui son los del walk-forward, que **no** son los
de la comparacion en el periodo de prueba (`modelo_final.PARAMS_*`): esa usa 600 arboles y esta 400.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import modelo as M
from . import panel_modelo as PM
from .config import SEMILLA
from .modelo_final import FEATURES

INICIO_WALKFORWARD = pd.Timestamp("2025-01-01")

PARAMS_RF = dict(n_estimators=400, max_depth=8, min_samples_leaf=2,
                 random_state=SEMILLA, n_jobs=-1)
PARAMS_XGB = dict(objective="count:poisson", n_estimators=400, max_depth=4, learning_rate=.05,
                  subsample=.8, colsample_bytree=.8, min_child_weight=3, reg_lambda=1.0,
                  base_score=1.0, max_delta_step=.7, random_state=SEMILLA,
                  enable_categorical=True, tree_method="hist")

MODELOS = ["Tasa de conversión", "Random Forest", "XGBoost Poisson", "Naive (mes anterior)"]
LINEAS_BASE = ["Cero (no anticipa)", "Media móvil 3 meses"]


def _fila(mes, modelo: str, te: pd.DataFrame, pred: np.ndarray, n_train: int) -> dict:
    real = float(te.devueltas.sum())
    total = float(np.sum(pred))
    return {"mes": mes, "modelo": modelo, "real": real, "pred": total, "n_train": n_train,
            "celdas_ae": float(np.abs(te.devueltas.to_numpy() - pred).sum()),
            "ae": abs(real - total), "ape": abs(real - total) / real * 100,
            "mes_s": f"{mes:%Y-%m}"}


def origenes(panel: pd.DataFrame, desde: pd.Timestamp = INICIO_WALKFORWARD) -> list[pd.Timestamp]:
    return sorted(panel[panel.mes >= desde].mes.unique())


def walk_forward(panel: pd.DataFrame, desde: pd.Timestamp = INICIO_WALKFORWARD) -> pd.DataFrame:
    """Un renglon por (mes, modelo): lo real, lo predicho y sus errores."""
    from sklearn.ensemble import RandomForestRegressor
    from xgboost import XGBRegressor

    panel = panel.sort_values(["marca", "mes"]).reset_index(drop=True)
    filas = []
    for mes in origenes(panel, desde):
        tr, te = panel[panel.mes < mes], panel[panel.mes == mes]
        x1, x2 = M.preparar_X_one_hot(tr, [te], FEATURES)
        pred = {
            "Tasa de conversión": PM.prediccion_tasa_conversion(panel, [mes]).prediccion.to_numpy(),
            "Random Forest": RandomForestRegressor(**PARAMS_RF).fit(x1, tr.devueltas).predict(x2),
            "XGBoost Poisson": (XGBRegressor(**PARAMS_XGB).fit(M.preparar_X(tr, FEATURES), tr.devueltas)
                                .predict(M.preparar_X(te, FEATURES))),
            "Naive (mes anterior)": te.dev_lag1.to_numpy(float),
        }
        filas += [_fila(mes, nombre, te, p, len(tr)) for nombre, p in pred.items()]
    return pd.DataFrame(filas)


def lineas_base(panel: pd.DataFrame, desde: pd.Timestamp = INICIO_WALKFORWARD) -> pd.DataFrame:
    """Las dos referencias sencillas, en el mismo formato que `walk_forward`."""
    panel = panel.sort_values(["marca", "mes"]).reset_index(drop=True)
    filas = []
    for mes in origenes(panel, desde):
        te = panel[panel.mes == mes]
        n = int((panel.mes < mes).sum())
        filas.append(_fila(mes, LINEAS_BASE[0], te, np.zeros(len(te)), n))
        filas.append(_fila(mes, LINEAS_BASE[1], te, te.dev_mm3.to_numpy(float), n))
    return pd.DataFrame(filas)


def resumen(w: pd.DataFrame) -> pd.DataFrame:
    """MAPE por modelo a lo largo de los origenes, ordenado de menor a mayor error medio."""
    g = w.groupby("modelo").ape
    r = pd.DataFrame({"MAPE_medio": g.mean(), "mediana": g.median(), "desv": g.std(),
                      "p10": g.quantile(.1), "p90": g.quantile(.9), "peor": g.max(),
                      "MAE": w.groupby("modelo").ae.mean()})
    return r.sort_values("MAPE_medio").round(2)
