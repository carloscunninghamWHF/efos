"""Interpret Last Action Participation (LAP) without treating it as player quality."""
from __future__ import annotations
import pandas as pd


def interpret_lap(lap: pd.DataFrame, top_n: int = 8) -> dict:
    if lap is None or lap.empty:
        return {"players":[],"claims":[]}
    g=lap.copy(); g["final_third_actions"]=pd.to_numeric(g["final_third_actions"],errors="coerce").fillna(0)
    g=g.sort_values(["LAP","final_third_actions"],ascending=[False,False]).head(top_n)
    rows=[]
    for _,r in g.iterrows():
        rows.append({"player":str(r.get("player")),"LAP":round(float(r.get("LAP",0)),2),"critical_actions":int(r.get("critical_actions",0)),
                     "final_third_actions":int(r.get("final_third_actions",0)),"xG":round(float(r.get("xG",0)),4),"xA":round(float(r.get("xA",0)),4)})
    lead=rows[0] if rows else None
    claim=(f"LAP describe qué proporción de las acciones de cada jugador en último tercio pertenece a tipos definidos como críticos. "
           f"En la tabla descriptiva, {lead['player']} registra {lead['LAP']:.1f}% ({lead['critical_actions']}/{lead['final_third_actions']}) dentro de esta definición." if lead else "")
    return {"players":rows,"claims":[{
        "id":"lap_participation","section":"player_participation","claim":claim,"evidence":{"players":rows},
        "n":sum(r["final_third_actions"] for r in rows),"source":"LAP_ENGINE","confidence":"MEDIUM",
        "limitation":"LAP mide participación relativa en acciones críticas del último tercio; no es una medida de calidad, valor o ranking global del jugador."
    }]}
