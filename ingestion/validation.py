"""Data-integrity gates for EFOS Sprint 2."""
from __future__ import annotations
import pandas as pd


def deduplicate_events(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """One analytical row per event_id when IDs exist; preserves rows with null IDs."""
    if df.empty or "event_id" not in df.columns:
        return df.copy(), {"duplicates_removed": 0}
    mask = df["event_id"].notna()
    duplicated = mask & df.duplicated(subset=["match_id", "event_id"], keep="first")
    out = df.loc[~duplicated].copy().reset_index(drop=True)
    return out, {"duplicates_removed": int(duplicated.sum())}


def validate_events(df: pd.DataFrame, expected_matches: int | None = None) -> dict:
    issues=[]
    if df.empty:
        issues.append("empty_event_table")
        return {"ok": False, "issues": issues, "n_events": 0, "n_matches": 0}
    n_matches=int(df["match_id"].nunique()) if "match_id" in df else 0
    if expected_matches is not None and n_matches != expected_matches:
        issues.append(f"expected_{expected_matches}_matches_found_{n_matches}")
    if "event_id" in df:
        nonnull=df[df.event_id.notna()]
        if nonnull.duplicated(["match_id","event_id"]).any():
            issues.append("duplicate_event_ids")
    for col,lo,hi in [("location_x",0,120),("location_y",0,80),("end_location_x",0,120),("end_location_y",0,80)]:
        if col in df:
            s=pd.to_numeric(df[col], errors="coerce").dropna()
            if ((s<lo)|(s>hi)).any(): issues.append(f"{col}_out_of_bounds")
    return {"ok": len(issues)==0, "issues": issues, "n_events": len(df), "n_matches": n_matches}
