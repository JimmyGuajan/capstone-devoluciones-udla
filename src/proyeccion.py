"""Pronostico de los meses siguientes al ultimo dato: octubre, noviembre y diciembre de 2026.

El modelo es `en_riesgo x tasa(marca)`. La tasa se conoce al cierre del ultimo mes con datos. Lo que
cambia con el horizonte es de donde sale `en_riesgo`, las unidades que cumpliran 60 dias en el mes
y siguen en el canal al cierre del mes anterior:

  mes +1 (octubre)    se OBSERVA: son las unidades que ya estan en el canal al ultimo cierre.
  mes +2 (noviembre)  se PROYECTA: despachadas dos meses antes (ya conocidas) x la fraccion que
                      historicamente sigue en el canal al llegar a los 60 dias.
  mes +3 (diciembre)  se PROYECTA con un SUPUESTO: depende de despachos que aun no ocurren; se toma
                      el promedio de los ultimos tres meses y el usuario puede cambiarlo.

Por eso la precision cae con el horizonte. `backtest_horizontes` lo mide con el historico: repite el
ejercicio desde cada cierre pasado y compara con lo que ocurrio. Esa medicion es la que justifica los
rangos que se muestran, no un supuesto.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import modelo_final as MF

VENTANA_RAZON = 9
HORIZONTES = {1: "observada", 2: "proyectada", 3: "proyectada con supuesto de despachos"}
INICIO_BACKTEST = pd.Timestamp("2025-03-01")


def _mas(mes: pd.Timestamp, n: int) -> pd.Timestamp:
    return mes + pd.DateOffset(months=n)


def razon_exposicion(panel: pd.DataFrame, hasta: pd.Timestamp, ventana: int = VENTANA_RAZON) -> pd.Series:
    """Fraccion de lo despachado dos meses antes que llega en riesgo al mes, por marca.

    `en_riesgo(t) / despachadas(t-2)`, acumulada sobre los `ventana` meses que terminan en `hasta`.
    """
    h = panel[(panel.mes <= hasta) & (panel.mes > _mas(hasta, -ventana)) & panel.desp_lag2.notna()]
    a = h.groupby("marca")[["en_riesgo", "desp_lag2"]].sum()
    return (a.en_riesgo / a.desp_lag2.replace(0, np.nan)).fillna(0.0)


def _exposicion(panel: pd.DataFrame, cierre: pd.Timestamp, horizonte: int, exposicion_siguiente=None,
                factor_despachos: float = 1.0) -> pd.Series:
    """Unidades en riesgo por marca del mes `cierre + horizonte`, segun el horizonte."""
    siguiente = _mas(cierre, 1)
    if horizonte == 1:
        if exposicion_siguiente is not None:
            return exposicion_siguiente.set_index("marca").en_riesgo.astype(float)
        return panel[panel.mes == siguiente].set_index("marca").en_riesgo.astype(float)

    p = parametros(panel, cierre, exposicion_siguiente)
    despachos = p.despachos_cierre if horizonte == 2 else p.despachos_promedio * factor_despachos
    return p.razon * despachos


def parametros(panel: pd.DataFrame, cierre: pd.Timestamp, exposicion_siguiente=None) -> pd.DataFrame:
    """Por marca: razon de exposicion, despachos del ultimo mes y promedio de los ultimos tres.

    Con eso, noviembre = razon x despachos del ultimo mes y diciembre = razon x promedio x factor.
    """
    siguiente = _mas(cierre, 1)
    base = panel
    if exposicion_siguiente is not None:       # el mes +1 aun no esta en el panel: se agrega para la razon
        desp = panel[panel.mes == _mas(cierre, -1)].set_index("marca").despachadas
        ext = exposicion_siguiente.assign(mes=siguiente,
                                          desp_lag2=lambda d: d.marca.map(desp).to_numpy())
        base = pd.concat([panel, ext[["mes", "marca", "en_riesgo", "desp_lag2"]]], ignore_index=True)
    razon = razon_exposicion(base, siguiente)
    ultimo = panel[panel.mes == cierre].set_index("marca").despachadas
    prom = panel[(panel.mes <= cierre) & (panel.mes > _mas(cierre, -3))].groupby("marca").despachadas.mean()
    return pd.DataFrame({"razon": razon, "despachos_cierre": ultimo.reindex(razon.index).fillna(0.0),
                         "despachos_promedio": prom.reindex(razon.index).fillna(0.0)})


def pronosticar(panel: pd.DataFrame, exposicion_siguiente: pd.DataFrame | None = None,
                factor_despachos: float = 1.0) -> pd.DataFrame:
    """Octubre, noviembre y diciembre por marca: unidades en riesgo, tasa, prediccion y su origen.

    `exposicion_siguiente`: columnas `marca,en_riesgo` del mes +1, observadas al ultimo cierre.
    `factor_despachos`: multiplica el supuesto de despachos del mes +2 (1,0 = promedio de 3 meses).
    """
    cierre = panel.mes.max()
    tasas = MF.ajustar_tasas(panel, _mas(cierre, 1))
    filas = []
    for h in (1, 2, 3):
        exp = _exposicion(panel, cierre, h, exposicion_siguiente, factor_despachos)
        for marca, e in exp.items():
            t = tasas["tasas"].get(marca, tasas["tasa_global"])
            filas.append({"mes": _mas(cierre, h), "horizonte": h, "origen": HORIZONTES[h], "marca": marca,
                          "en_riesgo": float(e), "tasa": float(t), "prediccion": float(e * t)})
    return pd.DataFrame(filas)


def backtest_horizontes(panel: pd.DataFrame, desde: pd.Timestamp = INICIO_BACKTEST) -> pd.DataFrame:
    """Repite el pronostico a 1, 2 y 3 meses desde cada cierre pasado y lo compara con lo ocurrido."""
    panel = panel.sort_values(["marca", "mes"]).reset_index(drop=True)
    ultimo = panel.mes.max()
    filas = []
    for h in (1, 2, 3):
        for cierre in sorted(m for m in panel.mes.unique() if m >= desde):
            objetivo = _mas(cierre, h)
            if objetivo > ultimo:
                continue
            # al cierre se conoce la exposicion del mes +1 (no sus devoluciones); nada posterior
            visible = panel[panel.mes <= _mas(cierre, 1)]
            tasas = MF.ajustar_tasas(panel, _mas(cierre, 1))
            exp = _exposicion(visible, cierre, h)
            ev = panel[panel.mes == objetivo].set_index("marca")
            exp = exp.reindex(ev.index).fillna(0.0)
            tasa = pd.Series({m: tasas["tasas"].get(m, tasas["tasa_global"]) for m in ev.index})
            filas.append({"cierre": cierre, "horizonte": h, "mes": objetivo,
                          "exposicion_real": float(ev.en_riesgo.sum()), "exposicion_proyectada": float(exp.sum()),
                          "prediccion": float((exp * tasa).sum()), "real": float(ev.devueltas.sum())})
    b = pd.DataFrame(filas)
    b["ape"] = (b.prediccion - b.real).abs() / b.real * 100
    return b


def resumen_horizontes(bt: pd.DataFrame, bandas=(0.1, 0.9)) -> pd.DataFrame:
    """MAPE por horizonte y rango empirico: cociente real / prediccion en los casos historicos."""
    filas = []
    for h, g in bt.groupby("horizonte"):
        cociente = g.real / g.prediccion
        filas.append({"horizonte": h, "casos": len(g), "mape_medio": g.ape.mean(), "mape_mediana": g.ape.median(),
                      "peor": g.ape.max(), "cociente_bajo": cociente.quantile(bandas[0]),
                      "cociente_mediano": cociente.median(), "cociente_alto": cociente.quantile(bandas[1])})
    return pd.DataFrame(filas).set_index("horizonte")
