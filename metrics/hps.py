"""EFOS v0.4 High Pressure Stability (HPS v2).

Separates opponent pressure context (PCI) from the focal team's response.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from config_loader import get_thresholds, get_weights
from intelligence.pressure_context import build_pressure_context

FAIL_TYPES={"Dispossessed","Miscontrol","Error"}
FAIL_OUTCOMES={"Incomplete","Out","Lost","Unknown","Injury Clearance"}


def _retention_score(row) -> float:
    et=str(row.get("event_type", "")); outcome=str(row.get("outcome_name", ""))
    if et in FAIL_TYPES: return 0.0
    if outcome in FAIL_OUTCOMES: return 0.0
    if et=="Pass" and outcome in {"Incomplete","Out","Unknown"}: return 0.0
    # Carries/receipts without an explicit adverse outcome are retained actions.
    return 1.0


def _progression_score(row) -> float:
    x=row.get("location_x"); ex=row.get("end_location_x")
    if pd.isna(x) or pd.isna(ex): return 0.5
    delta=float(ex)-float(x)
    # 20m positive action ~= full progression contribution.
    return float(np.clip(0.5+delta/40.0,0,1))


def _value_score(row, scale: float) -> float:
    v=row.get("obv_total_net")
    if v is None or pd.isna(v): return 0.5
    return float(1/(1+np.exp(-float(v)*scale)))


def _decision_score(row) -> float:
    if row.get("event_type")!="Pass": return 0.5
    p=row.get("pass_success_probability")
    if p is None or pd.isna(p): return 0.5
    expected=float(np.clip(float(p),0,1)); actual=_retention_score(row)
    # Accuracy of decision execution relative to model expectation.
    return float(np.clip(1-abs(actual-expected),0,1))


def compute_hps(events: pd.DataFrame, focal_team: str, pressure_context: pd.DataFrame|None=None) -> tuple[float,pd.DataFrame,dict]:
    pc=pressure_context.copy() if pressure_context is not None else build_pressure_context(events)
    focal=pc[pc["team"].eq(focal_team)].copy()
    # HPS measures the focal system response while it has/contests possession;
    # off-ball pressure actions by the focal team are not response actions.
    if "possession_team" in focal.columns:
        focal=focal[focal["possession_team"].eq(focal_team)].copy()
    if focal.empty:
        return 0.0, focal, {"retention":0.0,"progression":0.0,"value_preservation":0.0,"decision_stability":0.0,"n_actions":0}
    th=get_thresholds()["pressure_engine"]["hps"]
    hw=get_weights()["hps_weights"]
    lam=float(th["pressure_weight_lambda"]); scale=float(th["obv_logistic_scale"])
    focal["retention_stability"]=focal.apply(_retention_score,axis=1)
    focal["progression_stability"]=focal.apply(_progression_score,axis=1)
    focal["value_preservation"]=focal.apply(lambda r:_value_score(r,scale),axis=1)
    focal["decision_stability_hps"]=focal.apply(_decision_score,axis=1)
    focal["pressure_weight"]=1.0+lam*pd.to_numeric(focal["pci"],errors="coerce").fillna(0).clip(0,1)
    def wmean(col):
        v=pd.to_numeric(focal[col],errors="coerce"); w=focal["pressure_weight"]
        ok=v.notna()&w.notna()
        return float(np.average(v[ok],weights=w[ok])) if ok.any() else 0.0
    comp={"retention":wmean("retention_stability"),"progression":wmean("progression_stability"),
          "value_preservation":wmean("value_preservation"),"decision_stability":wmean("decision_stability_hps")}
    total=sum(float(hw.get(k,0))*comp[k] for k in comp); denom=sum(float(hw.get(k,0)) for k in comp) or 1.0
    score=float(np.clip(100*total/denom,0,100))
    meta={**comp,"n_actions":int(len(focal)),"mean_pci":float(pd.to_numeric(focal["pci"],errors="coerce").mean())}
    return score,focal,meta
