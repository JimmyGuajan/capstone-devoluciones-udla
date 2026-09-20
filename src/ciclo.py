"""Ciclo de vida de cada unidad: despacho, permanencia y devolucion.

Este modulo implementa la definicion de target acordada con el negocio:

    Una unidad despachada a un local que permanece UMBRAL_DIAS o mas sin
    venderse se cuenta como devolucion esperada.

Y, en paralelo, mide la **devolucion observada**: la unidad que reaparece
fisicamente en bodega central despues de haber estado en un local. Tener las
dos permite calibrar la regla de negocio contra el hecho fisico, que es el
control de calidad que el plan pide en su seccion 5.6.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import UMBRAL_DIAS

CENTRALES = ("BODEGA CENTRAL", "BODEGA MATERIA PRIMA", "PRODUCCI", "SCRAP")


def es_central(nombre: pd.Series) -> pd.Series:
    n = nombre.astype(str).str.upper()
    m = pd.Series(False, index=nombre.index)
    for c in CENTRALES:
        m |= n.str.contains(c, na=False, regex=False)
    return m


# --- Estadias ----------------------------------------------------------------
def estadias(stock: pd.DataFrame) -> pd.DataFrame:
    """Colapsa el snapshot diario a tramos: donde estuvo cada IMEI y cuanto.

    Un IMEI aparece en ~N snapshots consecutivos mientras esta en una bodega.
    Guardar esas N filas es redundante; lo que importa es el tramo
    (imei, bodega, desde, hasta). Reduce el volumen entre 10 y 30 veces y es
    la estructura sobre la que se calcula todo lo demas.
    """
    s = stock[["imei", "bodega_id", "bodega_nombre", "sku", "modelo",
               "marca", "condicion", "precio", "fecha"]].sort_values(["imei", "fecha"])
    # Un tramo nuevo empieza cuando cambia el imei o cambia la bodega.
    corte = (s["imei"] != s["imei"].shift()) | (s["bodega_id"] != s["bodega_id"].shift())
    s["tramo"] = corte.cumsum()
    e = (s.groupby("tramo", sort=False)
           .agg(imei=("imei", "first"), bodega_id=("bodega_id", "first"),
                bodega_nombre=("bodega_nombre", "first"), sku=("sku", "first"),
                modelo=("modelo", "first"), marca=("marca", "first"),
                condicion=("condicion", "last"), precio=("precio", "last"),
                desde=("fecha", "min"), hasta=("fecha", "max"),
                dias_observados=("fecha", "size"))
           .reset_index(drop=True))
    e["dias_tramo"] = (e["hasta"] - e["desde"]).dt.days + 1
    e["en_central"] = es_central(e["bodega_nombre"])
    return e


# --- Ciclo de vida por unidad -------------------------------------------------
def construir(despachos: pd.DataFrame, est: pd.DataFrame,
              ventas: pd.DataFrame | None = None,
              umbral: int = UMBRAL_DIAS,
              corte_ventas: pd.Timestamp | None = None) -> pd.DataFrame:
    """Una fila por unidad despachada, con su desenlace.

    Solo se consideran los despachos de EQUIPO, que son los que llevan IMEI.
    Las SIM no son trazables por esta via porque el snapshot de simcards no
    trae el codigo de bodega.
    """
    d = (despachos[despachos.segmento.eq("EQUIPO") & despachos.imei.notna()]
         .sort_values("fecha")
         .drop_duplicates("imei", keep="last")          # ultimo despacho de la unidad
         [["imei", "fecha", "sku", "producto", "marca", "ruc", "destino",
           "destino_cod", "ciudad", "canal", "precio"]]
         .rename(columns={"fecha": "fecha_despacho", "precio": "precio_despacho"}))

    e = est.merge(d[["imei", "fecha_despacho"]], on="imei", how="inner")

    # Llegada al local: primera estadia NO central que termina despues del
    # despacho. Filtrar solo por "posterior al despacho" no basta: la unidad
    # sigue figurando en el snapshot de central uno o dos dias despues de
    # salir, y ese rastro se confundiria con un retorno.
    local = (e[(~e.en_central) & (e.hasta >= e.fecha_despacho)]
             .sort_values(["imei", "desde"]))
    perm = (local.groupby("imei")
                 .agg(llegada_local=("desde", "min"),
                      bodega_final=("bodega_id", "last"),
                      bodega_final_nombre=("bodega_nombre", "last"),
                      ultima_vista=("hasta", "max"),
                      condicion=("condicion", "last"))
                 .reset_index())

    # Retorno observado: transicion local -> central en la secuencia de
    # estadias. Se recorre el orden real de los tramos, no un maximo: una
    # unidad puede volver a central y ser reenviada a otro local, y ese
    # regreso cuenta igual.
    seq = (e.merge(perm[["imei", "llegada_local"]], on="imei", how="inner")
            .sort_values(["imei", "desde"]))
    mismo = seq["imei"].eq(seq["imei"].shift())
    venia_de_local = mismo & ~seq["en_central"].shift().fillna(True)
    # El regreso tiene que ser posterior a la llegada al local; si no, se
    # estaria contando el rastro que la unidad deja en central mientras viaja.
    tras_llegada = seq["desde"] > seq["llegada_local"]
    ret = (seq[seq["en_central"] & venia_de_local & tras_llegada]
           .groupby("imei").desde.min().rename("fecha_retorno").reset_index())

    c = d.merge(perm, on="imei", how="left").merge(ret, on="imei", how="left")

    # Venta al cliente final, si la hay.
    if ventas is not None and len(ventas):
        v = (ventas[ventas.imei.notna()].groupby("imei").fecha.min()
             .rename("fecha_venta").reset_index())
        c = c.merge(v, on="imei", how="left")
        if corte_ventas is None:
            corte_ventas = ventas["fecha"].max()
    else:
        c["fecha_venta"] = pd.NaT

    # --- Desenlace ------------------------------------------------------------
    # La observacion termina en el menor de los dos cortes. El inventario llega
    # mas lejos que las ventas, y usar el corte del inventario haria que las
    # unidades recientes parecieran no vendidas solo porque su venta aun no
    # esta registrada.
    corte_stock = est["hasta"].max()
    corte_obs = min(corte_stock, corte_ventas) if corte_ventas is not None else corte_stock

    # Una unidad que nunca aparece en ningun snapshot de local no es rastreable:
    # no se sabe si llego, si se vendio alli o si volvio. Marcarla como devuelta
    # por "llevar muchos dias" seria inventar el dato -- el caso extremo son 544
    # unidades a un cliente institucional, todas con exactamente 847 dias, que
    # es la fecha de corte menos la del despacho. Se excluyen del target.
    c["trazable"] = c["llegada_local"].notna()

    c["vendida"] = c["fecha_venta"].notna()
    c["devuelta_real"] = c["fecha_retorno"].notna() & (
        c["fecha_venta"].isna() | (c["fecha_retorno"] < c["fecha_venta"]))

    # Dias que la unidad permanecio en el local antes de salir de el, por venta
    # o por regreso a central. Se cuenta desde la llegada, no desde el despacho:
    # el transito no es responsabilidad del distribuidor.
    inicio = c["llegada_local"]
    salida = c[["fecha_venta", "fecha_retorno"]].min(axis=1)
    fin_obs = salida.fillna(corte_obs).clip(upper=corte_obs)
    c["dias_en_local"] = (fin_obs - inicio).dt.days.clip(lower=0)

    # Target de negocio, planteado como supervivencia: la unidad llego al dia
    # `umbral` sin haber salido del local. Que se venda despues no lo cambia --
    # a los 60 dias ya era inventario parado, que es lo que el negocio quiere
    # anticipar.
    c["devuelta_60d"] = c["trazable"] & (c["dias_en_local"] >= umbral)

    # Solo es evaluable la unidad para la que se pudieron observar `umbral` dias
    # completos desde su llegada al local. Sin este filtro los ultimos meses
    # aparecen inflados: sus unidades no tuvieron tiempo de venderse dentro de
    # la ventana de datos.
    c["madura"] = c["trazable"] & (
        (corte_obs - c["llegada_local"]).dt.days >= umbral)

    c["mes_despacho"] = c["fecha_despacho"].dt.to_period("M").dt.to_timestamp()

    # Mes en que se imputa cada devolucion. Para la regla de negocio es el mes
    # en que la unidad cumple el umbral; para el retorno fisico, el mes en que
    # efectivamente vuelve. np.where romperia el dtype datetime, asi que se
    # construyen por enmascaramiento.
    cumple = ((c["llegada_local"] + pd.Timedelta(days=umbral))
              .dt.to_period("M").dt.to_timestamp())
    c["mes_dev_60d"] = cumple.where(c["devuelta_60d"])
    c["mes_dev_real"] = (c["fecha_retorno"].dt.to_period("M").dt.to_timestamp()
                         .where(c["devuelta_real"]))
    return c


# --- Panel de modelado --------------------------------------------------------
def panel_mensual(ciclo: pd.DataFrame, por=("marca",),
                  target: str = "devuelta_60d") -> pd.DataFrame:
    """Serie mensual de devoluciones por la dimension elegida.

    `por` puede ser ('marca',), ('sku',), ('marca','ruc'), ('marca','ciudad')...
    Se incluyen explicitamente los meses sin devolucion.
    """
    c = ciclo[ciclo.madura & ciclo.trazable].copy()

    # Los ultimos meses conservan muy pocas unidades maduras: su tasa se
    # calcula sobre una muestra minuscula y no es comparable. Se recortan los
    # meses de cola cuyo volumen cae por debajo del 30 % de la mediana.
    porm = c.groupby(c.mes_despacho).size()
    if len(porm) > 3:
        umbral_vol = porm.median() * 0.3
        validos = porm[porm >= umbral_vol].index
        c = c[c.mes_despacho.isin(validos)]

    llaves = list(por)
    col_mes = {"devuelta_60d": "mes_dev_60d", "devuelta_real": "mes_dev_real"}[target]

    desp = (c.groupby(llaves + ["mes_despacho"])
              .agg(despachadas=("imei", "size"),
                   valor_despachado=("precio_despacho", "sum"))
              .reset_index().rename(columns={"mes_despacho": "mes"}))

    dev = (c[c[target] & c[col_mes].notna()].groupby(llaves + [col_mes])
             .agg(devueltas=("imei", "size"),
                  valor_devuelto=("precio_despacho", "sum"))
             .reset_index().rename(columns={col_mes: "mes"}))

    meses = pd.date_range(c.mes_despacho.min(), c.mes_despacho.max(), freq="MS")
    niveles = [sorted(c[k].dropna().unique()) for k in llaves] + [meses]
    idx = pd.MultiIndex.from_product(niveles, names=llaves + ["mes"]).to_frame(index=False)

    p = (idx.merge(desp, on=llaves + ["mes"], how="left")
            .merge(dev, on=llaves + ["mes"], how="left"))
    num = ["despachadas", "valor_despachado", "devueltas", "valor_devuelto"]
    p[num] = p[num].fillna(0)
    p["tasa_devolucion"] = p["devueltas"] / p["despachadas"].replace(0, np.nan)
    return p.sort_values(llaves + ["mes"]).reset_index(drop=True)


def barrido_umbral(ciclo: pd.DataFrame,
                   umbrales=range(15, 151, 15)) -> pd.DataFrame:
    """Contrasta la regla de negocio contra el retorno fisico observado.

    La regla dice "N dias en el local sin vender = devolucion". El retorno
    fisico es un hecho observable en los snapshots. Barrer N permite responder
    con datos si el umbral elegido es el adecuado, en lugar de adoptarlo por
    convencion.

    Precision = de las unidades que la regla marca, cuantas vuelven de verdad.
    Cobertura = de las que vuelven de verdad, cuantas anticipa la regla.
    """
    c = ciclo[ciclo.madura & ciclo.trazable]
    real = c["devuelta_real"].to_numpy()
    filas = []
    for n in umbrales:
        pred = (c["dias_en_local"] >= n).to_numpy()
        vp = int((pred & real).sum())
        prec = vp / pred.sum() if pred.sum() else np.nan
        cob = vp / real.sum() if real.sum() else np.nan
        f1 = 2 * prec * cob / (prec + cob) if prec and cob else 0.0
        filas.append({"umbral_dias": n, "marcadas": int(pred.sum()),
                      "aciertos": vp, "precision": round(prec, 3),
                      "cobertura": round(cob, 3), "F1": round(f1, 3)})
    return pd.DataFrame(filas)


def resumen(ciclo: pd.DataFrame) -> pd.Series:
    c = ciclo
    m = c[c.madura & c.trazable]
    return pd.Series({
        "unidades despachadas": len(c),
        "rastreables en snapshots": int(c.trazable.sum()),
        "con desenlace maduro": len(m),
        "vendidas": int(m.vendida.sum()),
        "devueltas (regla 60d)": int(m.devuelta_60d.sum()),
        "devueltas (retorno observado)": int(m.devuelta_real.sum()),
        "tasa devolucion 60d": round(m.devuelta_60d.mean(), 4),
        "tasa devolucion observada": round(m.devuelta_real.mean(), 4),
        "dias en local (mediana)": float(m.dias_en_local.median()),
        "dias en local (p90)": float(m.dias_en_local.quantile(.9)),
    })
