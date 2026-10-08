"""
events.py
----------
Convierte los dicts crudos producidos por ingestion.statsbomb_events en
una lista de data/schemas.event_schema.NormalizedEvent, aplicando:
  - normalización de coordenadas (normalization.coordinates)
  - cálculo de timestamp_seconds (minute*60 + second) para poder
    ordenar eventos y fusionar con PIP One
  - marca explícita has_360 según disponibilidad de freeze-frame
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from normalization.coordinates import extract_location
from data.schemas.event_schema import NormalizedEvent

logger = logging.getLogger("efos.normalization.events")


def _timestamp_seconds(minute: Optional[int], second: Optional[float]) -> Optional[float]:
    if minute is None or second is None:
        return None
    return float(minute) * 60.0 + float(second)


def normalize_events(
    raw_events: list[dict],
    freeze_frames: Optional[dict[str, dict]] = None,
) -> pd.DataFrame:
    """
    raw_events: salida de ingestion.statsbomb_events.load_statsbomb_events
    freeze_frames: salida de ingestion.statsbomb_360.load_statsbomb_360 (puede ser {})

    Devuelve un DataFrame de eventos normalizados, ordenado por
    (match_id, timestamp_seconds, index) cuando esa información existe.
    """
    freeze_frames = freeze_frames or {}
    normalized: list[dict] = []

    for ev in raw_events:
        x, y = extract_location(ev.get("location"))
        end_loc = ev.get("end_location")
        if end_loc is None:
            pass_obj = ev.get("pass") or {}
            carry_obj = ev.get("carry") or {}
            end_loc = pass_obj.get("end_location") or carry_obj.get("end_location")
        end_x, end_y = extract_location(end_loc)
        ts = _timestamp_seconds(ev.get("minute"), ev.get("second"))

        pass_info = ev.get("pass") or {}
        shot_info = ev.get("shot") or {}
        duel_info = ev.get("duel") or {}

        event_id = str(ev.get("event_id")) if ev.get("event_id") is not None else None
        has_360 = event_id is not None and event_id in freeze_frames

        record = NormalizedEvent(
            match_id=str(ev.get("match_id")),
            event_id=event_id,
            index=ev.get("index"),
            possession=ev.get("possession"),
            possession_team=ev.get("possession_team"),
            team=ev.get("team"),
            player=ev.get("player"),
            minute=ev.get("minute"),
            second=ev.get("second"),
            timestamp_seconds=ts,
            event_type=ev.get("event_type"),
            location_x=x,
            location_y=y,
            end_location_x=end_x,
            end_location_y=end_y,
            pass_outcome=pass_info.get("outcome", {}).get("name") if isinstance(pass_info.get("outcome"), dict) else None,
            shot_outcome=shot_info.get("outcome", {}).get("name") if isinstance(shot_info.get("outcome"), dict) else None,
            duel_outcome=duel_info.get("outcome", {}).get("name") if isinstance(duel_info.get("outcome"), dict) else None,
            under_pressure=bool(ev.get("under_pressure", False)),
            has_360=has_360,
        )
        normalized.append(record.model_dump())

    df = pd.DataFrame(normalized)
    if df.empty:
        logger.warning("normalize_events: no se produjo ningún evento normalizado.")
        return df

    sort_cols = [c for c in ["match_id", "timestamp_seconds", "index"] if c in df.columns]
    df = df.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    logger.info(
        "Eventos normalizados: %d | con 360: %d (%.1f%%)",
        len(df), df["has_360"].sum(),
        100.0 * df["has_360"].mean() if len(df) else 0.0,
    )
    return df
