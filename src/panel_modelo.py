"""Construccion del panel marca x mes que alimenta el modelo.

Reune la logica que antes vivia en scripts sueltos fuera del repositorio. Va de los
inventarios y despachos hasta el panel con el grupo en riesgo y las variables
rezagadas, que es la entrada de los cuadernos 06, 07 y 08.

Cadena completa::

    stock + despachos --estadias--> tramos --periodos--> permanencia en canal
                                                   --panel--> marca x mes

Nada aqui depende del valor de los identificadores, solo de que sean iguales entre
inventario y despachos. Por eso el resultado es identico con los datos originales y
con los seudonimizados (ver `scripts/verificar_equivalencia.py`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import ciclo as CI
from . import permanencia as P


def periodos_desde_estadias(estadias: pd.DataFrame, despachos: pd.DataFrame) -> pd.DataFrame:
    """Periodos de permanencia en canal, con su fecha de despacho y de umbral."""
    return P.marcar(P.con_despacho(P.periodo_en_canal(estadias), despachos))


def construir_periodos(stock: pd.DataFrame, despachos: pd.DataFrame) -> pd.DataFrame:
    """Lo mismo, partiendo del inventario diario en lugar de las estadias."""
    return periodos_desde_estadias(CI.estadias(stock), despachos)


def grupo_en_riesgo(validos: pd.DataFrame, meses) -> pd.DataFrame:
    """Unidades que cumplen el umbral en el mes y seguian en el canal al cierre del anterior."""
    filas = []
    marcas = validos.marca.dropna().unique()
    for m in meses:
        cierre_previo = m - pd.Timedelta(days=1)
        fin_mes = m + pd.offsets.MonthEnd(0)
        v = validos[(validos.fecha_umbral >= m) & (validos.fecha_umbral <= fin_mes)]
        r = v[(v.inicio_canal <= cierre_previo) & (v.fin_canal >= cierre_previo)]
        for mk in marcas:
            filas.append({"mes": m, "marca": mk, "en_riesgo": int((r.marca == mk).sum())})
    return pd.DataFrame(filas)


def construir_panel(periodos: pd.DataFrame) -> pd.DataFrame:
    """Panel marca x mes con el grupo en riesgo y las variables rezagadas."""
    validos = periodos[~periodos.sin_despacho]
    flujo = P.flujo_mensual(validos, por=("marca",))
    primer_mes = flujo.mes.min() + pd.offsets.MonthBegin(1)
    riesgo = grupo_en_riesgo(validos, pd.date_range(primer_mes, flujo.mes.max(), freq="MS"))

    d = (flujo.merge(riesgo, on=["marca", "mes"])
              .sort_values(["marca", "mes"]).reset_index(drop=True))
    g = d.groupby("marca", observed=True)
    for lag in (1, 2, 3):
        d[f"dev_lag{lag}"] = g["devueltas"].shift(lag)
    d["desp_lag1"] = g["despachadas"].shift(1)
    d["desp_lag2"] = g["despachadas"].shift(2)
    d["dev_mm3"] = g["devueltas"].shift(1).rolling(3, min_periods=1).mean().values
    d["r_marca"] = ((g["devueltas"].cumsum() - d.devueltas)
                    / (g["en_riesgo"].cumsum() - d.en_riesgo).replace(0, np.nan))
    d["mes_sin"] = np.sin(2 * np.pi * d.mes.dt.month / 12)
    d["mes_cos"] = np.cos(2 * np.pi * d.mes.dt.month / 12)
    return d.dropna(subset=["dev_lag1"]).reset_index(drop=True)


def prediccion_tasa_conversion(panel: pd.DataFrame, meses, ventana: int = 9, k: int = 300) -> pd.DataFrame:
    """Modelo seleccionado: unidades en riesgo x tasa de la marca, reestimada cada mes.

    La tasa usa solo los `ventana` meses anteriores y se encoge hacia la tasa global con
    peso `k`. Devuelve una fila por marca y mes con la prediccion.
    """
    salida = []
    for mes in meses:
        base = panel[panel.mes == mes]
        h = panel[(panel.mes < mes) & (panel.mes >= mes - pd.DateOffset(months=ventana))]
        gl = h.devueltas.sum() / max(h.en_riesgo.sum(), 1)
        a = h.groupby("marca")[["devueltas", "en_riesgo"]].sum()
        tasa = base.marca.map((a.devueltas + k * gl) / (a.en_riesgo + k)).fillna(gl)
        salida.append(base.assign(prediccion=base.en_riesgo.to_numpy() * tasa.to_numpy()))
    return pd.concat(salida, ignore_index=True)
