"""
players.py
-----------
Normalización mínima de identidad de jugadores/equipos (Sprint 1).

En Sprint 1 esto se limita a limpiar espacios y mayúsculas/minúsculas
inconsistentes, para evitar que "Team A" y "team a " se traten como
entidades distintas en fusiones y agrupaciones posteriores. La
resolución de identidad más avanzada (alias, IDs cruzados entre
fuentes) se deja como extensión futura explícita.
"""
from __future__ import annotations

from typing import Optional


def normalize_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    cleaned = str(name).strip()
    return cleaned if cleaned else None


def normalize_player_column(series):
    """Aplica normalize_name a una columna (pandas Series) de nombres."""
    return series.apply(normalize_name)
