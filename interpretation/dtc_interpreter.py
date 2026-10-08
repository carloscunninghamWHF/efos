"""Interpret Dynamic Transition Competition (DTC) state sequences."""
from __future__ import annotations
import pandas as pd


def interpret_dtc(states: pd.DataFrame, matrix: pd.DataFrame) -> dict:
    if states is None or states.empty or "state" not in states:
        return {"state_distribution":{},"transitions":[],"claims":[]}
    counts=states["state"].value_counts(); total=int(counts.sum())
    dist={str(k):{"windows":int(v),"share_pct":round(100*int(v)/max(total,1),2)} for k,v in counts.items()}
    transitions=[]
    if matrix is not None and not matrix.empty and "state" in matrix:
        for _,r in matrix.iterrows():
            origin=str(r["state"])
            for c in matrix.columns:
                if c=="state" or pd.isna(r[c]): continue
                transitions.append({"from":origin,"to":str(c),"probability":round(float(r[c]),6)})
    top=max(transitions,key=lambda x:x["probability"]) if transitions else None
    dominant=max(dist.items(),key=lambda kv:kv[1]["windows"])[0] if dist else "unknown"
    claim=f"DTC clasifica {total} ventanas. El estado más frecuente es {dominant} ({dist[dominant]['share_pct']:.1f}% de las ventanas)."
    if top:
        claim += f" La transición condicional más frecuente observada es {top['from']} → {top['to']} ({100*top['probability']:.1f}%)."
    return {"state_distribution":dist,"transitions":transitions,"claims":[{
        "id":"dtc_states","section":"dynamic_states","claim":claim,"evidence":{"state_distribution":dist,"top_transition":top},
        "n":total,"source":"DTC_ENGINE","confidence":"MEDIUM",
        "limitation":"Los estados DTC dependen de umbrales configurables de ESI/HPS/DER y todavía requieren calibración externa."
    }]}
