"""
statsbomb_wide_csv.py
---------------------
Lee el CSV "ancho" que exporta StatsBomb (254 columnas, una o varias filas
por evento) y lo convierte al formato normalizado que consumen
run_sprint2.py / run_sprint3.py, SIN perder las métricas avanzadas
(xG, OBV, probabilidad de pase, control_degree, etc.).

Qué resuelve:
  - Junta varios archivos (p. ej. p1 + p2 = 38 partidos).
  - Quita las filas repetidas por freeze frame y alineación (1 fila = 1 evento).
  - Renombra columnas al esquema EFOS (event_type, team, player, ...).
  - Construye timestamp_seconds monótono por partido usando `period`, para que
    el añadido del 1T no se mezcle con el inicio del 2T.
  - Rellena shot_outcome / pass_outcome a partir de outcome_name.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Union

import pandas as pd

logger = logging.getLogger("efos.ingestion.statsbomb_wide_csv")

RENAME = {
    "id": "event_id",
    "event_type_name": "event_type",
    "possession_team_name": "possession_team",
    "team_name": "team",
    "player_name": "player",
}

# Columnas que se conservan del CSV ancho (si existen).
KEEP = [
    "id", "index", "match_id", "period", "timestamp", "minute", "second", "duration",
    "event_type_name", "type_name", "outcome_name", "play_pattern_name",
    "possession", "possession_team_id", "possession_team_name",
    "team_id", "team_name", "player_id", "player_name", "player_position_name",
    "location_x", "location_y", "end_location_x", "end_location_y",
    "under_pressure", "counterpress", "pass_recipient_name", "pass_length", "pass_angle",
    "pass_height_name", "pass_cross", "pass_switch", "through_ball",
    "key_pass_id", "assisted_shot_id", "body_part_name", "technique_name",
    "substituted_player_id", "substituted_player_name",
    "statsbomb_xg", "shot_execution_xg", "obv_for_net", "obv_against_net", "obv_total_net",
    "pass_success_probability", "pass_cluster_label", "duel_win_probability",
    "set_piece_phase", "attacking_direction", "control_degree", "is_transition",
    "is_controlled_possession", "possession_directness", "location_bucket",
    "defensive_responsibility_pressure_like",
    "defensive_responsibility_interception_like",
    "defensive_responsibility_probability_sum",
    "aerial_won",  # v0.4.28: duelo aéreo ganado (Perfil por fase)
]

# Minuto de inicio de cada periodo en StatsBomb (el reloj no se reinicia).
PERIOD_START_MIN = {1: 0, 2: 45, 3: 90, 4: 105, 5: 120}

BOOL_COLS = ["under_pressure", "counterpress", "pass_cross", "pass_switch", "through_ball", "aerial_won"]


def _add_monotonic_time(df: pd.DataFrame) -> pd.DataFrame:
    """timestamp_seconds = segundos reales transcurridos desde el inicio del partido."""
    start = df["period"].map(PERIOD_START_MIN).fillna(0)
    df["period_seconds"] = (df["minute"] - start) * 60 + df["second"]
    out = []
    for _, g in df.groupby("match_id", sort=False):
        g = g.sort_values(["period", "index"]).copy()
        offsets, acc = {}, 0.0
        for p in sorted(g["period"].dropna().unique()):
            offsets[p] = acc
            acc += float(g.loc[g["period"] == p, "period_seconds"].max())
        g["timestamp_seconds"] = g["period"].map(offsets) + g["period_seconds"]
        out.append(g)
    return pd.concat(out, ignore_index=True)


def load_statsbomb_wide(paths: Iterable[Union[str, Path]]) -> pd.DataFrame:
    frames = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            raise FileNotFoundError(f"No se encontró el CSV: {p}")
        header = pd.read_csv(p, nrows=0).columns
        cols = [c for c in KEEP if c in header]
        missing = [c for c in ["id", "match_id", "period", "event_type_name", "team_name"] if c not in cols]
        if missing:
            raise ValueError(f"{p.name} no parece un CSV de eventos StatsBomb (faltan {missing}).")
        df = pd.read_csv(p, usecols=cols, low_memory=False)
        logger.info("%s: %d filas, %d partidos", p.name, len(df), df["match_id"].nunique())
        frames.append(df)

    df = pd.concat(frames, ignore_index=True)
    before = len(df)
    df = df.drop_duplicates(subset=["match_id", "id"], keep="first")
    logger.info("Filas repetidas (freeze frame / alineación) eliminadas: %d", before - len(df))

    df = df.rename(columns=RENAME)
    if "outcome_name" not in df.columns:
        df["outcome_name"] = pd.NA
    for c in BOOL_COLS:
        if c in df:
            df[c] = df[c].fillna(False).astype(bool)
    df["shot_outcome"] = df["outcome_name"].where(df["event_type"] == "Shot")
    df["pass_outcome"] = df["outcome_name"].where(df["event_type"] == "Pass")
    df["match_id"] = df["match_id"].astype(str)

    df = _add_monotonic_time(df)
    df = df.sort_values(["match_id", "period", "index"]).reset_index(drop=True)
    df.attrs["n_source_rows"] = int(before)
    df.attrs["source_duplicates_removed"] = int(before - len(df))
    logger.info("Eventos únicos: %d | partidos: %d", len(df), df["match_id"].nunique())
    return df
