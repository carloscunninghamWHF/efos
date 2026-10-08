"""Possession analytical objects."""
from __future__ import annotations
import pandas as pd


def build_possessions(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty: return pd.DataFrame()
    rows=[]
    keys=["match_id","possession"] if "possession" in events and events["possession"].notna().any() else ["match_id","possession_team"]
    for key,g in events.groupby(keys, dropna=False, sort=False):
        g=g.sort_values(["timestamp_seconds","index"], na_position="last")
        first=g.iloc[0]; last=g.iloc[-1]
        rows.append({
            "match_id": first.get("match_id"), "possession": first.get("possession"),
            "team": first.get("possession_team") or first.get("team"),
            "start_time": first.get("timestamp_seconds"), "end_time": last.get("timestamp_seconds"),
            "duration_s": (last.get("timestamp_seconds")-first.get("timestamp_seconds")) if pd.notna(last.get("timestamp_seconds")) and pd.notna(first.get("timestamp_seconds")) else None,
            "n_events": len(g), "start_x": first.get("location_x"), "end_x": last.get("end_location_x") if pd.notna(last.get("end_location_x")) else last.get("location_x"),
            "ended_in_shot": bool((g["event_type"]=="Shot").any()),
            "under_pressure_events": int(g.get("under_pressure", pd.Series(False,index=g.index)).fillna(False).sum()),
        })
    return pd.DataFrame(rows)
