"""Antiguedad de inventario en el canal — definicion operativa del negocio.

El cliente cuenta como devolucion esperada toda unidad que **lleva UMBRAL_DIAS
o mas en la misma bodega de un distribuidor**, medido sobre el inventario
diario. No interviene el reporte de despachos.

Se valido contra un corte real: de los 367 Samsung que el negocio marco el
13-ene-2026, los 367 aparecen en nuestro snapshot de ese dia con la misma
bodega, y su mediana de permanencia es de 80 dias frente a 13 del resto del
inventario Samsung.

Diferencia con `ciclo.py`, que se conserva para comparacion: alli los dias se
contaban desde la llegada al local segun el despacho, lo que obligaba a
emparejar dos fuentes y dejaba fuera el 8 % de unidades no rastreables. Aqui
basta el inventario.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import UMBRAL_DIAS
from .ciclo import es_central

# Un hueco de uno o dos dias no altera el conteo de antiguedad; a partir de
# tres ya puede esconder un movimiento de la unidad.
HUECO_TOLERABLE = 2

# Bodegas operadas por Telefonica, que el reporte del negocio no cuenta como
# inventario del canal. Se derivaron comparando nuestro calculo contra el
# listado real del 13-ene-2026: de las 185 unidades que marcabamos de mas,
# 176 estaban en alguna de estas.
#
# El matiz de CAVS: "CAVS SAN MARINO" es tienda propia y se excluye, pero
# "CAVS AE SALESLAND MACHALA" la opera un agente externo y si cuenta. La
# marca "AE" es la que distingue. Pendiente de confirmar con el cliente
# (consulta b del acta de solicitud de datos).
NO_CANAL = (
    r"TIENDA VIRTUAL|REF\. OPERACIONES|PRUEBAS|^\.1 ACCOUNT|"
    r"DEVOLUCIONES DELIVERY|SERVICIO TECNICO|DELIVERY EXPRESS|"
    r"^CAVS (?!.*\bAE\b)"
)


def dias_faltantes(stock: pd.DataFrame) -> pd.DatetimeIndex:
    """Dias del periodo sin ningun snapshot."""
    d = pd.DatetimeIndex(sorted(stock["fecha"].unique()))
    return pd.date_range(d.min(), d.max(), freq="D").difference(d)


def estadias_canal(est: pd.DataFrame, faltantes: pd.DatetimeIndex,
                   umbral: int = UMBRAL_DIAS,
                   corte: pd.Timestamp | None = None) -> pd.DataFrame:
    """Estadias en bodega de canal, con su antiguedad y sus advertencias.

    Se excluyen las bodegas propias de Telefonica: bodega central, materia
    prima, scrap y tiendas propias. El reporte del negocio tampoco las cuenta,
    porque no son inventario en poder del canal.
    """
    propia = (est.en_central
              | est.bodega_nombre.str.upper().str.contains(NO_CANAL, regex=True, na=False))
    e = est[~propia].copy()
    corte = corte or est["hasta"].max()

    e["dias_en_bodega"] = (e["hasta"] - e["desde"]).dt.days + 1

    # --- Advertencias por huecos de snapshot -------------------------------
    # Si la unidad llego durante un hueco, su antiguedad arranca tarde y queda
    # subestimada. Si salio y volvio dentro del hueco, queda sobreestimada.
    if len(faltantes):
        f = pd.Series(faltantes)
        # dia inmediatamente posterior a cada hueco
        tras_hueco = set((f[f.diff().dt.days.ne(1).shift(-1).fillna(True)]
                          + pd.Timedelta(days=1)).dt.normalize())
        # tamano del hueco que precede a cada uno de esos dias
        grupo = f.diff().dt.days.ne(1).cumsum()
        tam = {(x.max() + pd.Timedelta(days=1)).normalize(): len(x)
               for _, x in f.groupby(grupo)}
        e["inicio_tras_hueco"] = e["desde"].isin(tras_hueco)
        e["dias_hueco_previo"] = e["desde"].map(tam).fillna(0).astype(int)
        # huecos contenidos dentro del tramo
        cuenta = pd.Series(1, index=faltantes).cumsum()
        dentro = (cuenta.reindex(e["hasta"], method="ffill").fillna(0).to_numpy()
                  - cuenta.reindex(e["desde"], method="ffill").fillna(0).to_numpy())
        e["dias_sin_dato_dentro"] = dentro.astype(int)
    else:
        e["inicio_tras_hueco"] = False
        e["dias_hueco_previo"] = 0
        e["dias_sin_dato_dentro"] = 0

    e["antiguedad_dudosa"] = (
        (e["inicio_tras_hueco"] & (e["dias_hueco_previo"] > HUECO_TOLERABLE))
        | (e["dias_sin_dato_dentro"] > HUECO_TOLERABLE))

    # --- Target -------------------------------------------------------------
    e["supera_umbral"] = e["dias_en_bodega"] >= umbral
    # Dia en que la unidad cumple el umbral; es la fecha del evento.
    e["fecha_umbral"] = e["desde"] + pd.Timedelta(days=umbral - 1)
    e["mes_umbral"] = e["fecha_umbral"].dt.to_period("M").dt.to_timestamp()
    # Solo es evaluable la estadia que tuvo tiempo de llegar al umbral.
    e["madura"] = e["fecha_umbral"] <= corte
    e["mes_inicio"] = e["desde"].dt.to_period("M").dt.to_timestamp()
    return e.reset_index(drop=True)


def foto_mensual(e: pd.DataFrame, umbral: int = UMBRAL_DIAS) -> pd.DataFrame:
    """Unidades con UMBRAL o mas dias de antiguedad al cierre de cada mes.

    Reproduce el reporte operativo del cliente, que es una foto y no un flujo.
    Sirve para conciliar; el modelo usa la serie de eventos.
    """
    cortes = pd.date_range(e.desde.min(), e.hasta.max(), freq="ME")
    filas = []
    for c in cortes:
        v = e[(e.desde <= c) & (e.hasta >= c)]
        ant = (c - v.desde).dt.days + 1
        filas.append({"corte": c, "en_canal": len(v),
                      "con_umbral": int((ant >= umbral).sum()),
                      "valor": float(v.loc[ant >= umbral, "precio"].sum())})
    f = pd.DataFrame(filas)
    f["pct"] = (f.con_umbral / f.en_canal.replace(0, np.nan) * 100).round(1)
    return f


def panel_mensual(e: pd.DataFrame, por=("marca",),
                  excluir_dudosas: bool = False) -> pd.DataFrame:
    """Serie mensual de unidades que cumplen el umbral, con los ceros incluidos."""
    d = e[e.madura]
    if excluir_dudosas:
        d = d[~d.antiguedad_dudosa]
    llaves = list(por)

    ent = (d.groupby(llaves + ["mes_inicio"])
             .agg(ingresaron=("imei", "size"))
             .reset_index().rename(columns={"mes_inicio": "mes"}))
    sup = (d[d.supera_umbral].groupby(llaves + ["mes_umbral"])
             .agg(superan=("imei", "size"), valor=("precio", "sum"))
             .reset_index().rename(columns={"mes_umbral": "mes"}))

    meses = pd.date_range(d.mes_inicio.min(), d.mes_umbral.max(), freq="MS")
    idx = pd.MultiIndex.from_product(
        [*[sorted(d[k].dropna().unique()) for k in llaves], meses],
        names=llaves + ["mes"]).to_frame(index=False)

    p = (idx.merge(ent, on=llaves + ["mes"], how="left")
            .merge(sup, on=llaves + ["mes"], how="left"))
    p[["ingresaron", "superan", "valor"]] = p[["ingresaron", "superan", "valor"]].fillna(0)
    p["tasa"] = p.superan / p.ingresaron.replace(0, np.nan)
    return p.sort_values(llaves + ["mes"]).reset_index(drop=True)


def validar(e: pd.DataFrame, imeis: set[str], corte: pd.Timestamp,
            umbral: int = UMBRAL_DIAS) -> pd.DataFrame:
    """Compara un listado del negocio contra el calculo propio en esa fecha."""
    v = e[(e.desde <= corte) & (e.hasta >= corte)].copy()
    v["antiguedad"] = (corte - v.desde).dt.days + 1
    v["en_listado"] = v.imei.isin(imeis)
    v["nosotros"] = v.antiguedad >= umbral
    t = pd.crosstab(v.en_listado, v.nosotros)
    t.index = ["fuera del listado", "en el listado"]
    t.columns = [f"<{umbral} dias", f"{umbral}+ dias"]
    return t


def resumen(e: pd.DataFrame) -> pd.Series:
    m = e[e.madura]
    return pd.Series({
        "estadias en canal": len(e),
        "evaluables (maduras)": len(m),
        "superan el umbral": int(m.supera_umbral.sum()),
        "tasa": round(m.supera_umbral.mean(), 4),
        "con antiguedad dudosa": int(m.antiguedad_dudosa.sum()),
        "dias en bodega (mediana)": float(m.dias_en_bodega.median()),
        "dias en bodega (p90)": float(m.dias_en_bodega.quantile(.9)),
    })
