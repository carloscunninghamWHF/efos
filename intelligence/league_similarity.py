"""Similitud técnica entre perfiles EFOS realmente calculados.

No contiene porcentajes precargados ni arquetipos ficticios. Para comparar a
un DT/equipo se requieren al menos dos perfiles de la misma liga calculados con
el mismo conjunto de ejes. Esto evita mostrar similitudes inventadas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_AXES = ["construction", "progression", "attack", "defense", "transition", "adaptation"]


def similarity(a: dict, b: dict, axes: list[str] | None = None) -> float | None:
    axes = axes or DEFAULT_AXES
    pairs = [(float(a[k]), float(b[k])) for k in axes if a.get(k) is not None and b.get(k) is not None]
    if len(pairs) < 4:
        return None
    gaps = [abs(x - y) for x, y in pairs]
    return float(np.clip(100 - np.mean(gaps), 0, 100))


def rank_similarity(selected_name: str, selected_profile: dict, reference_profiles: list[dict], axes: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for r in reference_profiles:
        if r.get("name") == selected_name:
            continue
        score = similarity(selected_profile, r.get("profile", {}), axes)
        if score is not None:
            rows.append({"entrenador": r.get("coach") or r.get("name"), "equipo": r.get("name"), "similitud": score})
    return pd.DataFrame(rows).sort_values("similitud", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(columns=["entrenador","equipo","similitud"])
