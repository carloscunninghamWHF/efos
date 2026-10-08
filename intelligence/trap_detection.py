"""EFOS v0.4 Defensive Trap Engine.
Sequence-level detector: Pressure -> Funneling/Constraint -> Outcome.
One candidate trap is evaluated per opponent possession to avoid event overcounting.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from config_loader import get_thresholds
from intelligence.pressure_context import build_pressure_context

NEG_OUTCOMES={"Incomplete","Out","Lost","Unknown"}
NEG_TYPES={"Dispossessed","Miscontrol","Clearance","Error"}


def _touchline_distance(y,width=80.0):
    if y is None or pd.isna(y): return np.nan
    y=float(y); return min(y,width-y)


def _forced_outcome(row,long_pass_m):
    et=str(row.get("event_type","")); outcome=str(row.get("outcome_name",""))
    if outcome in NEG_OUTCOMES: return True,outcome
    if et in NEG_TYPES: return True,et
    if et=="Pass":
        x=row.get("location_x"); ex=row.get("end_location_x"); plen=row.get("pass_length")
        if not pd.isna(x) and not pd.isna(ex) and float(ex)<float(x): return True,"Backward pass"
        if plen is not None and not pd.isna(plen) and float(plen)>=long_pass_m: return True,"Forced long pass"
    obv=row.get("obv_total_net")
    if obv is not None and not pd.isna(obv) and float(obv)<0: return True,"Negative OBV"
    return False,""


def detect_traps(events:pd.DataFrame,defending_team:str,pressure_context:pd.DataFrame|None=None)->tuple[pd.DataFrame,dict]:
    pc=pressure_context.copy() if pressure_context is not None else build_pressure_context(events)
    columns=["match_id","start_event_id","possession","pressure_context","funnel_delta","constraint_delta","successful","outcome_type","pressure_source"]
    if pc.empty: return pd.DataFrame(columns=columns),{"trap_attempts":0,"successful_traps":0,"DTE":0.0,"trap_rate":0.0}
    th=get_thresholds()["pressure_engine"]["traps"]
    obs=float(th["observation_window_seconds"]); min_pci=float(th["min_pressure_context"]); min_delta=float(th["min_constraint_delta"])
    min_funnel=float(th["min_funnel_delta"]); long_pass=float(th["long_pass_m"])
    opp=pc[pc["team"].ne(defending_team)].copy().sort_values(["match_id","timestamp_seconds","index"])
    if opp.empty: return pd.DataFrame(columns=columns),{"trap_attempts":0,"successful_traps":0,"DTE":0.0,"trap_rate":0.0}
    rows=[]
    group_cols=["match_id","possession"] if "possession" in opp else ["match_id"]
    possession_count=0
    for keys,g in opp.groupby(group_cols,sort=False,dropna=False):
        possession_count+=1; g=g.sort_values(["timestamp_seconds","index"])
        high=pd.to_numeric(g["pci"],errors="coerce").ge(min_pci)
        if not high.any(): continue
        start_pos=int(np.flatnonzero(high.to_numpy())[0]); r=g.iloc[start_pos]; t0=float(r.get("timestamp_seconds",0))
        seq=g.iloc[start_pos:].copy(); seq=seq[pd.to_numeric(seq["timestamp_seconds"],errors="coerce").le(t0+obs)]
        if len(seq)<2: continue
        start_touch=_touchline_distance(r.get("location_y")); touch=pd.to_numeric(seq.get("location_y"),errors="coerce").apply(_touchline_distance)
        end_touch=float(touch.dropna().iloc[-1]) if touch.notna().any() else np.nan
        funnel=(start_touch-end_touch) if not pd.isna(start_touch) and not pd.isna(end_touch) else 0.0
        max_pci=float(pd.to_numeric(seq["pci"],errors="coerce").max()); cdelta=max_pci-float(r.get("pci",0))
        if funnel<min_funnel and cdelta<min_delta: continue
        success=False; out_type=""
        for _,q in seq.iloc[1:].iterrows():
            success,out_type=_forced_outcome(q,long_pass)
            if success: break
        rows.append({"match_id":str(r.get("match_id")),"start_event_id":str(r.get("event_id")),"possession":r.get("possession"),
                     "pressure_context":float(r.get("pci",0)),"funnel_delta":float(funnel),"constraint_delta":float(cdelta),
                     "successful":bool(success),"outcome_type":out_type,"pressure_source":r.get("pressure_source","EVENT_PROXY")})
    traps=pd.DataFrame(rows,columns=columns); attempts=len(traps); successful=int(traps["successful"].sum()) if attempts else 0
    meta={"trap_attempts":attempts,"successful_traps":successful,"DTE":100.0*successful/attempts if attempts else 0.0,
          "trap_rate":100.0*attempts/max(possession_count,1)}
    return traps,meta
