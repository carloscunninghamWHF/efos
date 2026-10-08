"""EFOS v0.4 Pressure & Constraint Engine.

EVENT mode uses observed event/context proxies only. 360 mode enriches selected
pass events with snapshot lane-closure geometry when a valid freeze frame is
available. Tracking/TTI is intentionally not inferred here.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from config_loader import get_thresholds, get_weights, get_parameters


def _clip01(x):
    if x is None or pd.isna(x):
        return np.nan
    return float(np.clip(float(x), 0.0, 1.0))


def _weighted_available(values: dict, weights: dict) -> float:
    pairs=[(float(weights.get(k,0.0)), float(v)) for k,v in values.items() if v is not None and not pd.isna(v)]
    denom=sum(w for w,_ in pairs)
    if denom <= 0:
        return 0.0
    return float(np.clip(sum(w*v for w,v in pairs)/denom,0,1))


def _boundary_constraint(y, width=80.0):
    if y is None or pd.isna(y): return np.nan
    y=float(y); d=min(max(y,0.0), max(width-y,0.0))
    return float(np.clip(1.0-d/(width/2.0),0,1))


def _nearby_pressure(events: pd.DataFrame, row, window_s: float) -> float:
    """Binary observed opponent Pressure event around an on-ball action."""
    if "timestamp_seconds" not in events or "team" not in events: return 0.0
    t=float(row.get("timestamp_seconds", np.nan))
    if np.isnan(t): return 0.0
    mid=str(row.get("match_id")); team=row.get("team")
    cand=events[(events["match_id"].astype(str)==mid) & events["event_type"].eq("Pressure") & events["team"].ne(team)]
    if cand.empty: return 0.0
    dt=(pd.to_numeric(cand["timestamp_seconds"],errors="coerce")-t).abs()
    return float(dt.le(window_s).any())


def _defr_component(row):
    vals=[]
    for c in ["defensive_responsibility_probability_sum", "defensive_responsibility_pressure_like", "defensive_responsibility_interception_like"]:
        if c in row.index and not pd.isna(row[c]): vals.append(float(row[c]))
    if not vals: return np.nan
    # Export semantics can differ by field; aggregate probabilities are clipped,
    # never interpreted as physical pressing intensity.
    return float(np.clip(max(vals),0,1))


def _control_constraint(row):
    if "control_degree" not in row.index or pd.isna(row["control_degree"]): return np.nan
    x=float(row["control_degree"])
    if x>1: x/=100.0
    return float(np.clip(1-x,0,1))


def _point_segment_distance(px, py, ax, ay, bx, by):
    vx,vy=bx-ax,by-ay; wx,wy=px-ax,py-ay
    denom=vx*vx+vy*vy
    if denom<=1e-12: return math.hypot(px-ax,py-ay)
    t=max(0.0,min(1.0,(wx*vx+wy*vy)/denom))
    cx,cy=ax+t*vx,ay+t*vy
    return math.hypot(px-cx,py-cy)


def lane_closure_from_360(row, frame: dict|None, sigma: float=3.0) -> float:
    """Snapshot geometric lane-closure proxy for passes only.

    Requires start/end coordinates and at least one non-teammate player in the
    360 freeze frame. This is *not* TTI because velocity/orientation are absent.
    """
    if not frame or row.get("event_type")!="Pass": return np.nan
    coords=[row.get("location_x"),row.get("location_y"),row.get("end_location_x"),row.get("end_location_y")]
    if any(pd.isna(v) for v in coords): return np.nan
    ax,ay,bx,by=map(float,coords)
    blockers=[]
    for p in frame.get("freeze_frame",[]) or []:
        if p.get("teammate") is True: continue
        loc=p.get("location")
        if not loc or len(loc)<2: continue
        d=_point_segment_distance(float(loc[0]),float(loc[1]),ax,ay,bx,by)
        blockers.append(math.exp(-(d*d)/(2*sigma*sigma)))
    if not blockers: return np.nan
    closure=1.0
    for b in blockers: closure*=1.0-b
    return float(np.clip(1.0-closure,0,1))


def _pressure_time_cache(events: pd.DataFrame) -> dict:
    cache={}
    if events.empty or "timestamp_seconds" not in events: return cache
    pr=events[events["event_type"].eq("Pressure")]
    for (mid,team),g in pr.groupby(["match_id","team"],dropna=False):
        arr=np.sort(pd.to_numeric(g["timestamp_seconds"],errors="coerce").dropna().to_numpy(dtype=float))
        cache[(str(mid),team)]=arr
    return cache

def _nearby_from_cache(cache: dict, match_id, team, t, window_s: float) -> float:
    if t is None or pd.isna(t): return 0.0
    arrays=[a for (mid,tm),a in cache.items() if mid==str(match_id) and tm!=team and len(a)]
    if not arrays: return 0.0
    t=float(t)
    for arr in arrays:
        i=np.searchsorted(arr,t)
        if i<len(arr) and abs(arr[i]-t)<=window_s: return 1.0
        if i>0 and abs(arr[i-1]-t)<=window_s: return 1.0
    return 0.0

def build_pressure_context(events: pd.DataFrame, frames_360: dict|None=None) -> pd.DataFrame:
    """Annotate every event with pressure/constraint components and PCI [0,1].

    The EVENT layer is vectorized so league-scale files stay practical.
    """
    d=events.copy()
    if d.empty:
        return d.assign(direct_pressure=pd.Series(dtype=float), nearby_pressure=pd.Series(dtype=float),
                        boundary_constraint=pd.Series(dtype=float), defensive_responsibility=pd.Series(dtype=float),
                        control_constraint=pd.Series(dtype=float), lane_closure=pd.Series(dtype=float),
                        reachability=pd.Series(dtype=float), tti=pd.Series(dtype=float), pci=pd.Series(dtype=float),
                        pressure_source=pd.Series(dtype=str))
    th=get_thresholds()["pressure_engine"]
    weights=get_weights()["pressure_context_weights"]
    width=float(get_parameters()["pitch"]["width_m"])
    pressure_window=float(th["event_pressure"]["pressure_event_window_seconds"])
    sigma=float(th["lane_closure"]["defender_distance_sigma"])
    frames_360=frames_360 or {}

    # 1) Direct pressure (observed StatsBomb flag).
    if "under_pressure" in d:
        d["direct_pressure"]=d["under_pressure"].fillna(False).astype(bool).astype(float)
    else:
        d["direct_pressure"]=0.0

    # 2) Opponent Pressure event within configured temporal window, vectorized by match/team.
    d["nearby_pressure"]=0.0
    if {"match_id","team","event_type","timestamp_seconds"}.issubset(d.columns):
        times_all=pd.to_numeric(d["timestamp_seconds"],errors="coerce")
        for mid,g in d.groupby("match_id",sort=False):
            teams=g["team"].dropna().unique().tolist()
            for team in teams:
                idx=g.index[g["team"].eq(team)]
                opp_pr=g[g["team"].ne(team) & g["event_type"].eq("Pressure")]
                arr=np.sort(pd.to_numeric(opp_pr["timestamp_seconds"],errors="coerce").dropna().to_numpy(dtype=float))
                if not len(arr) or not len(idx): continue
                tv=times_all.loc[idx].to_numpy(dtype=float)
                valid=~np.isnan(tv); vals=np.zeros(len(tv),dtype=float)
                q=tv[valid]; pos=np.searchsorted(arr,q)
                right=np.where(pos<len(arr),arr[np.minimum(pos,len(arr)-1)],np.inf)
                left=np.where(pos>0,arr[np.maximum(pos-1,0)],-np.inf)
                dist=np.minimum(np.abs(right-q),np.abs(q-left))
                vals[valid]=(dist<=pressure_window).astype(float)
                d.loc[idx,"nearby_pressure"]=vals

    # 3) Boundary constraint.
    if "location_y" in d:
        y=pd.to_numeric(d["location_y"],errors="coerce")
        dist=np.minimum(y, width-y)
        d["boundary_constraint"]=(1.0-dist/(width/2.0)).clip(0,1)
    else:
        d["boundary_constraint"]=np.nan

    # 4) DefR: preserve semantics as responsibility proxy, not physical intensity.
    defr_cols=[c for c in ["defensive_responsibility_probability_sum","defensive_responsibility_pressure_like","defensive_responsibility_interception_like"] if c in d]
    if defr_cols:
        tmp=pd.concat([pd.to_numeric(d[c],errors="coerce") for c in defr_cols],axis=1)
        d["defensive_responsibility"]=tmp.max(axis=1,skipna=True).clip(0,1)
        d.loc[tmp.notna().sum(axis=1).eq(0),"defensive_responsibility"]=np.nan
    else:
        d["defensive_responsibility"]=np.nan

    # 5) Control constraint.
    if "control_degree" in d:
        c=pd.to_numeric(d["control_degree"],errors="coerce")
        c=c.where(c<=1,c/100.0)
        d["control_constraint"]=(1.0-c).clip(0,1)
    else:
        d["control_constraint"]=np.nan

    # Weighted mean over available EVENT components only.
    component_map={
        "direct_pressure":"direct_pressure",
        "nearby_pressure":"nearby_pressure",
        "boundary_constraint":"boundary_constraint",
        "defensive_responsibility":"defensive_responsibility",
        "control_constraint":"control_constraint",
    }
    num=pd.Series(0.0,index=d.index); den=pd.Series(0.0,index=d.index)
    for key,col in component_map.items():
        w=float(weights.get(key,0.0)); v=pd.to_numeric(d[col],errors="coerce")
        ok=v.notna(); num.loc[ok]+=w*v.loc[ok]; den.loc[ok]+=w
    d["pci"]=(num/den.replace(0,np.nan)).fillna(0.0).clip(0,1)

    # 360 enrichment is sparse and therefore only loops over actually available frame ids.
    d["lane_closure"]=np.nan; d["reachability"]=np.nan; d["tti"]=np.nan
    d["pressure_source"]="EVENT_PROXY"
    if frames_360 and th["lane_closure"].get("enabled",True) and "event_id" in d:
        by_id={str(v):i for i,v in d["event_id"].items()}
        for event_id,frame in frames_360.items():
            i=by_id.get(str(event_id))
            if i is None: continue
            lane=lane_closure_from_360(d.loc[i],frame,sigma=sigma)
            if pd.isna(lane): continue
            d.at[i,"lane_closure"]=lane
            d.at[i,"pci"]=float(np.clip(0.8*d.at[i,"pci"]+0.2*lane,0,1))
            d.at[i,"pressure_source"]="360_SNAPSHOT"
    return d
