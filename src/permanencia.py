"""Permanencia en el canal — definicion confirmada con el negocio.

Reglas, todas verificadas contra listados reales entregados por planificacion:

1. La antiguedad se cuenta desde la **fecha de despacho**, no desde la llegada
   a la bodega. Verificado: `dias = corte - fecha despachada` en 801 de 801
   registros del listado de enero 2025.

2. El reloj **se reinicia solo si la unidad vuelve a bodega central**. Moverse
   entre locales del canal no lo reinicia. Ejemplo del listado: un equipo
   despachado el 13-nov a CAVS MALL DEL RIO y movido el 27-nov a AE CELISTICS
   sigue contando desde el 13. En cambio otro que volvio a central el 5-nov y
   salio de nuevo cuenta desde esa segunda salida.

3. El corte es **fin de mes**, y la unidad debe seguir en stock a esa fecha.

4. Una devolucion del mes M es la unidad que **cumple el umbral durante M**.
   Es un flujo, no una foto: las que ya lo cumplieron antes no se repiten.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import UMBRAL_DIAS


def periodo_en_canal(est: pd.DataFrame) -> pd.DataFrame:
    """Inicio del tramo continuo actual de cada unidad fuera de bodega central.

    Se recorre la secuencia de estadias y se abre un periodo nuevo cada vez que
    la unidad sale de una bodega central hacia el canal. Los movimientos entre
    locales no abren periodo.
    """
    e = est.sort_values(["imei", "desde"]).copy()
    nueva_unidad = e["imei"].ne(e["imei"].shift())
    venia_central = e["en_central"].shift().fillna(True)
    # Un periodo nuevo empieza al pasar de central (o del inicio) a canal.
    e["nuevo_periodo"] = (~e["en_central"]) & (venia_central | nueva_unidad)
    e["periodo_id"] = e.groupby("imei")["nuevo_periodo"].cumsum()

    canal = e[~e["en_central"] & (e["periodo_id"] > 0)]
    per = (canal.groupby(["imei", "periodo_id"])
                .agg(inicio_canal=("desde", "min"),
                     fin_canal=("hasta", "max"),
                     bodega=("bodega_id", "last"),
                     bodega_nombre=("bodega_nombre", "last"),
                     sku=("sku", "last"), modelo=("modelo", "last"),
                     marca=("marca", "last"), precio=("precio", "last"),
                     condicion=("condicion", "last"))
                .reset_index())
    return per


def con_despacho(per: pd.DataFrame, despachos: pd.DataFrame,
                 margen_dias: int = 10) -> pd.DataFrame:
    """Asocia a cada periodo en canal el despacho que lo origino.

    Es el ultimo despacho ocurrido dentro de los `margen_dias` previos a la
    llegada al local. El margen cubre el transito: entre el despacho y la
    primera aparicion en el inventario pasan tipicamente dos dias.
    """
    d = (despachos[despachos.segmento.eq("EQUIPO") & despachos.imei.notna()]
         [["imei", "fecha", "destino", "ruc", "ciudad", "canal", "precio"]]
         .rename(columns={"fecha": "fecha_despacho",
                          "precio": "precio_despacho"}))

    m = per.merge(d, on="imei", how="left")
    # El despacho valido es anterior o igual a la llegada, dentro del margen.
    ok = (m.fecha_despacho <= m.inicio_canal) & \
         (m.inicio_canal - m.fecha_despacho <= pd.Timedelta(days=margen_dias))
    m = m[ok].sort_values("fecha_despacho").drop_duplicates(
        ["imei", "periodo_id"], keep="last")

    # Periodos sin despacho asociado: se conserva la llegada como referencia.
    sin = per.merge(m[["imei", "periodo_id"]], on=["imei", "periodo_id"],
                    how="left", indicator=True)
    sin = sin[sin._merge == "left_only"].drop(columns="_merge")
    if len(sin):
        sin["fecha_despacho"] = sin["inicio_canal"]
        sin["sin_despacho"] = True
        m["sin_despacho"] = False
        m = pd.concat([m, sin], ignore_index=True)
    else:
        m["sin_despacho"] = False
    return m.reset_index(drop=True)


def marcar(per: pd.DataFrame, umbral: int = UMBRAL_DIAS) -> pd.DataFrame:
    """Fecha en que el periodo cumple el umbral y si llego a cumplirlo."""
    p = per.copy()
    p["fecha_umbral"] = p["fecha_despacho"] + pd.Timedelta(days=umbral)
    p["mes_umbral"] = p["fecha_umbral"].dt.to_period("M").dt.to_timestamp()
    p["dias_totales"] = (p["fin_canal"] - p["fecha_despacho"]).dt.days
    # Cumple si seguia en el canal el dia en que tocaba el umbral.
    p["cumple"] = p["fecha_umbral"] <= p["fin_canal"]
    return p


def flujo_mensual(per: pd.DataFrame, por=("marca",),
                  desde: str | None = None) -> pd.DataFrame:
    """Unidades que cumplen el umbral durante cada mes — el target del modelo.

    Es lo que el negocio reporta como devoluciones del mes: las que cruzan el
    umbral en ese periodo, sin arrastrar las que ya lo cruzaron antes.
    """
    # Los periodos sin despacho asociado no son medibles con la definicion del
    # negocio, que cuenta dias desde el despacho. Son 53.838 de 309.768: 11.670
    # arrancan en enero de 2024 (ya estaban en tienda cuando empiezan los datos)
    # y 38.531 tienen un IMEI que no aparece en ningun despacho. Incluirlos
    # usando la fecha de llegada infla los primeros meses de la serie.
    per = per[~per.sin_despacho]

    c = per[per.cumple].copy()
    llaves = list(por)
    g = (c.groupby(llaves + ["mes_umbral"])
           .agg(devueltas=("imei", "size"), valor=("precio_despacho", "sum"))
           .reset_index().rename(columns={"mes_umbral": "mes"}))

    des = (per.groupby(llaves + [per.fecha_despacho.dt.to_period("M").dt.to_timestamp()])
             .agg(despachadas=("imei", "size")).reset_index())
    des.columns = llaves + ["mes", "despachadas"]

    meses = pd.date_range(g.mes.min(), g.mes.max(), freq="MS")
    idx = pd.MultiIndex.from_product(
        [*[sorted(per[k].dropna().unique()) for k in llaves], meses],
        names=llaves + ["mes"]).to_frame(index=False)
    p = idx.merge(des, on=llaves + ["mes"], how="left") \
           .merge(g, on=llaves + ["mes"], how="left")
    p[["despachadas", "devueltas", "valor"]] = \
        p[["despachadas", "devueltas", "valor"]].fillna(0)
    p["tasa"] = p.devueltas / p.despachadas.replace(0, np.nan)
    if desde:
        p = p[p.mes >= desde]
    return p.sort_values(llaves + ["mes"]).reset_index(drop=True)


def foto(per: pd.DataFrame, corte: pd.Timestamp,
         umbral: int = UMBRAL_DIAS) -> pd.DataFrame:
    """Inventario con `umbral` o mas dias a una fecha — la vista acumulada.

    A diferencia del flujo, aqui aparecen todas las cohortes: incluye unidades
    despachadas hace mas de un ano que siguen sin venderse.
    """
    v = per[(per.inicio_canal <= corte) & (per.fin_canal >= corte)].copy()
    v["dias"] = (corte - v.fecha_despacho).dt.days
    v = v[v.dias >= umbral]
    v["cohorte"] = v.fecha_despacho.dt.to_period("M").dt.to_timestamp()
    return v


def validar(per: pd.DataFrame, imeis: set[str], corte: pd.Timestamp,
            umbral: int = UMBRAL_DIAS) -> dict:
    """Compara el flujo del mes del corte contra un listado del negocio."""
    ini = corte.replace(day=1)
    f = per[per.cumple & per.fecha_umbral.between(ini, corte)
            & (per.fin_canal >= corte)]
    nuestro = set(f.imei)
    return {"listado": len(imeis), "nuestro": len(nuestro),
            "coinciden": len(nuestro & imeis),
            "solo_nuestro": len(nuestro - imeis),
            "solo_listado": len(imeis - nuestro),
            "cobertura": round(len(nuestro & imeis) / max(len(imeis), 1), 4)}
