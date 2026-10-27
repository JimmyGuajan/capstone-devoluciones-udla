"""Prueba de sobredispersion de Poisson y comparacion con la binomial negativa.

El modelo de tasa de conversion es una regresion de Poisson con offset de exposicion. Poisson supone
Var = media; aqui se comprueba ese supuesto sobre datos de entrenamiento y validacion (hasta dic-2025) y
se compara con la binomial negativa (NB2, Var = mu + alfa * mu^2). Despues se mide, sobre los nueve meses
de prueba, la cobertura de tres formas de construir el intervalo del volumen mensual: Poisson puro,
quasi-Poisson (phi de Pearson, la que usa el modelo) y binomial negativa.

La prueba (2026) no interviene en ningun ajuste: phi y alfa se estiman con datos anteriores a enero de 2026.

Produce `reports/sobredispersion_nb.csv`. Usa el panel de muestra versionado, asi que corre sin los datos
del cliente.

    python scripts/sobredispersion_nb.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.modules["bottleneck"] = None
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from src import modelo_final as MF
from src import panel_modelo as PM

Z = 1.96


def main() -> int:
    panel = pd.read_csv(RAIZ / "docs" / "muestra" / "panel_modelo_muestra.csv", parse_dates=["mes"])
    tr = panel[(panel.mes < MF.INICIO_PRUEBA) & (panel.en_riesgo > 0)].copy()
    off = np.log(tr.en_riesgo)

    pois = smf.glm("devueltas ~ C(marca)", data=tr, family=sm.families.Poisson(), offset=off).fit()
    phi = float(pois.pearson_chi2 / pois.df_resid)

    X = pd.get_dummies(tr.marca, drop_first=False).astype(float)
    nb = sm.NegativeBinomial(tr.devueltas.to_numpy(float), X.to_numpy(), offset=off.to_numpy()).fit(disp=0, maxiter=500)
    alfa = float(nb.params[-1])
    lr = 2 * (nb.llf - pois.llf)
    p_lr = float(0.5 * stats.chi2.sf(max(lr, 0), 1))     # alfa = 0 esta en la frontera del espacio parametrico

    # --- cobertura sobre la prueba, por mes (volumen mensual = suma de las marcas) -----------------------
    meses = sorted(panel[panel.mes >= MF.INICIO_PRUEBA].mes.unique())
    pr = PM.prediccion_tasa_conversion(panel, meses, ventana=MF.VENTANA, k=MF.K)
    m = pr.groupby("mes").agg(real=("devueltas", "sum"), pred=("prediccion", "sum"))
    m["var_nb"] = pr.assign(v=pr.prediccion + alfa * pr.prediccion ** 2).groupby("mes").v.sum()

    # phi de los 21 origenes del walk-forward (el que usa el modelo guardado)
    phi_modelo = MF.PHI if hasattr(MF, "PHI") else 8.86
    filas = []
    for nombre, sd in (("Poisson puro", np.sqrt(m.pred)),
                       (f"Quasi-Poisson (phi = {phi_modelo})", np.sqrt(phi_modelo * m.pred)),
                       (f"Binomial negativa (alfa = {alfa:.3f})", np.sqrt(m.var_nb))):
        lo, hi = m.pred - Z * sd, m.pred + Z * sd
        filas.append({"intervalo": nombre,
                      "meses_dentro": int(((m.real >= lo) & (m.real <= hi)).sum()),
                      "meses": len(m),
                      "amplitud_media": round(float((hi - lo).mean()), 0)})
    cob = pd.DataFrame(filas)

    resumen = pd.DataFrame([
        ("phi de Pearson (entrenamiento + validacion, GLM Poisson)", round(phi, 2)),
        ("filas del ajuste", len(tr)),
        ("AIC Poisson", round(float(pois.aic), 1)),
        ("AIC binomial negativa", round(float(nb.aic), 1)),
        ("alfa estimado (NB2)", round(alfa, 4)),
        ("estadistico LR (alfa = 0)", round(float(lr), 1)),
        ("p del LR (mezcla chi2)", f"{p_lr:.2e}"),
    ], columns=["indicador", "valor"])
    print(resumen.to_string(index=False)); print(); print(cob.to_string(index=False))
    out = pd.concat([resumen.assign(grupo="ajuste"),
                     cob.rename(columns={"intervalo": "indicador"}).assign(grupo="cobertura_prueba")], ignore_index=True)
    out.to_csv(RAIZ / "reports" / "sobredispersion_nb.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
