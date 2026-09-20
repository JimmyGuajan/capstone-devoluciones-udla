"""Baselines, modelos y metricas de evaluacion.

Las metricas siguen la correccion metodologica de la seccion 7.7 del plan: el
MAPE comprometido en el capstone se verifica sobre la agregacion
distribuidor-periodo, porque a grano fino divide por cero; el WMAPE es la
metrica principal y el MASE es el que dice si el modelo aporta algo sobre el
baseline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .config import SEMILLA


# --- Metricas ----------------------------------------------------------------
def wmape(y, yhat) -> float:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    d = np.abs(y).sum()
    return np.abs(y - yhat).sum() / d if d else np.nan


def mape_agregado(df: pd.DataFrame, y: str, yhat: str, por=("ruc", "periodo")) -> float:
    """MAPE al nivel en que el negocio decide, no a grano de celda."""
    g = df.groupby(list(por))[[y, yhat]].sum()
    g = g[g[y] > 0]
    if g.empty:
        return np.nan
    return float((np.abs(g[y] - g[yhat]) / g[y]).mean() * 100)


def mase(y_true, y_pred, y_train) -> float:
    """Error relativo al naive. MASE < 1 significa que el modelo aporta."""
    y_train = np.asarray(y_train, float)
    escala = np.abs(np.diff(y_train)).mean()
    if not escala:
        return np.nan
    return mean_absolute_error(y_true, y_pred) / escala


def sesgo(y, yhat) -> float:
    return float(np.mean(np.asarray(yhat, float) - np.asarray(y, float)))


def pct_subestimacion(y, yhat) -> float:
    """Riesgo asimetrico: subestimar la devolucion genera sobre-stock."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = y > 0
    return float((yhat[m] < y[m]).mean() * 100) if m.any() else np.nan


def evaluar(nombre: str, y, yhat, y_train, df=None, y_col=None) -> dict:
    r = {
        "modelo": nombre,
        "WMAPE": round(wmape(y, yhat), 4),
        "MAE": round(mean_absolute_error(y, yhat), 3),
        "RMSE": round(float(np.sqrt(mean_squared_error(y, yhat))), 3),
        "MASE": round(mase(y, yhat, y_train), 3),
        "sesgo": round(sesgo(y, yhat), 3),
        "pct_subestim": round(pct_subestimacion(y, yhat), 1),
    }
    if df is not None and y_col is not None:
        d = df.copy()
        d["_pred"] = yhat
        r["MAPE_agg_%"] = round(mape_agregado(d, y_col, "_pred"), 1)
    return r


# --- Particion temporal ------------------------------------------------------
def split_temporal(p: pd.DataFrame, col="periodo", n_valid=2, n_test=2):
    """Prohibido el split aleatorio: en pronostico temporal es fuga por diseno."""
    per = np.sort(p[col].unique())
    if len(per) < n_valid + n_test + 2:
        raise ValueError(
            f"Solo hay {len(per)} periodos; se necesitan al menos "
            f"{n_valid + n_test + 2} para una particion temporal honesta.")
    corte_v, corte_t = per[-(n_valid + n_test)], per[-n_test]
    return (p[p[col] < corte_v], p[(p[col] >= corte_v) & (p[col] < corte_t)],
            p[p[col] >= corte_t])


# --- Baselines ---------------------------------------------------------------
def baseline_naive(train: pd.DataFrame, test: pd.DataFrame, y="dev_u") -> np.ndarray:
    """y[t+1] = y[t]. El piso absoluto."""
    ult = (train.sort_values("periodo").groupby(["ruc", "segmento"], observed=True)[y]
                .last())
    idx = pd.MultiIndex.from_frame(test[["ruc", "segmento"]])
    return ult.reindex(idx).fillna(0).to_numpy()


def baseline_media(train: pd.DataFrame, test: pd.DataFrame, y="dev_u") -> np.ndarray:
    m = train.groupby(["ruc", "segmento"], observed=True)[y].mean()
    idx = pd.MultiIndex.from_frame(test[["ruc", "segmento"]])
    return m.reindex(idx).fillna(train[y].mean()).to_numpy()


def baseline_croston(train: pd.DataFrame, test: pd.DataFrame,
                     y="dev_u", alpha=0.1) -> np.ndarray:
    """Croston/SBA: el rival real en demanda intermitente, no el naive."""
    pred = {}
    for k, g in train.sort_values("periodo").groupby(["ruc", "segmento"], observed=True):
        s = g[y].to_numpy()
        nz = np.flatnonzero(s)
        if not len(nz):
            pred[k] = 0.0
            continue
        z = s[nz[0]]
        x = nz[0] + 1
        for i in range(1, len(nz)):
            z = alpha * s[nz[i]] + (1 - alpha) * z
            x = alpha * (nz[i] - nz[i - 1]) + (1 - alpha) * x
        pred[k] = (1 - alpha / 2) * z / x if x else 0.0   # correccion SBA
    return np.array([pred.get((r, s), 0.0)
                     for r, s in zip(test["ruc"], test["segmento"])])


