"""Hace importable el paquete `src` y ofrece el panel de muestra a las pruebas del modelo."""
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.modules["bottleneck"] = None      # evita un conflicto de versiones con pandas

PANEL_MUESTRA = RAIZ / "docs" / "muestra" / "panel_modelo_muestra.csv"


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    """Panel marca x mes versionado (319 filas, sin identificadores): no requiere datos del cliente."""
    return pd.read_csv(PANEL_MUESTRA, parse_dates=["mes"])
