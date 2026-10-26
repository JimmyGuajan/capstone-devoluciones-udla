"""Pruebas de la seudonimizacion. Usan solo datos sintetizados: ningun dato del cliente."""
import numpy as np
import pandas as pd
import pytest

from src import seudonimizar as S

CLAVE_A = bytes.fromhex("11" * 32)
CLAVE_B = bytes.fromhex("22" * 32)


def _imeis(n, semilla=0):
    rng = np.random.default_rng(semilla)
    return pd.Series([str(int(x)) for x in rng.integers(10**14, 10**15, n)])


# --- propiedades del resumen -------------------------------------------------
def test_es_determinista():
    s = pd.Series(["350000000000001", "350000000000002", "350000000000001"])
    t = S.tokenizar(s, CLAVE_A, "IM_")
    assert t[0] == t[2]               # mismo identificador, mismo codigo
    assert t[0] != t[1]               # distinto identificador, distinto codigo


def test_es_inyectivo_sobre_una_muestra_grande():
    s = _imeis(50_000).drop_duplicates()
    t = S.tokenizar(s, CLAVE_A, "IM_")
    assert t.nunique() == len(s)      # sin colisiones: las uniones no se corrompen


def test_otra_clave_da_otros_codigos():
    s = _imeis(100)
    assert (S.tokenizar(s, CLAVE_A, "IM_") != S.tokenizar(s, CLAVE_B, "IM_")).all()


def test_conserva_los_nulos():
    s = pd.Series(["350000000000001", None, np.nan, "350000000000002"])
    t = S.tokenizar(s, CLAVE_A, "IM_")
    assert t.isna().tolist() == [False, True, True, False]


def test_el_codigo_no_se_confunde_con_un_numero_real():
    t = S.tokenizar(_imeis(20_000), CLAVE_A, "IM_")
    assert not t.str.fullmatch(r"\d{10,}").any()
    assert t.str.startswith("IM_").all()
    assert (t.str.len() == 3 + 24).all()


# --- la clave ----------------------------------------------------------------
def test_sin_clave_falla_con_un_mensaje_util(monkeypatch):
    monkeypatch.delenv(S.VARIABLE_CLAVE, raising=False)
    with pytest.raises(RuntimeError, match=S.VARIABLE_CLAVE):
        S.cargar_clave()


def test_rechaza_claves_debiles_o_mal_formadas(monkeypatch):
    monkeypatch.setenv(S.VARIABLE_CLAVE, "abcd")
    with pytest.raises(RuntimeError, match="demasiado corta"):
        S.cargar_clave()
    monkeypatch.setenv(S.VARIABLE_CLAVE, "no-es-hexadecimal")
    with pytest.raises(RuntimeError, match="hexadecimal"):
        S.cargar_clave()


def test_acepta_una_clave_valida(monkeypatch):
    monkeypatch.setenv(S.VARIABLE_CLAVE, "ab" * 32)
    assert S.cargar_clave() == bytes.fromhex("ab" * 32)


# --- tipo de RUC -------------------------------------------------------------
def test_clasifica_el_ruc_por_su_tercer_digito():
    r = pd.Series(["0990000000001",   # 9 -> sociedad privada
                   "1710000000001",   # 1 -> persona natural
                   "1760000000001",   # 6 -> sector publico
                   "1712345678",      # 10 digitos: cedula -> persona natural
                   "123",             # no valido
                   None])
    assert S.ruc_tipo(r).tolist() == ["sociedad_privada", "persona_natural", "sector_publico",
                                      "persona_natural", "desconocido", "desconocido"]


# --- el DataFrame completo ---------------------------------------------------
def _despachos():
    return pd.DataFrame({
        "imei": ["350000000000001", "350000000000002", None],
        "iccid": ["8959300000000000001", None, "8959300000000000003"],
        "ruc": ["0990000000001", "1710000000001", None],
        "destino": ["AE TIENDA UNO", "CAVS CENTRO DOS", "AE TIENDA UNO"],
        "destino_cod": ["AE TIENDA UNO", "CAVS CENTRO DOS", "AE TIENDA UNO"],
        "ciudad": ["QUITO", "GUAYAQUIL", "QUITO"],
        "cantidad": [1, 1, 1],
    })


def test_el_dataframe_queda_sin_identificadores_en_claro():
    s = S.seudonimizar(_despachos(), CLAVE_A)
    assert S.identificadores_en_claro(s) == {}


def test_detecta_identificadores_en_claro():
    assert set(S.identificadores_en_claro(_despachos())) == {"imei", "iccid", "ruc", "destino",
                                                             "destino_cod"}


def test_calcula_ruc_tipo_antes_de_perder_el_dato():
    s = S.seudonimizar(_despachos(), CLAVE_A)
    assert s["ruc_tipo"].tolist() == ["sociedad_privada", "persona_natural", "desconocido"]


def test_conserva_las_columnas_que_no_identifican():
    s = S.seudonimizar(_despachos(), CLAVE_A)
    assert s["ciudad"].tolist() == ["QUITO", "GUAYAQUIL", "QUITO"]
    assert s["cantidad"].tolist() == [1, 1, 1]


def test_no_modifica_el_original():
    original = _despachos()
    S.seudonimizar(original, CLAVE_A)
    assert original["imei"].iloc[0] == "350000000000001"


def test_un_mismo_destino_produce_un_mismo_alias():
    s = S.seudonimizar(_despachos(), CLAVE_A)
    assert s["destino"].iloc[0] == s["destino"].iloc[2]
    assert s["destino"].iloc[0] != s["destino"].iloc[1]


def test_las_uniones_entre_tablas_se_conservan():
    """La propiedad que importa: unir por IMEI da lo mismo antes y despues."""
    despachos = pd.DataFrame({"imei": ["350000000000001", "350000000000002"], "fecha": [1, 2]})
    stock = pd.DataFrame({"imei": ["350000000000002", "350000000000001", "350000000000009"],
                          "bodega": ["A", "B", "C"]})
    antes = despachos.merge(stock, on="imei")
    despues = (S.seudonimizar(despachos, CLAVE_A)
               .merge(S.seudonimizar(stock, CLAVE_A), on="imei"))
    assert len(antes) == len(despues) == 2
    assert sorted(antes["bodega"]) == sorted(despues["bodega"])
