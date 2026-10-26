"""Pruebas de las cifras que alimentan el sitio de defensa.

El generador lee las salidas de los cuadernos en lugar de copiarlas a mano. Estas pruebas fijan lo que
esas lecturas deben dar, y protegen una correccion concreta: el barrido de umbral NO respalda los 60
dias (su F1 maximo esta en 75); el 60 es la regla del negocio.
"""
import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def camino(panel):
    spec = importlib.util.spec_from_file_location("generar_defensa", RAIZ / "scripts" / "generar_defensa.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    exposicion = pd.read_csv(g.EXPOSICION)
    return g.datos_camino(panel, g.datos_comunes(panel, exposicion))


def test_el_barrido_de_umbral_tiene_su_maximo_en_75_dias_no_en_60(camino):
    u = {r["dias"]: r["f1"] for r in camino["umbral"]}
    assert max(u, key=u.get) == 75
    assert u[60] < u[75]
    assert max(r["precision"] for r in camino["umbral"]) < 0.10      # el retorno fisico casi no se observa


def test_ningun_documento_versionado_dice_que_60_maximizo_el_f1():
    texto = ""
    for ruta in [RAIZ / "README.md", RAIZ / "reports" / "html" / "el_camino_hasta_el_modelo.html",
                 *(RAIZ / "scripts" / "defensa").glob("*.html")]:
        texto += ruta.read_text(encoding="utf-8")
    assert not re.search(r"60 maximiz", texto)
    assert not re.search(r"maximiza el estad[ií]stico F1, que result[oó] ser 60", texto)


def test_las_cifras_del_primer_modelo_vienen_del_cuaderno_02(camino):
    mape = {r["modelo"]: r["mape"] for r in camino["v1"]["mape"]}
    assert mape["XGBoost Poisson"] == 28.3 and mape["Random Forest"] == 76.4
    assert len(camino["v1"]["wmape"]) == 7
    assert min(r["v"] for r in camino["v1"]["wmape"]) == pytest.approx(0.4006)


def test_las_definiciones_suman_lo_que_imprime_el_cuaderno_03(camino):
    d = camino["def"]
    assert (d["tot"]["d1"], d["tot"]["d2"]) == (12982, 17914)
    assert len(d["meses"]) == len(d["d1"]) == len(d["d2"]) == len(d["d3"]) == 18


def test_el_contraste_con_el_negocio(camino):
    assert (camino["cont3"]["coinciden"], camino["cont3"]["listado"], camino["cont3"]["nuestro"]) == (799, 801, 1024)
    assert camino["cont3"]["solo_nuestro"] == 225      # la cobertura no es la precision: no se oculta
    assert camino["cont2"]["capturados"] == 308 and camino["cont2"]["listado"] == 367


def test_el_tramo_intacto_son_agosto_y_septiembre(camino):
    assert [(h["mes"], h["error_pct"]) for h in camino["holdout"]] == [("Agosto", -0.9), ("Septiembre", -0.8)]


def test_el_caso_honor_cuadra_con_el_analisis(camino):
    h = camino["honor"]
    assert (h["en_riesgo"], h["u600"], h["resto_unid"]) == (831, 495, 336)
    assert h["real"] == 643 and h["prediccion"] == pytest.approx(492, abs=1)
    assert h["prediccion"] - h["real"] == pytest.approx(-151, abs=1)
    como_el_resto = h["prediccion"] - (h["resto_cumplen"] + h["u600"] * h["resto_tasa"])
    assert como_el_resto == pytest.approx(52, abs=1)