# --- Modelos supervisados ----------------------------------------------------
def preparar_X(p: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Matriz de diseno con las categoricas como dtype 'category'.

    XGBoost las consume nativamente con enable_categorical=True. Random Forest
    no: para el hay que pasar por preparar_X_one_hot.
    """
    X = p[features].copy()
    for c in X.columns:
        if X[c].dtype == object or str(X[c].dtype) in ("string", "category"):
            X[c] = X[c].astype("category")
    return X


def preparar_X_one_hot(train: pd.DataFrame, otros: list[pd.DataFrame],
                       features: list[str]):
    """One-hot alineado entre train y el resto, para modelos sin soporte nativo.

    Las columnas se fijan con el train: una categoria no vista en produccion
    entra como cero, que es el comportamiento deseado.
    """
    cat = [c for c in features
           if train[c].dtype == object or str(train[c].dtype) in ("string", "category")]
    Xtr = pd.get_dummies(train[features], columns=cat, dummy_na=True).fillna(-1)
    salida = [Xtr]
    for o in otros:
        Xo = (pd.get_dummies(o[features], columns=cat, dummy_na=True)
              .reindex(columns=Xtr.columns, fill_value=0).fillna(-1))
        salida.append(Xo)
    return salida


def random_forest(**kw) -> RandomForestRegressor:
    params = dict(n_estimators=400, max_depth=8, min_samples_leaf=3,
                  random_state=SEMILLA, n_jobs=-1)
    params.update(kw)
    return RandomForestRegressor(**params)


def backtest_rodante(p: pd.DataFrame, features: list[str], constructor,
                     y_col="dev_u", min_train=4, one_hot=False) -> pd.DataFrame:
    """Reentrena en cada origen y predice un paso adelante.

    Con pocos periodos, un unico holdout estima el error sobre una muestra
    diminuta. El backtesting de origen rodante usa todos los origenes
    disponibles y es la metrica principal que debe reportarse en ese escenario,
    acompanada de un intervalo de confianza.
    """
    per = np.sort(p["periodo"].unique())
    filas = []
    for i in range(min_train, len(per)):
        tr = p[p["periodo"] < per[i]]
        te = p[p["periodo"] == per[i]]
        if te.empty or tr[y_col].sum() == 0:
            continue
        if one_hot:
            Xtr, Xte = preparar_X_one_hot(tr, [te], features)
        else:
            Xtr, Xte = preparar_X(tr, features), preparar_X(te, features)
        mod = constructor().fit(Xtr, tr[y_col])
        filas.append(pd.DataFrame({
            "periodo": te["periodo"].values, "ruc": te["ruc"].values,
            "segmento": te["segmento"].values,
            "y": te[y_col].values, "yhat": mod.predict(Xte)}))
    return pd.concat(filas, ignore_index=True) if filas else pd.DataFrame()


def ic_bootstrap(y, yhat, n=2000, semilla=SEMILLA):
    """IC del WMAPE por remuestreo. Devuelve NaN si el target es todo cero."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    if np.abs(y).sum() == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(semilla)
    idx = np.arange(len(y))
    vals = []
    for _ in range(n):
        b = rng.choice(idx, len(idx), replace=True)
        v = wmape(y[b], yhat[b])
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return (np.nan, np.nan, np.nan)
    return tuple(np.percentile(vals, [2.5, 50, 97.5]))


def xgboost_poisson(**kw):
    """objective='count:poisson': el default reg:squarederror es inadecuado
    para conteos con exceso de ceros -- produce predicciones negativas y sesga
    hacia la media."""
    from xgboost import XGBRegressor
    # base_score=1.0 es obligatorio: XGBoost 2.x estima el intercepto
    # automaticamente y con Poisson lo hace sobre la escala equivocada, de modo
    # que el modelo devuelve una constante del orden de 1e13. max_delta_step
    # acota el paso de cada arbol, que es la recomendacion de la libreria para
    # este objetivo.
    params = dict(objective="count:poisson", n_estimators=400, max_depth=4,
                  learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                  min_child_weight=5, reg_lambda=1.0, random_state=SEMILLA,
                  base_score=1.0, max_delta_step=0.7,
                  enable_categorical=True, tree_method="hist")
    params.update(kw)
    return XGBRegressor(**params)
