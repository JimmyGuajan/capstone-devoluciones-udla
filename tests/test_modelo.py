"""Pruebas del modelo final: logica, ausencia de fuga y reproduccion de lo reportado.

Usan el panel de muestra versionado (`docs/muestra/`), que son totales por marca y mes: corren en
cualquier equipo, sin los datos del cliente.

Random Forest se compara con tolerancia: el paralelismo no garantiza igualdad bit a bit.
"""
import numpy as np
import pandas as pd
import pytest

from src import modelo_final as MF
from src import panel_modelo as PM
from src import validacion as V


# --- Logica del estimador --------------------------------------------------------
def _historia():
    """Dos marcas: A devuelve el 80 % de lo que tiene en riesgo, B el 20 %."""
    meses = pd.date_range("2025-01-01", periods=6, freq="MS")
    filas = []
    for m in meses:
        filas += [{"mes": m, "marca": "A", "en_riesgo": 100, "devueltas": 80},
                  {"mes": m, "marca": "B", "en_riesgo": 100, "devueltas": 20}]
    return pd.DataFrame(filas)


def test_con_mucha_historia_la_tasa_se_acerca_a_la_de_la_marca():
    t = MF.ajustar_tasas(_historia(), pd.Timestamp("2025-07-01"), ventana=9, k=1)
    assert t["tasas"]["A"] == pytest.approx(0.80, abs=0.01)
    assert t["tasas"]["B"] == pytest.approx(0.20, abs=0.01)


def test_el_encogimiento_acerca_las_tasas_a_la_global():
    flojo = MF.ajustar_tasas(_historia(), pd.Timestamp("2025-07-01"), k=1)
    fuerte = MF.ajustar_tasas(_historia(), pd.Timestamp("2025-07-01"), k=100_000)
    assert abs(fuerte["tasas"]["A"] - fuerte["tasa_global"]) < abs(flojo["tasas"]["A"] - flojo["tasa_global"])
    assert fuerte["tasa_global"] == pytest.approx(0.5)


def test_marca_sin_historia_usa_la_tasa_global():
    t = MF.ajustar_tasas(_historia(), pd.Timestamp("2025-07-01"))
    pred = MF.predecir(pd.DataFrame({"marca": ["A", "NUEVA"], "en_riesgo": [100, 100]}), t)
    assert pred.tasa.iloc[1] == pytest.approx(t["tasa_global"])


def test_la_prediccion_es_unidades_en_riesgo_por_tasa():
    t = MF.ajustar_tasas(_historia(), pd.Timestamp("2025-07-01"))
    pred = MF.predecir(pd.DataFrame({"marca": ["A"], "en_riesgo": [250]}), t)
    assert pred.prediccion.iloc[0] == pytest.approx(250 * t["tasas"]["A"])


def test_la_ventana_descarta_lo_antiguo():
    h = _historia()
    h.loc[h.mes < "2025-03-01", "devueltas"] = 0          # los dos primeros meses, muy distintos
    corta = MF.ajustar_tasas(h, pd.Timestamp("2025-07-01"), ventana=3, k=1)
    larga = MF.ajustar_tasas(h, pd.Timestamp("2025-07-01"), ventana=9, k=1)
    assert corta["tasas"]["A"] > larga["tasas"]["A"]


# --- Sin fuga de informacion -----------------------------------------------------
def test_las_tasas_no_miran_el_mes_que_se_predice_ni_el_futuro():
    h = _historia()
    mes = pd.Timestamp("2025-04-01")
    antes = MF.ajustar_tasas(h, mes)
    alterada = h.copy()
    alterada.loc[alterada.mes >= mes, ["devueltas", "en_riesgo"]] = 10_000
    assert MF.ajustar_tasas(alterada, mes) == antes


def test_los_rezagos_del_panel_son_exactamente_los_meses_anteriores(panel):
    base = panel.set_index(["marca", "mes"])
    marcas = base.index.get_level_values("marca")
    meses = base.index.get_level_values("mes")
    for lag, col, fuente in ((1, "dev_lag1", "devueltas"), (2, "dev_lag2", "devueltas"),
                             (3, "dev_lag3", "devueltas"), (1, "desp_lag1", "despachadas"),
                             (2, "desp_lag2", "despachadas")):
        previo = pd.MultiIndex.from_arrays([marcas, meses - pd.DateOffset(months=lag)])
        esperado = base[fuente].reindex(previo).to_numpy()
        comparables = ~np.isnan(esperado)
        assert comparables.sum() > 150
        assert np.allclose(base[col].to_numpy()[comparables], esperado[comparables]), col


def test_ninguna_variable_es_el_objetivo_del_mes(panel):
    """El objetivo `devueltas` no puede estar entre las variables ni coincidir con ninguna."""
    assert "devueltas" not in MF.FEATURES
    for c in MF.FEATURES:
        if c != "marca":
            assert not np.allclose(panel[c], panel.devueltas), f"{c} reproduce el objetivo"


def _periodos_sinteticos():
    """Dos marcas, diez meses de despachos, permanencias aleatorias. Sin datos reales."""
    rng = np.random.default_rng(7)
    filas = []
    for marca in ("A", "B"):
        for mes in pd.date_range("2025-01-01", periods=10, freq="MS"):
            for i in range(60):
                desp = mes + pd.Timedelta(days=int(rng.integers(0, 28)))
                inicio = desp + pd.Timedelta(days=int(rng.integers(0, 3)))
                filas.append({"imei": f"{marca}{mes:%y%m}{i}", "marca": marca, "sin_despacho": False,
                              "fecha_despacho": desp, "inicio_canal": inicio,
                              "fin_canal": inicio + pd.Timedelta(days=int(rng.integers(5, 120))),
                              "precio_despacho": 100.0})
    from src import permanencia as P
    return P.marcar(pd.DataFrame(filas))


