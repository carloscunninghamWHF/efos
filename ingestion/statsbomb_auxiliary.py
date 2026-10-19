"""Preserve observational rows hidden by StatsBomb-wide event deduplication.

These are NOT StatsBomb 360 data: shot freeze frames depict shot-time players
only, and formation rows indicate listed participants, not live positioning.
Both tables retain their original event identifiers for traceability.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SHOT_FRAME_FIELDS = ["match_id", "id", "freeze_frame_player_id", "freeze_frame_player_name",
                     "freeze_frame_player_position_id", "freeze_frame_player_position_name",
                     "freeze_frame_teammate", "freeze_frame_x", "freeze_frame_y"]
FORMATION_FIELDS = ["match_id", "id", "event_type_name", "formation_player_id", "formation_player_name",
                    "formation_position_id", "formation_position_name", "formation_jersey_number"]


def _empty(fields):
    return pd.DataFrame(columns=["event_id" if x == "id" else x for x in fields])


def extract_statsbomb_auxiliary(paths, match_ids=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract unique player rows for shots and lineups from raw wide CSVs.

    Rows are not interpolated, turned into generic 360 or counted as new events.
    """
    shot_frames = []
    formation_rows = []
    accepted = {str(x) for x in match_ids} if match_ids is not None else None
    for path in paths:
        path = Path(path)
        header = set(pd.read_csv(path, nrows=0).columns)
        for fields, anchor, target in (
            (SHOT_FRAME_FIELDS, "freeze_frame_x", shot_frames),
            (FORMATION_FIELDS, "formation_player_name", formation_rows),
        ):
            if anchor not in header or not {"match_id", "id"}.issubset(header):
                continue
            present = [name for name in fields if name in header]
            table = pd.read_csv(path, usecols=present, low_memory=False)
            if accepted is not None:
                table = table.loc[table["match_id"].astype(str).isin(accepted)]
            table = table.loc[table[anchor].notna()].copy()
            if table.empty:
                continue
            table["match_id"] = table["match_id"].astype(str)
            table = table.rename(columns={"id": "event_id"})
            target.append(table)

    def consolidate(items, fields):
        if not items:
            return _empty(fields)
        return pd.concat(items, ignore_index=True).drop_duplicates().reset_index(drop=True)

    frames = consolidate(shot_frames, SHOT_FRAME_FIELDS)
    formations = consolidate(formation_rows, FORMATION_FIELDS)
    return frames, formations
