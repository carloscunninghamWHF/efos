"""Defensive Responsibility (DefR) helpers for StatsBomb wide CSV exports.

Preserves aggregate DefR fields on events and can normalize player-specific
wide probability columns into a long auditable table.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable, Union
import re
import pandas as pd

AGGREGATE_COLUMNS = [
    "defensive_responsibility_pressure_like",
    "defensive_responsibility_interception_like",
    "defensive_responsibility_probability_sum",
]

_PATTERN = re.compile(
    r"^(?P<defender_id>\d+)_(?P<kind>pressure_like|interception_like)_defensive_responsibility_probability$"
)


def extract_defensive_responsibility(paths: Iterable[Union[str, Path]]) -> pd.DataFrame:
    """Return long-form per-defender DefR probabilities from raw wide CSVs.

    Output columns: match_id, event_id, defender_id, responsibility_type,
    probability. Empty input/absence of player-specific columns returns an
    empty dataframe with the same schema.
    """
    rows = []
    for path in paths:
        path = Path(path)
        header = pd.read_csv(path, nrows=0).columns.tolist()
        player_cols = [c for c in header if _PATTERN.match(c)]
        if not player_cols:
            continue
        usecols = [c for c in ["match_id", "id"] if c in header] + player_cols
        frame = pd.read_csv(path, usecols=usecols, low_memory=False)
        frame = frame.drop_duplicates(subset=[c for c in ["match_id", "id"] if c in frame], keep="first")
        for c in player_cols:
            m = _PATTERN.match(c)
            s = pd.to_numeric(frame[c], errors="coerce")
            valid = s.notna() & s.gt(0)
            if not valid.any():
                continue
            sub = frame.loc[valid, ["match_id", "id"]].copy()
            sub["defender_id"] = m.group("defender_id")
            sub["responsibility_type"] = m.group("kind")
            sub["probability"] = s.loc[valid].astype(float).values
            sub = sub.rename(columns={"id": "event_id"})
            rows.append(sub)
    if not rows:
        return pd.DataFrame(columns=["match_id", "event_id", "defender_id", "responsibility_type", "probability"])
    out = pd.concat(rows, ignore_index=True)
    out["match_id"] = out["match_id"].astype(str)
    out["event_id"] = out["event_id"].astype(str)
    return out.sort_values(["match_id", "event_id", "responsibility_type", "probability"], ascending=[True, True, True, False]).reset_index(drop=True)


def responsibility_entropy(defr: pd.DataFrame) -> pd.DataFrame:
    """Shannon entropy of responsibility distribution per event/type."""
    import numpy as np
    if defr is None or defr.empty:
        return pd.DataFrame(columns=["match_id", "event_id", "responsibility_type", "responsibility_entropy"])
    d = defr.copy()
    d["probability"] = pd.to_numeric(d["probability"], errors="coerce").fillna(0).clip(lower=0)
    total = d.groupby(["match_id", "event_id", "responsibility_type"])["probability"].transform("sum")
    p = d["probability"] / total.replace(0, pd.NA)
    d["term"] = -(p * np.log(p.where(p > 0))).fillna(0)
    return d.groupby(["match_id", "event_id", "responsibility_type"], as_index=False)["term"].sum().rename(columns={"term": "responsibility_entropy"})
