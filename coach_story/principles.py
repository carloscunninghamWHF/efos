"""Evidence-first Coach Story candidate principles — EFOS v0.4."""
from __future__ import annotations
import pandas as pd
import numpy as np
from config_loader import get_weights


def _confidence(freq,consistency,coverage):
    w=get_weights().get('principle_confidence_weights',{'frequency':.4,'consistency':.35,'coverage':.25})
    return float(np.clip(100*(w.get('frequency',.4)*freq+w.get('consistency',.35)*consistency+w.get('coverage',.25)*coverage),0,100))

def _append(rows,principle,series,group,coverage,evidence_n,extra=None):
    freq=float(series.mean()) if len(series) else 0.0
    consistency=max(0,1-float(group.std(ddof=0) if len(group)>1 else 0))
    row={'principle':principle,'value_pct':100*freq,'matches':int(len(group)),'confidence':_confidence(freq,consistency,coverage),'evidence_n':int(evidence_n)}
    if extra: row.update(extra)
    rows.append(row)

def detect_principles(events:pd.DataFrame,focal_team:str,transitions:pd.DataFrame|None=None,pressure_context:pd.DataFrame|None=None,traps:pd.DataFrame|None=None)->pd.DataFrame:
    e=events[events.team.eq(focal_team)].copy(); rows=[]; matches=max(e.match_id.nunique(),1)
    if transitions is not None and len(transitions):
        t=transitions[transitions.team_lost.eq(focal_team)]
        if len(t): _append(rows,'Immediate response after possession loss',t.response_within_5s.astype(float),t.groupby('match_id').response_within_5s.mean(),t.match_id.nunique()/matches,len(t),{'source':'TRANSITION_ENGINE'})
    p=e[e.event_type.eq('Pass')]
    if len(p) and 'end_location_x' in p:
        eligible=p[p.location_x<40]; hit=eligible.end_location_x>80
        if len(eligible): _append(rows,'Direct deep progression from X<40 to X>80',hit.astype(float),eligible.assign(hit=hit).groupby('match_id').hit.mean(),eligible.match_id.nunique()/matches,len(eligible),{'source':'EVENT'})
    pr=e[e.event_type.eq('Pressure')]
    if len(pr):
        high=pd.to_numeric(pr.location_x,errors='coerce')>80
        _append(rows,'High-block pressure',high.astype(float),pr.assign(hit=high).groupby('match_id').hit.mean(),pr.match_id.nunique()/matches,len(pr),{'source':'EVENT'})
    if pressure_context is not None and len(pressure_context):
        # Pressure resistance concerns focal-team actions while being constrained.
        pc=pressure_context[pressure_context.team.eq(focal_team)].copy()
        if len(pc):
            high=pd.to_numeric(pc.pci,errors='coerce').ge(.60)
            if high.any():
                retained=~pc.loc[high,'event_type'].isin(['Dispossessed','Miscontrol','Error'])
                by=pc.loc[high].assign(hit=retained.values).groupby('match_id').hit.mean()
                _append(rows,'Ball retention under high constraint',retained.astype(float),by,pc.loc[high].match_id.nunique()/matches,int(high.sum()),{'source':'EVENT_PROXY'})
        # Defensive style from opponent events: direct engagement vs spatial constraint.
        opp=pressure_context[pressure_context.team.ne(focal_team)].copy()
        if len(opp):
            direct=pd.to_numeric(opp.direct_pressure,errors='coerce').fillna(0)
            lane=pd.to_numeric(opp.get('lane_closure'),errors='coerce') if 'lane_closure' in opp else pd.Series(index=opp.index,dtype=float)
            boundary=pd.to_numeric(opp.boundary_constraint,errors='coerce').fillna(0)
            constrained=pd.to_numeric(opp.pci,errors='coerce').ge(.60)
            if constrained.any():
                idx=constrained[constrained].index
                # Direct pressure share uses all opponent actions, avoiding a tautology with high PCI.
                dh=direct.ge(.5); bm=opp.assign(hit=dh.values).groupby('match_id').hit.mean()
                _append(rows,'Direct pressure on opponent actions',dh.astype(float),bm,opp.match_id.nunique()/matches,len(opp),{'source':'EVENT_PROXY'})
                touch=boundary.loc[idx].ge(.75); bm2=opp.loc[idx].assign(hit=touch.values).groupby('match_id').hit.mean()
                _append(rows,'Boundary use within high-constraint actions',touch.astype(float),bm2,opp.loc[idx].match_id.nunique()/matches,len(idx),{'source':'EVENT_PROXY'})
                if lane.notna().any():
                    valid=lane.notna(); deny=lane[valid].ge(.55); bm3=opp.loc[valid].assign(hit=deny.values).groupby('match_id').hit.mean()
                    _append(rows,'Passing-lane denial',deny.astype(float),bm3,opp.loc[valid].match_id.nunique()/matches,int(valid.sum()),{'source':'360_SNAPSHOT'})
    if traps is not None and len(traps):
        succ=traps.successful.astype(float); by=traps.groupby('match_id').successful.mean(); coverage=traps.match_id.nunique()/matches
        _append(rows,'Defensive trap execution',succ,by,coverage,len(traps),{'source':'TRAP_ENGINE'})
    return pd.DataFrame(rows).sort_values(['confidence','evidence_n'],ascending=False).reset_index(drop=True) if rows else pd.DataFrame()
