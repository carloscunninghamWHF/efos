"""
csv_events.py
--------------
Carga eventos desde un archivo CSV "plano" (una fila = un evento) y los
convierte al MISMO formato de dict que produce
`ingestion.statsbomb_events.load_statsbomb_events`, para que el resto del
pipeline (normalization.events.normalize_events, merge con PIP One, etc.)
no tenga que saber de dónde vino el dato.

Columnas esperadas en el CSV (nombres flexibles, ver COLUMN_ALIASES):

    match_id, event_id, index, possession, possession_team, team, player,
    minute, second, event_type, x, y, pass_outcome, shot_outcome,
    duel_outcome, under_pressure, duration

Solo son estrictamente requeridas: team y event_type (igual que en
StatsBomb JSON). El resto puede faltar y se propaga como None/NaN.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import pandas as pd

logger = logging.getLogger("efos.ingestion.csv_events")

# Permite que un CSV real (exportado de otra herramienta) use nombres de
# columna ligeramente distintos sin tener que editarlo a mano.
COLUMN_ALIASES = {
    "match": "match_id",
    "matchid": "match_id",
    "id": "event_id",
    "idx": "index",
    "team_name": "team",
    "player_name": "player",
    "type": "event_type",
    "event": "event_type",
    "loc_x": "x",
    "loc_y": "y",
    "location_x": "x",
    "location_y": "y",
    "end_x": "end_location_x",
    "end_y": "end_location_y",
    "pressure": "under_pressure",
}

REQUIRED_COLUMNS = ["team", "event_type"]


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    df = df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns})
    return df


def load_csv_events(path: Union[str, Path]) -> list[dict]:
    """
    Lee un CSV de eventos y devuelve una lista de dicts en el mismo
    formato que ingestion.statsbomb_events.load_statsbomb_events, de modo
    que normalization.events.normalize_events pueda consumirlos sin cambios.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo CSV de eventos: {path}")

    df = pd.read_csv(path)
    df = _clean_columns(df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"El CSV {path.name} no tiene las columnas requeridas: {missing}. "
            f"Columnas encontradas: {list(df.columns)}"
        )

    match_id_fallback = path.stem
    parsed: list[dict] = []
    dropped = 0

    for _, row in df.iterrows():
        team = row.get("team")
        event_type = row.get("event_type")

        if pd.isna(team) or pd.isna(event_type):
            dropped += 1
            continue

        x = row.get("x")
        y = row.get("y")
        location = None
        if pd.notna(x) and pd.notna(y):
            location = [float(x), float(y)]

        record = {
            "match_id": str(row["match_id"]) if "match_id" in df.columns and pd.notna(row.get("match_id")) else match_id_fallback,
            "event_id": str(row["event_id"]) if "event_id" in df.columns and pd.notna(row.get("event_id")) else None,
            "index": int(row["index"]) if "index" in df.columns and pd.notna(row.get("index")) else None,
            "possession": int(row["possession"]) if "possession" in df.columns and pd.notna(row.get("possession")) else None,
            "possession_team": row.get("possession_team") if "possession_team" in df.columns and pd.notna(row.get("possession_team")) else None,
            "team": str(team),
            "player": str(row["player"]) if "player" in df.columns and pd.notna(row.get("player")) else None,
            "minute": int(row["minute"]) if "minute" in df.columns and pd.notna(row.get("minute")) else None,
            "second": float(row["second"]) if "second" in df.columns and pd.notna(row.get("second")) else None,
            "event_type": str(event_type),
            "location": location,
            "end_location": [float(row["end_location_x"]), float(row["end_location_y"])] if "end_location_x" in df.columns and "end_location_y" in df.columns and pd.notna(row.get("end_location_x")) and pd.notna(row.get("end_location_y")) else None,
            "pass": {"outcome": {"name": row["pass_outcome"]}} if "pass_outcome" in df.columns and pd.notna(row.get("pass_outcome")) else None,
            "shot": {"outcome": {"name": row["shot_outcome"]}} if "shot_outcome" in df.columns and pd.notna(row.get("shot_outcome")) else None,
            "duel": {"outcome": {"name": row["duel_outcome"]}} if "duel_outcome" in df.columns and pd.notna(row.get("duel_outcome")) else None,
            "duration": float(row["duration"]) if "duration" in df.columns and pd.notna(row.get("duration")) else None,
            "under_pressure": bool(row["under_pressure"]) if "under_pressure" in df.columns and pd.notna(row.get("under_pressure")) else False,
        }
        parsed.append(record)

    logger.info(
        "CSV %s: filas leídas=%d, eventos válidos=%d, descartadas=%d",
        path.name, len(df), len(parsed), dropped,
    )
    return parsed


def load_csv_pip_one(path: Union[str, Path]) -> pd.DataFrame:
    """
    Lee un CSV de eventos PIP One y lo normaliza al esquema estándar
    (mismas columnas que ingestion.pip_one.load_pip_one produce).
    Columnas esperadas: match_id, timestamp, team, player, event_type,
    zone, target_player, context, confidence, analyst_id.
    """
    from ingestion.pip_one import PIP_ONE_FIELDS

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de PIP One: {path}")

    df = pd.read_csv(path)
    df = _clean_columns(df)

    for col in PIP_ONE_FIELDS:
        if col not in df.columns:
            df[col] = None

    df = df[PIP_ONE_FIELDS].rename(columns={"timestamp": "timestamp_seconds"})
    logger.info("CSV PIP One %s: %d eventos cargados", path.name, len(df))
    return df
