"""Sequence labels and N-k contextual windows."""
from __future__ import annotations
import pandas as pd

def label_phase(x):
    if pd.isna(x): return "unknown"
    if x < 36: return "build_up"
    if x <= 80: return "progression"
    return "final_third"

def build_sequences(events: pd.DataFrame) -> pd.DataFrame:
    out=events.copy()
    out["phase"]=out["location_x"].apply(label_phase)
    out["sequence_id"]=(out.groupby("match_id")["phase"].transform(lambda s: s.ne(s.shift()).cumsum())).astype("Int64")
    return out

def contextual_windows(events: pd.DataFrame, target_mask, n: int=5) -> pd.DataFrame:
    rows=[]
    for mid,g in events.groupby("match_id", sort=False):
        g=g.sort_values(["timestamp_seconds","index"], na_position="last").reset_index(drop=True)
        mask=target_mask(g) if callable(target_mask) else target_mask.reindex(g.index, fill_value=False)
        for pos in g.index[mask]:
            start=max(0,pos-n)
            target=g.loc[pos]
            for rank,j in enumerate(range(start,pos), start=-(pos-start)):
                r=g.loc[j]
                rows.append({"match_id":mid,"target_event_id":target.get("event_id"),"relative_n":rank,"event_id":r.get("event_id"),"event_type":r.get("event_type"),"team":r.get("team"),"x":r.get("location_x"),"y":r.get("location_y")})
    return pd.DataFrame(rows)
