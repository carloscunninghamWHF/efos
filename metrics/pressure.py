"""Pressure metric summaries for EFOS v0.4.

Two perspectives are supported:
- faced: actions performed by the focal team (constraint experienced)
- imposed: opponent actions (constraint context generated while focal team defends)

"imposed" is still an event-level contextual proxy, not physical pressing intensity.
"""
from __future__ import annotations
import pandas as pd

COMPONENTS=["direct_pressure","nearby_pressure","boundary_constraint","defensive_responsibility","control_constraint","lane_closure"]


def summarize_pressure_context(pc: pd.DataFrame, focal_team: str, perspective: str="faced") -> dict:
    empty={"perspective":perspective,"n_actions":0,"mean_pci":0.0,"high_pressure_rate":0.0,"lane_closure_coverage":0.0,"components":{}}
    if pc is None or pc.empty: return empty
    if perspective=="imposed":
        e=pc[pc["team"].ne(focal_team)]
    else:
        e=pc[pc["team"].eq(focal_team)]
    if e.empty: return empty
    pci=pd.to_numeric(e["pci"],errors="coerce")
    components={}
    for c in COMPONENTS:
        if c not in e: continue
        s=pd.to_numeric(e[c],errors="coerce")
        components[c]={"mean":float(s.mean()) if s.notna().any() else None,"coverage":float(s.notna().mean())}
    lane=components.get("lane_closure",{})
    return {
        "perspective":perspective,"n_actions":int(len(e)),"mean_pci":float(pci.mean()),"high_pressure_rate":float(pci.ge(.60).mean()),
        "lane_closure_coverage":float(lane.get("coverage",0.0) or 0.0),"components":components,
    }
