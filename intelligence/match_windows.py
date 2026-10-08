"""Build auditable match windows for contextual ESI and DTC."""
from __future__ import annotations
import pandas as pd
from metrics.esi import compute_dimensions, compute_esi

def compute_match_windows(events, focal_team, transitions=None, window_minutes=15):
    rows=[]
    e=events.copy(); e['window_order']=(pd.to_numeric(e['timestamp_seconds'],errors='coerce')//(window_minutes*60)).fillna(0).astype(int)
    for (mid,w),g in e.groupby(['match_id','window_order']):
        tr=None
        if transitions is not None and len(transitions):
            tw=(pd.to_numeric(transitions['transition_time'],errors='coerce')//(window_minutes*60))
            tr=transitions[transitions.match_id.eq(mid) & tw.eq(w)]
        d=compute_dimensions(g,focal_team,tr)
        state=g['score_state'].mode().iloc[0] if 'score_state' in g and not g['score_state'].mode().empty else 'unknown'
        rows.append({'match_id':mid,'window_order':int(w),'score_state':state,**d,'ESI':compute_esi(d),'n_events':len(g[g.team.eq(focal_team)])})
    return pd.DataFrame(rows)
