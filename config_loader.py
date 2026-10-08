"""
config_loader.py
-----------------
Punto único de acceso a los archivos de configuración de EFOS
(weights.yaml, thresholds.yaml, parameters.yaml).

Principio de diseño: ningún motor debe leer un YAML directamente ni
hardcodear un peso/umbral. Todo pasa por aquí, para que un analista
sin conocimientos de programación pueda modificar el comportamiento
del sistema editando únicamente los archivos de /config.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import yaml

CONFIG_DIR = Path(__file__).parent / "config"


@lru_cache(maxsize=None)
def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_weights() -> dict:
    """Devuelve el contenido completo de weights.yaml."""
    return _load_yaml("weights.yaml")


def get_thresholds() -> dict:
    """Devuelve el contenido completo de thresholds.yaml."""
    return _load_yaml("thresholds.yaml")


def get_parameters() -> dict:
    """Devuelve el contenido completo de parameters.yaml."""
    return _load_yaml("parameters.yaml")


def get_coach_archetypes() -> dict:
    """Devuelve el contenido completo de coach_archetypes.yaml (perfiles de entrenador)."""
    return _load_yaml("coach_archetypes.yaml")


def reload_all() -> None:
    """Limpia la caché — útil en tests o cuando se edita un YAML en caliente."""
    _load_yaml.cache_clear()
