"""Hace importable el paquete `src` al ejecutar pytest desde cualquier directorio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
