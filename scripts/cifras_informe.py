"""Reune en un solo archivo las cifras de datos que cita el informe, cada una con su definicion.

Lee los artefactos de `data/processed/` (datos del cliente) y escribe solo agregados, sin ningun
identificador, en `reports/cifras_informe.csv`. Asi cada numero del informe sobre volumen,
exclusiones, densidad por nivel de agregacion y tipo de RUC se puede reproducir con un comando.

    python scripts/cifras_informe.py

Definiciones que conviene tener presentes:
  * eventos: unidades que cumplen 60 dias sin haber salido del canal (el objetivo, sin agrupar).
  * densidad de un nivel: celdas (entidad x mes) con al menos una devolucion, sobre las celdas
    posibles (entidades que alguna vez registraron un evento x meses del panel).
  * tipo de RUC: por su tercer digito (regla del SRI), reponiendo el cero que Excel quita a los de 12.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd

from src import seudonimizar as S
from src.config import PROC


def fila(grupo, indicador, valor, nota=""):
    return {"grupo": grupo, "indicador": indicador, "valor": valor, "nota": nota}


def main() -> int:
    per = pd.read_parquet(PROC / "v6_periodos.parquet")
    est = pd.read_parquet(PROC / "v6_estadias.parquet", columns=["imei"])
    st = pd.read_parquet(PROC / "v6_stock.parquet", columns=["fecha", "imei"])
    desp = pd.read_parquet(PROC / "v6_despachos.parquet", columns=["fecha", "imei", "segmento"])
    panel = pd.read_parquet(PROC / "v6_panel_modelo.parquet")
    cupos = pd.read_parquet(PROC / "dim_distribuidor.parquet")
    v = per[~per.sin_despacho]
    ev = v[v.cumple]
    r: list[dict] = []

    r += [fila("volumen", "filas de inventario diario", len(st)),
          fila("volumen", "dias distintos con inventario", st.fecha.nunique(), f"{st.fecha.min():%Y-%m-%d} a {st.fecha.max():%Y-%m-%d}"),
          fila("volumen", "filas de despachos", len(desp)),
          fila("volumen", "estadias", len(est)),
          fila("volumen", "compresion inventario -> estadias (veces)", round(len(st) / len(est), 1)),
          fila("volumen", "periodos en canal", len(per)),
          fila("volumen", "periodos con despacho asociado", len(v)),
          fila("exclusion", "periodos sin despacho asociado", int(per.sin_despacho.sum()), "se excluyen del objetivo"),
          fila("exclusion", "% de periodos sin despacho", round(per.sin_despacho.mean() * 100, 1))]
    eq = desp[(desp.segmento == "EQUIPO") & desp.imei.notna()]
    desp_imei, st_imei = set(eq.imei), set(st.imei)
    r += [fila("exclusion", "IMEI de equipos despachados", len(desp_imei)),
          fila("exclusion", "IMEI despachados que nunca aparecen en el inventario", len(desp_imei - st_imei)),
          fila("exclusion", "% de IMEI despachados no vistos en inventario", round(len(desp_imei - st_imei) / len(desp_imei) * 100, 1)),
          fila("objetivo", "eventos (unidades que cumplen 60 dias)", int(v.cumple.sum())),
          fila("objetivo", "meses con eventos", ev.mes_umbral.nunique(), f"{ev.mes_umbral.min():%Y-%m} a {ev.mes_umbral.max():%Y-%m}"),
          fila("panel", "filas", len(panel)), fila("panel", "meses", panel.mes.nunique(), f"{panel.mes.min():%Y-%m} a {panel.mes.max():%Y-%m}"),
          fila("panel", "marcas", panel.marca.nunique()), fila("panel", "columnas", panel.shape[1]),
          fila("panel", "devoluciones en el panel", int(panel.devueltas.sum()), "los dos primeros meses de eventos caen por los rezagos")]

    meses = pd.date_range(panel.mes.min(), panel.mes.max(), freq="MS")
    e = ev[ev.mes_umbral.isin(meses)]
    for cols, nombre in ((["marca"], "marca x mes"), (["sku"], "SKU x mes"), (["ruc"], "distribuidor (RUC) x mes"),
                         (["ruc", "sku"], "distribuidor x SKU x mes")):
        ee = e.dropna(subset=cols)           # un evento sin RUC no se puede asignar a un distribuidor
        n = len(ee[cols].drop_duplicates())
        c = len(ee.groupby(cols + ["mes_umbral"]))
        r += [fila("densidad", f"{nombre}: entidades", n), fila("densidad", f"{nombre}: celdas con dato", c),
              fila("densidad", f"{nombre}: densidad %", round(c / (n * len(meses)) * 100, 1),
                   "" if len(ee) == len(e) else f"descarta {len(e) - len(ee):,} eventos sin {'/'.join(cols)}"),
              fila("densidad", f"{nombre}: devoluciones por celda con dato", round(len(ee) / c, 1))]
    ee = e.dropna(subset=["ruc", "sku"])
    n_ruc, n_sku = ee.ruc.nunique(), ee.sku.nunique()
    r.append(fila("densidad", "distribuidor x SKU x mes sobre la grilla completa %",
                  round(len(ee.groupby(["ruc", "sku", "mes_umbral"])) / (n_ruc * n_sku * len(meses)) * 100, 1),
                  f"{n_ruc} RUC x {n_sku} SKU x {len(meses)} meses"))
    r.append(fila("densidad", "% de eventos sin RUC (no asignables a un distribuidor)", round(e.ruc.isna().mean() * 100, 1)))

    def tipo(s: pd.Series) -> pd.Series:
        return S.ruc_tipo(s.astype("object"))

    cupos_t = tipo(cupos.ruc.astype(str))
    r += [fila("ruc", "distribuidores en el archivo de cupos", len(cupos)),
          fila("ruc", "cupos con RUC de persona natural", int((cupos_t == "persona_natural").sum()),
               "tercer digito 0-5, o cedula de 10 digitos")]
    t = tipo(v.ruc)
    r += [fila("ruc", "RUC distintos con despacho", int(v.ruc.nunique())),
          fila("ruc", "RUC de persona natural entre los receptores", int(v.loc[t == "persona_natural", "ruc"].nunique())),
          fila("ruc", "% de periodos con RUC de persona natural", round((t == "persona_natural").mean() * 100, 1)),
          fila("ruc", "% de eventos con RUC de persona natural", round((t[v.cumple] == "persona_natural").mean() * 100, 1)),
          fila("ruc", "% de periodos sin RUC", round(v.ruc.isna().mean() * 100, 1)),
          fila("ruc", "% de periodos con RUC de sociedad", round((t == "sociedad_privada").mean() * 100, 1))]

    out = pd.DataFrame(r)
    out.to_csv(RAIZ / "reports" / "cifras_informe.csv", index=False)
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
