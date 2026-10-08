"""EFOS v0.4 Engine Stability Index.
Transparent, auditable baselines. Scores are descriptive hypotheses until calibrated.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from config_loader import get_weights
from metrics.hps import compute_hps


def _clip(x):
    if x is None or pd.isna(x): return 0.0
    return float(np.clip(x,0,100))

def _safe_mean(s,default=0.0):
    s=pd.to_numeric(s,errors='coerce').dropna(); return float(s.mean()) if len(s) else default


def compute_dimensions(events: pd.DataFrame, focal_team: str, transitions: pd.DataFrame|None=None, pressure_context: pd.DataFrame|None=None) -> dict:
    e=events[events['team'].eq(focal_team)].copy()
    if e.empty: return {k:0.0 for k in ['OC','HPS','RPS','DS','DER']}
    spatial=[]
    for c in ['location_x','location_y']:
        if c in e:
            s=pd.to_numeric(e[c],errors='coerce').dropna()
            if len(s)>1:
                denom=120.0 if c.endswith('_x') else 80.0
                spatial.append(max(0.0,1.0-min(1.0,float(s.std())/(denom/2))))
    compact=np.mean(spatial) if spatial else 0.5
    control=_safe_mean(e['control_degree']) if 'control_degree' in e else compact
    if control>1: control/=100.0
    OC=_clip(100*(0.7*compact+0.3*np.clip(control,0,1)))

    HPS,_,_=compute_hps(events,focal_team,pressure_context)

    vulnerable=e[pd.to_numeric(e.get('location_x',pd.Series(index=e.index,dtype=float)),errors='coerce')<40]
    if len(vulnerable):
        loss=vulnerable['outcome_name'].fillna('').isin(['Incomplete','Out','Lost']).mean() if 'outcome_name' in vulnerable else 0.0
        RPS=_clip(100*(1-float(loss)))
    else: RPS=0.0

    passes=e[e['event_type'].eq('Pass')] if 'event_type' in e else e.iloc[0:0]
    if len(passes) and 'pass_success_probability' in passes:
        p=pd.to_numeric(passes['pass_success_probability'],errors='coerce')
        actual=(~passes['outcome_name'].fillna('').isin(['Incomplete','Out'])).astype(float) if 'outcome_name' in passes else pd.Series(1.0,index=passes.index)
        valid=p.notna(); DS=_clip(100*(1-float((actual[valid]-p[valid]).abs().mean()))) if valid.any() else 0.0
    else: DS=0.0

    if transitions is not None and len(transitions):
        t=transitions[transitions['team_lost'].eq(focal_team)]; rt=pd.to_numeric(t.get('response_time_s'),errors='coerce').dropna()
        DER=_clip(100*np.exp(-float(rt.mean())/5.0)) if len(rt) else 0.0
    else: DER=0.0
    return {'OC':OC,'HPS':HPS,'RPS':RPS,'DS':DS,'DER':DER}


def _esi_weights():
    raw=get_weights()['esi_weights']
    return {'OC':raw['organizational_cohesion'],'HPS':raw['high_pressure_stability'],
            'RPS':raw['risk_processing_stability'],'DS':raw['decision_stability'],
            'DER':raw['dynamic_equilibrium_response']}


def compute_esi(dimensions: dict,weights:dict|None=None)->float:
    weights=weights or _esi_weights(); total=sum(float(weights.get(k,0))*float(dimensions.get(k,0)) for k in weights)
    denom=sum(float(v) for v in weights.values()) or 1.0; return _clip(total/denom)


def esi_by_context(events,focal_team,transitions=None,pressure_context=None):
    out=[]
    for state in ['winning','drawing','losing']:
        g=events[events.get('score_state','').eq(state)] if 'score_state' in events else events.iloc[0:0]
        tr=transitions[transitions['score_state'].eq(state)] if transitions is not None and len(transitions) and 'score_state' in transitions else transitions
        pc=pressure_context[pressure_context.get('score_state','').eq(state)] if pressure_context is not None and len(pressure_context) and 'score_state' in pressure_context else None
        d=compute_dimensions(g,focal_team,tr,pc)
        out.append({'score_state':state,**d,'ESI':compute_esi(d),'n_events':len(g[g.team.eq(focal_team)]) if len(g) else 0})
    return pd.DataFrame(out)
