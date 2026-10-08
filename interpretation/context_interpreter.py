"""Interpret ESI by score-state context."""
from __future__ import annotations
import pandas as pd


def interpret_context_esi(context_esi: pd.DataFrame) -> dict:
    if context_esi is None or context_esi.empty:
        return {"rows":[],"claims":[]}
    rows=[]
    for _,r in context_esi.iterrows():
        rows.append({
            "score_state":str(r.get("score_state","unknown")),
            "ESI":round(float(r.get("ESI",0)),4),"OC":round(float(r.get("OC",0)),4),"HPS":round(float(r.get("HPS",0)),4),
            "RPS":round(float(r.get("RPS",0)),4),"DS":round(float(r.get("DS",0)),4),"DER":round(float(r.get("DER",0)),4),
            "n_events":int(r.get("n_events",0)),
        })
    valid=[r for r in rows if r["n_events"]>0]
    if not valid: return {"rows":rows,"claims":[]}
    hi=max(valid,key=lambda x:x["ESI"]); lo=min(valid,key=lambda x:x["ESI"]); spread=hi["ESI"]-lo["ESI"]
    if spread < 2.0:
        # Sin intervalos de confianza, diferencias de este tamaño no deben leerse como efecto del marcador.
        claim=(
            f"El ESI contextual se mantiene prácticamente igual según el marcador: entre {lo['ESI']:.1f} ({lo['score_state']}) "
            f"y {hi['ESI']:.1f} ({hi['score_state']}), una diferencia de {spread:.1f} puntos demasiado pequeña para interpretarla."
        )
    else:
        claim=(
            f"El ESI contextual varía entre {lo['ESI']:.2f} ({lo['score_state']}) y {hi['ESI']:.2f} ({hi['score_state']}), "
            f"una amplitud descriptiva de {spread:.2f} puntos dentro de esta muestra. Esto permite observar sensibilidad al estado del marcador sin asumir causalidad."
        )
    return {"rows":rows,"spread":round(spread,4),"claims":[{
        "id":"esi_by_score_state","section":"contextual_behavior","claim":claim,"evidence":{"rows":rows,"spread":round(spread,4)},
        "n":sum(r["n_events"] for r in valid),"source":"EFOS_CONTEXT","confidence":"MEDIUM",
        "limitation":"El estado del marcador coexiste con rival, minuto, alineación y otros factores; la diferencia no identifica causalidad."
    }]}
