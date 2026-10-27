"""Seudonimizacion de identificadores (LOPDP).

Sustituye cada identificador por un codigo que no se puede traducir de vuelta sin
una clave guardada aparte. Es **determinista**: el mismo identificador produce
siempre el mismo codigo, de modo que las uniones entre inventario y despachos y el
calculo de permanencia por equipo dan exactamente el mismo resultado que con los
valores originales.

Que se transforma
-----------------
Claves de union, que se convierten en un codigo hexadecimal con prefijo:

    imei   -> IM_<24 hex>        iccid  -> IC_<24 hex>
    serie  -> SE_<24 hex>        ruc    -> RU_<24 hex>

Identidad comercial, que se convierte en un alias corto:

    destino, destino_cod -> DEST_<8 hex>

El prefijo hace imposible confundir un codigo con un numero real: un IMEI tiene 15
digitos y un codigo empieza siempre por letras.

Antes de transformar el RUC se calcula `ruc_tipo` (persona natural, sociedad
privada, sector publico), porque el tercer digito del RUC se pierde al aplicar el
resumen y es un dato analiticamente util que no identifica a nadie.

Por que HMAC y no un hash simple
--------------------------------
Un IMEI tiene estructura conocida y un espacio de busqueda pequeno: con un hash
simple bastaria probar combinaciones para recuperar los reales. Con HMAC-SHA256 y
una clave secreta eso deja de ser factible.

La clave NO vive en el repositorio. Se lee de la variable de entorno
`PRY_CLAVE_SEUDONIMIZACION` (32 bytes o mas, en hexadecimal). Quien tenga la clave
puede reconstruir la correspondencia, asi que el resultado sigue siendo dato
personal protegido; lo que se gana es que un archivo extraviado no revele a quien
pertenece cada dato.
"""
from __future__ import annotations

import hashlib
import hmac
import os

import numpy as np
import pandas as pd

VARIABLE_CLAVE = "PRY_CLAVE_SEUDONIMIZACION"
MIN_BYTES_CLAVE = 16

# columna -> (prefijo, largo en hexadecimal)
COLUMNAS_TOKEN = {
    "imei": ("IM_", 24),
    "iccid": ("IC_", 24),
    "serie": ("SE_", 24),
    "ruc": ("RU_", 24),
}
COLUMNAS_ALIAS = {
    "destino": ("DEST_", 8),
    "destino_cod": ("DEST_", 8),
}


def cargar_clave() -> bytes:
    """Lee la clave del entorno. Falla de forma explicita si falta o es debil."""
    v = os.environ.get(VARIABLE_CLAVE, "").strip()
    if not v:
        raise RuntimeError(
            f"Falta la clave de seudonimizacion. Defina la variable {VARIABLE_CLAVE} "
            "con 32 bytes en hexadecimal. Para generar una: "
            "python -c \"import secrets; print(secrets.token_hex(32))\". "
            "Guardela fuera del repositorio y de las carpetas sincronizadas.")
    try:
        clave = bytes.fromhex(v)
    except ValueError as e:
        raise RuntimeError(f"{VARIABLE_CLAVE} debe estar en hexadecimal.") from e
    if len(clave) < MIN_BYTES_CLAVE:
        raise RuntimeError(
            f"{VARIABLE_CLAVE} es demasiado corta: {len(clave)} bytes, "
            f"minimo {MIN_BYTES_CLAVE}.")
    return clave


def _resumen(texto: str, clave: bytes) -> str:
    return hmac.new(clave, texto.encode("utf-8"), hashlib.sha256).hexdigest()


def tokenizar(serie: pd.Series, clave: bytes, prefijo: str = "", largo: int = 24) -> pd.Series:
    """Aplica HMAC-SHA256 a cada valor distinto. Los nulos se conservan como nulos."""
    codigos, unicos = pd.factorize(serie.astype("object"), use_na_sentinel=True)
    if len(unicos) == 0:
        return pd.Series([None] * len(serie), index=serie.index, dtype="object")
    tabla = np.array([prefijo + _resumen(str(u), clave)[:largo] for u in unicos], dtype=object)
    salida = np.where(codigos >= 0, tabla[np.clip(codigos, 0, None)], None)
    return pd.Series(salida, index=serie.index, dtype="object")


def ruc_tipo(ruc: pd.Series) -> pd.Series:
    """Clasifica el RUC por su tercer digito (regla del SRI). Calcular ANTES de tokenizar.

    - 13 digitos, tercer digito 0-5  -> persona_natural
    - 13 digitos, tercer digito 6    -> sector_publico
    - 13 digitos, tercer digito 9    -> sociedad_privada
    - 10 digitos (cedula)            -> persona_natural
    - cualquier otro caso            -> desconocido

    Los RUC que pasaron por una hoja de calculo como numero pierden el cero inicial y quedan de 12
    digitos; se les repone antes de clasificar (en los cupos de distribuidores son 22 de 44).
    """
    s = ruc.astype("object").map(lambda v: None if v is None or pd.isna(v) else str(v))
    s = s.map(lambda v: "0" + v if isinstance(v, str) and v.isdigit() and len(v) == 12 else v)
    tipo = pd.Series("desconocido", index=s.index, dtype="object")
    t13 = s.map(lambda v: isinstance(v, str) and v.isdigit() and len(v) == 13)
    t10 = s.map(lambda v: isinstance(v, str) and v.isdigit() and len(v) == 10)
    tercero = s.map(lambda v: v[2] if isinstance(v, str) and len(v) >= 3 else "")
    tipo[t13 & tercero.isin(list("012345"))] = "persona_natural"
    tipo[t13 & (tercero == "6")] = "sector_publico"
    tipo[t13 & (tercero == "9")] = "sociedad_privada"
    tipo[t10] = "persona_natural"
    return tipo


def seudonimizar(df: pd.DataFrame, clave: bytes | None = None) -> pd.DataFrame:
    """Devuelve una copia con los identificadores sustituidos. No modifica el original."""
    clave = clave if clave is not None else cargar_clave()
    out = df.copy()
    if "ruc" in out.columns and "ruc_tipo" not in out.columns:
        out["ruc_tipo"] = ruc_tipo(out["ruc"])
    for col, (prefijo, largo) in COLUMNAS_TOKEN.items():
        if col in out.columns:
            out[col] = tokenizar(out[col], clave, prefijo, largo)
    for col, (prefijo, largo) in COLUMNAS_ALIAS.items():
        if col in out.columns:
            out[col] = tokenizar(out[col], clave, prefijo, largo)
    return out


def identificadores_en_claro(df: pd.DataFrame) -> dict[str, int]:
    """Cuenta, por columna, los valores que aun parecen un identificador sin tratar.

    Una clave de union en claro es un numero de 10 digitos o mas; un destino en
    claro es cualquier texto que no empiece por el prefijo del alias. Devuelve solo
    las columnas con incidencias, de modo que un diccionario vacio significa limpio.
    """
    hallazgos: dict[str, int] = {}
    for col, (prefijo, _) in COLUMNAS_TOKEN.items():
        if col in df.columns:
            v = df[col].dropna().astype(str)
            n = int((~v.str.startswith(prefijo)).sum())
            if n:
                hallazgos[col] = n
    for col, (prefijo, _) in COLUMNAS_ALIAS.items():
        if col in df.columns:
            v = df[col].dropna().astype(str)
            n = int((~v.str.startswith(prefijo)).sum())
            if n:
                hallazgos[col] = n
    return hallazgos
