"""Temporal/sample evolution for Coach Story.

If no match dates exist, matches are ordered by first appearance in the event file.
The report labels this explicitly as sample order, not calendar chronology.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

METRICS=["ESI","OC","HPS","RPS","DS","DER"]


def _ordered_match_ids(events: pd.DataFrame):
    if "match_date" in events.columns and events["match_date"].notna().any():
        tmp=events[["match_id","match_date"]].dropna().drop_duplicates("match_id")
        tmp["match_date"] = pd.to_datetime(tmp["match_date"], errors="coerce")
        ids=tmp.sort_values("match_date")["match_id"].astype(str).tolist()
        return ids, "calendar_date"
    return [str(x) for x in pd.unique(events["match_id"])], "dataset_order"


def analyze_temporal_evolution(events: pd.DataFrame, match_windows: pd.DataFrame) -> dict:
    if match_windows is None or match_windows.empty:
        return {"ordering":"unavailable","phases":[],"claims":[]}
    ids, ordering = _ordered_match_ids(events)
    rank={m:i for i,m in enumerate(ids)}
    w=match_windows.copy(); w["match_id"]=w["match_id"].astype(str)
    agg=w.groupby("match_id")[METRICS].mean(numeric_only=True).reset_index()
    agg["_order"]=agg["match_id"].map(rank)
    agg=agg.sort_values("_order").dropna(subset=["_order"])
    if agg.empty: return {"ordering":ordering,"phases":[],"claims":[]}
    n=len(agg); bins=np.array_split(np.arange(n),3); names=["early","middle","late"]
    phases=[]
    for name,idx in zip(names,bins):
        g=agg.iloc[idx] if len(idx) else agg.iloc[0:0]
        phases.append({"phase":name,"matches":int(len(g)),**{m:round(float(g[m].mean()),4) if len(g) else 0.0 for m in METRICS}})
    first=phases[0]; last=phases[-1]
    deltas={m:round(float(last[m]-first[m]),4) for m in METRICS}
    top=max(deltas,key=lambda k:abs(deltas[k])) if deltas else None
    direction="aumenta" if deltas.get(top,0)>0 else "disminuye"
    order_note="fecha calendario" if ordering=="calendar_date" else "orden de aparición en el dataset"
    claim=(
        f"Al dividir la muestra en tres bloques por {order_note}, el mayor cambio entre el primer y último bloque aparece en {top}: "
        f"{first.get(top,0):.2f} → {last.get(top,0):.2f} (Δ={deltas.get(top,0):+.2f}); por tanto {direction} dentro de esta partición descriptiva."
        if top else "No hay suficientes datos para describir evolución temporal."
    )
    confidence="MEDIUM" if n>=9 else "LOW"
    return {
        "ordering":ordering,"n_matches":int(n),"phases":phases,"delta_late_vs_early":deltas,
        "claims":[{"id":"temporal_evolution","section":"temporal_evolution","claim":claim,
                   "evidence":{"ordering":ordering,"phases":phases,"delta_late_vs_early":deltas},"n":int(n),
                   "source":"MATCH_WINDOWS","confidence":confidence,
                   "limitation":"Si no existen fechas de partido, la partición usa el orden del archivo y no debe presentarse como cronología calendario."}]
    }
