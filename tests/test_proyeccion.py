"""Pruebas del pronostico de los meses siguientes al ultimo dato. Usan el panel de muestra."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import modelo_final as MF
from src import panel_modelo as PM
from src import proyeccion as PR

EXPOSICION = Path(__file__).resolve().parents[1] / "docs" / "muestra" / "en_riesgo_2026-10.csv"


def _panel_sintetico(razon=0.25, meses=14):
    """Una marca con despachos conocidos y exposicion = razon x despachos de dos meses antes."""
    m = pd.date_range("2025-01-01", periods=meses, freq="MS")
    desp = np.linspace(1000, 1400, meses)
    d = pd.DataFrame({"mes": m, "marca": "A", "despachadas": desp})
    d["desp_lag2"] = d.despachadas.shift(2)
    d["en_riesgo"] = (razon * d.desp_lag2).fillna(0).round(6)
    d["devueltas"] = (0.7 * d.en_riesgo).round(6)
    return d


def test_la_razon_recupera_la_fraccion_que_llega_en_riesgo():
    r = PR.razon_exposicion(_panel_sintetico(0.25), pd.Timestamp("2026-02-01"))
    assert r["A"] == pytest.approx(0.25)


def test_noviembre_es_la_razon_por_los_despachos_del_ultimo_mes():
    panel = _panel_sintetico(0.25)
    cierre = panel.mes.max()
    exposicion = pd.DataFrame({"marca": ["A"], "en_riesgo": [0.25 * panel[panel.mes == cierre - pd.DateOffset(months=1)].despachadas.iloc[0]]})
    p = PR.pronosticar(panel, exposicion).set_index("horizonte")
    assert p.loc[2, "en_riesgo"] == pytest.approx(0.25 * panel[panel.mes == cierre].despachadas.iloc[0])


def test_diciembre_usa_el_promedio_de_tres_meses_y_el_factor_del_usuario():
    panel = _panel_sintetico(0.25)
    cierre = panel.mes.max()
    # exposicion del mes +1 coherente con la razon (0,25 x despachos de dos meses antes): la razon sigue siendo 0,25
    previo = panel[panel.mes == cierre - pd.DateOffset(months=1)].despachadas.iloc[0]
    exposicion = pd.DataFrame({"marca": ["A"], "en_riesgo": [0.25 * previo]})
    promedio = panel[panel.mes > cierre - pd.DateOffset(months=3)].despachadas.mean()
    base = PR.pronosticar(panel, exposicion).set_index("horizonte").loc[3, "en_riesgo"]
    doble = PR.pronosticar(panel, exposicion, factor_despachos=2.0).set_index("horizonte").loc[3, "en_riesgo"]
    assert base == pytest.approx(0.25 * promedio)
    assert doble == pytest.approx(2 * base)


def test_octubre_usa_la_exposicion_observada_tal_cual():
    panel = _panel_sintetico()
    exposicion = pd.DataFrame({"marca": ["A"], "en_riesgo": [321.0]})
    p = PR.pronosticar(panel, exposicion).set_index("horizonte")
    assert p.loc[1, "en_riesgo"] == 321.0 and p.loc[1, "origen"] == "observada"


def test_a_un_mes_el_backtest_es_el_modelo_de_siempre(panel):
    bt = PR.backtest_horizontes(panel)
    uno = bt[bt.horizonte == 1].set_index("mes")
    for mes in uno.index[-5:]:
        esperado = PM.prediccion_tasa_conversion(panel, [mes]).prediccion.sum()
        assert uno.loc[mes, "prediccion"] == pytest.approx(esperado)


def test_el_pronostico_no_mira_nada_posterior_al_cierre(panel):
    """Cambia todo lo que ocurre despues del mes +1 y comprueba que el pronostico no se mueve."""
    cierre = pd.Timestamp("2026-03-01")
    base = PR.backtest_horizontes(panel)
    alterado = panel.copy()
    futuro = alterado.mes >= cierre + pd.DateOffset(months=2)
    alterado.loc[futuro, ["en_riesgo", "devueltas", "despachadas"]] *= 7
    nuevo = PR.backtest_horizontes(alterado)
    for h in (2, 3):
        a = base[(base.cierre == cierre) & (base.horizonte == h)].prediccion.iloc[0]
        b = nuevo[(nuevo.cierre == cierre) & (nuevo.horizonte == h)].prediccion.iloc[0]
        assert a == pytest.approx(b), f"el pronostico a {h} meses depende del futuro"


def test_la_incertidumbre_crece_con_el_horizonte(panel):
    r = PR.resumen_horizontes(PR.backtest_horizontes(panel))
    assert r.mape_medio[1] < r.mape_medio[2] < r.mape_medio[3]
    assert r.loc[1, "mape_medio"] == pytest.approx(5.3, abs=0.1)
    assert (r.cociente_bajo < 1).all() and (r.cociente_alto > 1).all()


def test_la_exposicion_de_octubre_versionada_es_coherente():
    e = pd.read_csv(EXPOSICION)
    assert int(e.en_riesgo.sum()) == 527 and set(e.columns) == {"marca", "en_riesgo"}
    assert (e.en_riesgo > 0).all()
