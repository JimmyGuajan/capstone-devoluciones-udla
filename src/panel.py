"""Construccion de la sabana de modelado y del ciclo de vida de las SIMs."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CAMPANIAS
from .events import DEVOLUCION, INTRA, PEDIDO


# --- Ciclo de vida serializado ----------------------------------------------
def ciclo_vida_sims(ventas: pd.DataFrame) -> pd.DataFrame:
    """Intenta unir sell-in y sell-out por ICCID sobre los 20 meses de historia.

    ATENCION -- el enlace NO cierra, y el motivo es un hallazgo del proyecto:
    'Venta al Partner' en el reporte de ventas no es sell-in a distribuidores
    sino transferencia de rangos de SIM a socios MVNO (Tuenti, MVNO1, MVNO2,
    AKIMovil, Maxiplus). La interseccion de ICCID entre ambos flujos es del
    0,56 %. Ver diagnostico_flujos_ventas().

    La funcion se conserva porque produce esa evidencia; no debe usarse como
    fuente de variables del modelo.
    """
    v = ventas[ventas.iccid.notna()]
    ent = (v[v.flujo == "SELL_IN"].sort_values("fecha")
             .drop_duplicates("iccid")[["iccid", "fecha", "producto", "segmento", "precio"]]
             .rename(columns={"fecha": "fecha_sellin"}))
    sal = (v[v.flujo == "SELL_OUT"].sort_values("fecha")
             .drop_duplicates("iccid")[["iccid", "fecha", "bodega_id", "bodega_nombre"]]
             .rename(columns={"fecha": "fecha_sellout"}))

    c = ent.merge(sal, on="iccid", how="left")
    c["colocada"] = c["fecha_sellout"].notna()
    c["dias_a_venta"] = (c["fecha_sellout"] - c["fecha_sellin"]).dt.days
    # Una venta anterior al sell-in indica un desfase de registro, no un ciclo real.
    c.loc[c["dias_a_venta"] < 0, "dias_a_venta"] = np.nan
    c["mes_sellin"] = c["fecha_sellin"].dt.to_period("M").dt.to_timestamp()
    return c


def diagnostico_flujos_ventas(ventas: pd.DataFrame) -> pd.DataFrame:
    """Evidencia de que 'Venta al Partner' no es sell-in a distribuidores.

    Si lo fuera, cada producto tendria sell-in y sell-out del mismo orden de
    magnitud. En cambio las marcas MVNO concentran el sell-in y practicamente
    no registran sell-out: son rangos cedidos a otro operador, que los coloca
    en su propio circuito.
    """
    t = (ventas.groupby(["producto", "flujo"]).size().unstack("flujo")
         .fillna(0).astype(int))
    for c in ("SELL_IN", "SELL_OUT"):
        if c not in t:
            t[c] = 0
    t["ratio_out_in"] = (t["SELL_OUT"] / t["SELL_IN"].replace(0, np.nan)).round(3)
    return t.sort_values("SELL_IN", ascending=False)


def serie_sellout_mensual(ventas: pd.DataFrame, bodegas: pd.DataFrame) -> pd.DataFrame:
    """Sell-out por distribuidor, segmento y mes: la unica serie larga usable.

    El sell-out si trae la bodega donde se produjo la venta, y esa bodega cruza
    con el catalogo al 82 %. Da 20 meses de rotacion real por distribuidor, que
    es el insumo de estacionalidad y de las variables de conversion del panel.
    """
    so = (ventas[ventas.flujo == "SELL_OUT"]
          .merge(bodegas[["bodega_id", "ruc", "provincia", "canal"]],
                 on="bodega_id", how="left"))
    so = so[so.ruc.notna()].copy()
    so["mes"] = so["fecha"].dt.to_period("M").dt.to_timestamp()
    s = (so.groupby(["ruc", "segmento", "mes"])
           .agg(sellout=("serie", "size"), valor=("precio", "sum"))
           .reset_index())
    # Los meses de borde tienen cobertura parcial y distorsionan la estacionalidad.
    completos = s.groupby("mes").sellout.sum()
    validos = completos[completos > completos.max() * 0.2].index
    return s[s.mes.isin(validos)].reset_index(drop=True)


def curva_colocacion(ciclo: pd.DataFrame, cortes=(30, 60, 90, 120, 180)) -> pd.DataFrame:
    """Porcentaje de unidades colocadas dentro de N dias, por mes de sell-in.

    Solo se evaluan los meses con observacion completa: una cohorte necesita N
    dias de seguimiento para que su tasa a N dias sea comparable.
    """
    fin = ciclo["fecha_sellout"].max()
    filas = []
    for mes, g in ciclo.groupby("mes_sellin"):
        fila = {"mes_sellin": mes, "unidades": len(g)}
        for n in cortes:
            maduro = (fin - mes).days >= n
            fila[f"colocada_{n}d"] = (
                (g["dias_a_venta"] <= n).mean() if maduro else np.nan)
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("mes_sellin")


# --- Calendario --------------------------------------------------------------
def marcar_campanias(fechas: pd.Series) -> pd.DataFrame:
    f = pd.to_datetime(fechas)
    out = pd.DataFrame(index=f.index)
    out["en_campania"] = 0
    out["dias_desde_fin_campania"] = np.nan
    for nombre, (ini, fin) in CAMPANIAS.items():
        ini, fin = pd.Timestamp(ini), pd.Timestamp(fin)
        out.loc[f.between(ini, fin), "en_campania"] = 1
        post = (f - fin).dt.days
        cand = post.where(post >= 0)
        out["dias_desde_fin_campania"] = np.fmin(
            out["dias_desde_fin_campania"].fillna(np.inf), cand.fillna(np.inf))
    out["dias_desde_fin_campania"] = out["dias_desde_fin_campania"].replace(np.inf, np.nan)
    # La devolucion es un fenomeno posterior a la campana: el distribuidor no
    # coloco el sobre-stock que pidio anticipandose a ella.
    out["mes_post_campania"] = (out["dias_desde_fin_campania"] <= 31).astype(int)
    return out


# --- Sabana ------------------------------------------------------------------
def construir(eventos: pd.DataFrame, bodegas: pd.DataFrame, cupos: pd.DataFrame,
              stock_equipos: pd.DataFrame, ventas: pd.DataFrame,
              freq: str = "D") -> pd.DataFrame:
    """Panel distribuidor x segmento x periodo, con los ceros explicitos.

    Omitir las celdas sin devolucion es el error que mas sesga estos modelos:
    el modelo deja de aprender cuando *no* hay devolucion, que es el 98 % de
    los casos.
    """
    e = eventos.copy()
    e["periodo"] = e["fecha"].dt.to_period(freq).dt.to_timestamp()

    def _agg(clase: str, pref: str) -> pd.DataFrame:
        g = e[e.clase == clase].groupby(["ruc", "segmento", "periodo"])
        return pd.DataFrame({f"{pref}_u": g.cantidad.sum(),
                             f"{pref}_lin": g.size(),
                             f"{pref}_ord": g.orden_id.nunique()}).reset_index()

    rucs = sorted(bodegas.loc[bodegas.es_distribuidor, "ruc"].dropna().unique())
    periodos = pd.period_range(e.periodo.min(), e.periodo.max(), freq=freq).to_timestamp()
    p = pd.MultiIndex.from_product(
        [rucs, ["SIM", "EQUIPO"], periodos],
        names=["ruc", "segmento", "periodo"]).to_frame(index=False)

    for clase, pref in [(DEVOLUCION, "dev"), (PEDIDO, "ped"), (INTRA, "intra")]:
        p = p.merge(_agg(clase, pref), on=["ruc", "segmento", "periodo"], how="left")
    cnt = [c for c in p.columns if c.endswith(("_u", "_lin", "_ord"))]
    p[cnt] = p[cnt].fillna(0)

    # --- Sell-out y sell-in del mes anterior, desde las ventas serializadas ---
    v = ventas.merge(bodegas[["bodega_id", "ruc"]], on="bodega_id", how="left")
    v = v[v.ruc.notna()].copy()
    v["periodo"] = v["fecha"].dt.to_period("M").dt.to_timestamp()
    flujos = (v.groupby(["ruc", "segmento", "periodo", "flujo"]).size()
                .unstack("flujo").fillna(0).reset_index())
    for c in ("SELL_IN", "SELL_OUT"):
        if c not in flujos:
            flujos[c] = 0.0
    flujos["periodo"] = flujos["periodo"] + pd.DateOffset(months=1)  # rezago: solo pasado
    flujos = flujos.rename(columns={"SELL_IN": "sellin_m1", "SELL_OUT": "sellout_m1"})
    p["mes"] = p["periodo"].dt.to_period("M").dt.to_timestamp()
    p = p.merge(flujos.rename(columns={"periodo": "mes"}),
                on=["ruc", "segmento", "mes"], how="left")
    p[["sellin_m1", "sellout_m1"]] = p[["sellin_m1", "sellout_m1"]].fillna(0)

    # --- Inventario en poder del distribuidor --------------------------------
    s = stock_equipos.merge(bodegas[["bodega_id", "ruc"]], on="bodega_id", how="left")
    s = s[s.ruc.notna()].copy()
    s["periodo"] = s["fecha"].dt.to_period(freq).dt.to_timestamp()
    stk = (s.groupby(["ruc", "segmento", "periodo"])
             .agg(stock_u=("imei", "size"),
                  stock_valor=("precio", "sum"),
                  pct_obsoleto=("condicion", lambda x: (x == "Obsoleto").mean()),
                  pct_usado=("condicion", lambda x: (x == "Usado").mean()))
             .reset_index())
    p = p.merge(stk, on=["ruc", "segmento", "periodo"], how="left")

    # --- Dimensiones ---------------------------------------------------------
    geo = (bodegas[bodegas.es_distribuidor]
           .groupby("ruc")
           .agg(region=("region", "first"), provincia=("provincia", "first"),
                ciudad=("ciudad", "first"), canal=("canal", "first"),
                categorizacion=("categorizacion", "first"),
                n_bodegas=("bodega_id", "nunique")).reset_index())
    p = p.merge(geo, on="ruc", how="left")
    p = p.merge(cupos[["ruc", "cupo_valor", "cupo_stock", "cupo_neto"]],
                on="ruc", how="left")

    # --- Calendario ----------------------------------------------------------
    p = pd.concat([p, marcar_campanias(p["periodo"])], axis=1)
    p["dia_semana"] = p["periodo"].dt.dayofweek
    p["dia_mes"] = p["periodo"].dt.day
    p["es_finde"] = p["dia_semana"].isin([5, 6]).astype(int)

    # --- Historia del target (siempre mirando hacia atras) -------------------
    p = p.sort_values(["ruc", "segmento", "periodo"]).reset_index(drop=True)
    g = p.groupby(["ruc", "segmento"], observed=True)
    for l in (1, 2, 3):
        p[f"dev_u_lag{l}"] = g["dev_u"].shift(l)
        p[f"ped_u_lag{l}"] = g["ped_u"].shift(l)
    p["dev_u_mm3"] = g["dev_u"].shift(1).rolling(3, min_periods=1).mean().values
    p["dev_acum"] = g["dev_u"].cumsum() - p["dev_u"]
    p["ped_acum"] = g["ped_u"].cumsum() - p["ped_u"]
    p["tasa_dev_hist"] = p["dev_acum"] / p["ped_acum"].replace(0, np.nan)

    # --- Derivadas de negocio ------------------------------------------------
    p["brecha_sellin_sellout"] = p["sellin_m1"] - p["sellout_m1"]
    p["ratio_conversion"] = p["sellout_m1"] / p["sellin_m1"].replace(0, np.nan)
    p["doh"] = p["stock_u"] / (p["sellout_m1"] / 30).replace(0, np.nan)
    p["ratio_intra_ped"] = p["intra_u"] / p["ped_u"].replace(0, np.nan)

    return p.drop(columns=["mes"])


def diagnostico_intermitencia(p: pd.DataFrame, target: str = "dev_u") -> pd.DataFrame:
    """Clasificacion de Syntetos-Boylan por serie: ADI y CV cuadrado.

    ADI = intervalo medio entre demandas; CV2 = varianza relativa de los
    valores no nulos. Determinan si la serie es modelable y con que familia.
    """
    filas = []
    for (ruc, seg), g in p.groupby(["ruc", "segmento"], observed=True):
        y = g[target].to_numpy()
        nz = y[y > 0]
        adi = len(y) / len(nz) if len(nz) else np.inf
        cv2 = (nz.std() / nz.mean()) ** 2 if len(nz) > 1 and nz.mean() else 0.0
        if not len(nz):
            clase = "sin demanda"
        elif adi < 1.32 and cv2 < 0.49:
            clase = "suave"
        elif adi < 1.32:
            clase = "erratica"
        elif cv2 < 0.49:
            clase = "intermitente"
        else:
            clase = "grumosa"
        filas.append({"ruc": ruc, "segmento": seg, "periodos": len(y),
                      "no_nulos": len(nz), "densidad": len(nz) / len(y),
                      "ADI": adi, "CV2": cv2, "clase": clase})
    return pd.DataFrame(filas).sort_values("densidad", ascending=False)
