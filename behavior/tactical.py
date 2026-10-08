"""MECE tactical behavior summary for Sprint 2."""
from __future__ import annotations
import pandas as pd

def tactical_summary(events: pd.DataFrame, focal_team: str) -> dict:
    e=events[events["team"]==focal_team].copy()
    passes=e[e.event_type=="Pass"]
    build=passes[passes.location_x<36]
    prog=passes[(passes.location_x<40) & (passes.end_location_x>80)] if "end_location_x" in passes else passes.iloc[0:0]
    final=e[e.location_x>80]
    pressure=e[e.event_type=="Pressure"]
    shots=e[e.event_type=="Shot"]
    return {
        "team": focal_team, "events":len(e), "build_up_passes":len(build),
        "deep_progressions":len(prog), "final_third_events":len(final),
        "pressures":len(pressure), "mean_pressure_x":float(pressure.location_x.mean()) if len(pressure) else None,
        "shots":len(shots), "goals":int((shots.shot_outcome=="Goal").sum()) if len(shots) else 0,
        "under_pressure_rate":float(e.under_pressure.fillna(False).mean()) if len(e) else 0.0,
    }