def test_el_desenlace_de_un_mes_no_altera_las_variables_de_ese_mes_ni_las_anteriores():
    """Prueba de no-fuga sobre el codigo real: cambia lo que ocurre en el ultimo mes y comprueba
    que ninguna variable explicativa de ese mes ni de los anteriores se mueve."""
    base = _periodos_sinteticos()
    ultimo = base.loc[base.cumple, "mes_umbral"].max()
    afectadas = base.index[(base.mes_umbral == ultimo) & base.cumple]
    assert len(afectadas) >= 4
    alterado = base.copy()
    alterado.loc[afectadas[::2], "cumple"] = False        # la mitad deja de contar como devuelta

    a, b = PM.construir_panel(base), PM.construir_panel(alterado)
    explicativas = ["en_riesgo", "dev_lag1", "dev_lag2", "dev_lag3", "desp_lag1", "desp_lag2",
                    "dev_mm3", "r_marca", "mes_sin", "mes_cos"]
    pd.testing.assert_frame_equal(a[a.mes < ultimo].reset_index(drop=True),
                                  b[b.mes < ultimo].reset_index(drop=True))
    ua, ub = a[a.mes == ultimo].reset_index(drop=True), b[b.mes == ultimo].reset_index(drop=True)
    pd.testing.assert_frame_equal(ua[explicativas], ub[explicativas])
    assert (ua.devueltas != ub.devueltas).any()           # el objetivo si cambio: la prueba es efectiva


def test_la_particion_es_cronologica_y_sin_solapamiento(panel):
    p = MF.particiones(panel)
    assert p["entrenamiento"].mes.max() < p["validacion"].mes.min()
    assert p["validacion"].mes.max() < p["prueba"].mes.min()
    assert len(p["entrenamiento"]) + len(p["validacion"]) + len(p["prueba"]) == len(panel)
    assert (len(p["entrenamiento"]), len(p["validacion"]), len(p["prueba"])) == (154, 66, 99)


# --- Intervalo -------------------------------------------------------------------
def test_intervalo_contiene_la_prediccion_y_crece_con_phi():
    lo1, hi1 = MF.intervalo_quasi_poisson(1000, 1.0)
    lo9, hi9 = MF.intervalo_quasi_poisson(1000, 9.0)
    assert lo1 < 1000 < hi1 and lo9 < 1000 < hi9
    assert (hi9 - lo9) == pytest.approx(3 * (hi1 - lo1))      # sqrt(9) = 3


def test_phi_vale_uno_para_datos_poisson_exactos():
    pred = np.array([100.0, 200.0, 300.0, 400.0])
    assert MF.dispersion_phi(pred, pred) == 0.0
    assert MF.dispersion_phi(pred + np.sqrt(pred), pred) == pytest.approx(4 / 3)


# --- Coherencia entre implementaciones ------------------------------------------
def test_la_funcion_del_panel_y_la_del_modelo_dan_lo_mismo(panel):
    meses = sorted(panel[panel.mes >= "2026-01-01"].mes.unique())
    a = PM.prediccion_tasa_conversion(panel, meses)
    for mes in meses:
        t = MF.ajustar_tasas(panel, mes)
        b = MF.predecir(panel[panel.mes == mes][["marca", "en_riesgo"]], t)
        assert np.allclose(a[a.mes == mes].prediccion.to_numpy(), b.prediccion.to_numpy())


# --- Reproduce lo reportado ------------------------------------------------------
def test_reproduce_el_mape_del_periodo_de_prueba(panel):
    r = MF.evaluar_prueba(panel, con_ensambles=False).loc["Tasa de conversión"]
    assert (r["MAPE %"], r["MAE"], r["RMSE"], r["WMAPE"]) == (4.1, 41.0, 69.9, 0.1161)


def test_reproduce_la_comparacion_con_los_ensambles(panel):
    r = MF.evaluar_prueba(panel)
    assert r.loc["Random Forest", "MAPE %"] == pytest.approx(5.2, abs=0.05)
    assert r.loc["XGBoost Poisson", "MAPE %"] == pytest.approx(9.5, abs=0.05)
    assert r["MAPE %"].idxmin() == "Tasa de conversión"
    assert (r["MAPE %"] <= 15).all()


def test_walk_forward_reproduce_el_mape_medio_y_el_orden_de_los_modelos(panel):
    w = V.walk_forward(panel)
    assert w.mes.nunique() == 21 and w.modelo.nunique() == 4
    r = V.resumen(pd.concat([w, V.lineas_base(panel)], ignore_index=True))
    assert r.loc["Tasa de conversión", "MAPE_medio"] == pytest.approx(5.26, abs=0.005)
    assert r.loc["Tasa de conversión", "peor"] == pytest.approx(17.52, abs=0.005)
    assert r.index[0] == "Tasa de conversión"                    # el menor error medio
    assert r.loc["Cero (no anticipa)", "MAPE_medio"] == 100.0
    assert r.loc["Tasa de conversión", "MAPE_medio"] < r.loc["Media móvil 3 meses", "MAPE_medio"] / 5


def test_el_modelo_guardado_corresponde_a_los_datos(panel):
    guardado = MF.cargar_modelo()
    t = MF.ajustar_tasas(panel, panel.mes.max() + pd.offsets.MonthBegin(1))
    assert guardado["tasas"] == pytest.approx(t["tasas"])
    assert guardado["tasa_global"] == pytest.approx(t["tasa_global"])
    assert guardado["ventana_meses"] == MF.VENTANA and guardado["k_encogimiento"] == MF.K
    assert guardado["phi_dispersion"] == pytest.approx(8.9, abs=0.05)
