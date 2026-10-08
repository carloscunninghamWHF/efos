"""Reconstruct score state and continuous game context."""
from __future__ import annotations
import pandas as pd


def add_score_state(df: pd.DataFrame, focal_team: str | None = None) -> pd.DataFrame:
    out=df.copy().sort_values(["match_id","timestamp_seconds","index"], na_position="last").reset_index(drop=True)
    out["home_score_proxy"]=0; out["away_score_proxy"]=0
    out["focal_goals"]=0; out["opponent_goals"]=0; out["score_diff"]=0; out["score_state"]="drawing"
    # Event feeds in v0.2 may not contain home/away metadata, so score is reconstructed relative to focal team.
    for mid, idxs in out.groupby("match_id", sort=False).groups.items():
        fg=og=0
        for i in idxs:
            row=out.loc[i]
            et=str(row.get("event_type",""))
            # Gol normal o autogol. En StatsBomb "Own Goal For" va a nombre del equipo beneficiado.
            is_goal=(et=="Shot" and str(row.get("shot_outcome",""))=="Goal") or et=="Own Goal For"
            if is_goal:
                if focal_team is None or row.get("team")==focal_team: fg+=1
                else: og+=1
            out.at[i,"focal_goals"]=fg; out.at[i,"opponent_goals"]=og
            diff=fg-og; out.at[i,"score_diff"]=diff
            out.at[i,"score_state"]="winning" if diff>0 else ("losing" if diff<0 else "drawing")
    return out
