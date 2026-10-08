"""Detect changes of possession and actual elapsed-time response."""
from __future__ import annotations
import pandas as pd

def detect_transitions(events: pd.DataFrame, response_window_s: float=5.0) -> pd.DataFrame:
    rows=[]
    for mid,g in events.groupby("match_id", sort=False):
        g=g.sort_values(["timestamp_seconds","index"], na_position="last").reset_index(drop=True)
        poss=g["possession_team"].fillna(g["team"])
        changes=poss.ne(poss.shift()) & poss.shift().notna()
        if "period" in g:  # un cambio de periodo (saque inicial del 2T) no es una transición
            changes &= g["period"].eq(g["period"].shift())
        for i in g.index[changes]:
            prev_team=poss.iloc[i-1]; new_team=poss.iloc[i]; t0=g.loc[i,"timestamp_seconds"]
            if pd.isna(t0): continue
            horizon=g[(g.index>=i) & (g["timestamp_seconds"]<=t0+response_window_s)]
            old_actions=horizon[horizon["team"]==prev_team]
            response=old_actions[old_actions["event_type"].isin(["Pressure","Ball Recovery","Interception"])]
            rt=None if response.empty else float(response.iloc[0]["timestamp_seconds"]-t0)
            rows.append({"match_id":mid,"transition_time":t0,"score_state":g.loc[i].get("score_state"),"team_lost":prev_team,"team_won":new_team,"response_within_5s":rt is not None and rt<=response_window_s,"response_time_s":rt})
    return pd.DataFrame(rows)
