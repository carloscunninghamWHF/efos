"""Last Action Participation (LAP) baseline for final-third critical sequences."""
from __future__ import annotations
import pandas as pd

def compute_lap(events: pd.DataFrame, focal_team: str, final_third_x: float=80.0) -> pd.DataFrame:
    e=events[(events.team==focal_team) & (pd.to_numeric(events.location_x,errors='coerce')>final_third_x)].copy()
    if e.empty or 'player' not in e: return pd.DataFrame(columns=['player','critical_actions','final_third_actions','LAP','xG','xA'])
    critical_types={'Pass','Carry','Shot','Ball Receipt*','Dribble'}
    e['critical']=e.event_type.isin(critical_types)
    rows=[]
    for player,g in e.groupby('player',dropna=True):
        n=len(g); crit=int(g.critical.sum())
        xg=pd.to_numeric(g.get('statsbomb_xg',0),errors='coerce').fillna(0).sum() if 'statsbomb_xg' in g else 0.0
        xa=pd.to_numeric(g.get('xA',0),errors='coerce').fillna(0).sum() if 'xA' in g else 0.0
        rows.append({'player':player,'critical_actions':crit,'final_third_actions':n,'LAP':100*crit/max(n,1),'xG':float(xg),'xA':float(xa)})
    return pd.DataFrame(rows).sort_values('LAP',ascending=False)
