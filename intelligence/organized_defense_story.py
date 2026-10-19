"""EFOS — Organized Defense Story v0.5.0.

Descriptive event evidence. Defensive-action locations are NOT off-ball
positioning, line height or a verified pressing structure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ACTIONS = frozenset({"Pressure", "Ball Recovery", "Interception", "Duel", "Block", "Clearance"})
RECOVERIES = frozenset({"Ball Recovery", "Interception"})
BANDS = (("Tercio propio", 0, 40), ("Tercio medio", 40, 80), ("Tercio rival", 80, 120.0001))


def action_samples(events: pd.DataFrame, team: str) -> pd.DataFrame:
    """Defensive event sample; all frequency denominators are observed actions."""
    required = {"match_id", "team", "event_type", "location_x", "location_y"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"Faltan columnas para Defensa Organizada: {sorted(missing)}")
    d = events.loc[events["team"].eq(team) & events["event_type"].isin(ACTIONS)].copy()
    d["location_x"] = pd.to_numeric(d["location_x"], errors="coerce")
    d["location_y"] = pd.to_numeric(d["location_y"], errors="coerce")
    return d.loc[d["location_x"].between(0, 120) & d["location_y"].between(0, 80)].copy()


def build_defensive_story(events: pd.DataFrame, team: str, minimum_matches: int = 3) -> dict:
    """One auditable short narrative plus zones, match coverage and tactical caveats."""
    df = action_samples(events, team)
    matches = int(events.loc[events["team"].eq(team), "match_id"].nunique())
    n = len(df)
    result = {"method":"EFOS_DEFENSIVE_STORY_v1", "team":team,
              "matches":matches, "actions_with_coordinates":n,
              "coverage": {"valid_actions":n}, "zones":[], "summary":"",
              "claims":[], "confidence":"INSUFFICIENT" if matches < minimum_matches or n < 30 else "DESCRIPTIVE",
              "limitations":["Las posiciones son ubicaciones de eventos defensivos, NO posiciones continuas de jugadores.",
                             "No se infiere marcaje zonal/individual, altura real del bloque ni presión coordinada sin 360/tracking.",
                             "Frecuencia de intervenciones no mide por sí misma efectividad defensiva."]}
    if n == 0:
        result["summary"]="No hay intervenciones defensivas con coordenadas suficientes para describir zonas."
        return result
    rows=[]
    for label, lo, hi in BANDS:
        b=df[df["location_x"].ge(lo)&df["location_x"].lt(hi)]
        rows.append({"zone":label,"n":len(b),"pct":round(100*len(b)/n,1),
                     "matches":int(b["match_id"].nunique()),
                     "recoveries":int(b["event_type"].isin(RECOVERIES).sum()),
                     "pressures":int(b["event_type"].eq("Pressure").sum())})
    result["zones"]=rows
    ordered=sorted(rows,key=lambda z:(-z["n"],z["zone"]))
    leader=ordered[0]
    prefix=(f"En {matches} partidos se registraron {n} intervenciones defensivas con ubicación. "
            f"El {leader['pct']:.1f}% ocurrió en el {leader['zone'].lower()} "
            f"({leader['n']} acciones distribuidas en {leader['matches']} partidos).")
    if matches < minimum_matches:
        result["summary"]=prefix+" Muestra de partidos insuficiente para inferir un patrón recurrente."
    else:
        result["summary"]=prefix+" Es concentración de eventos, no altura demostrada del bloque defensivo."
    result["claims"].append({"id":"defensive_event_concentration", "section":"defensive_identity",
      "claim":result["summary"],"evidence":{"zone":leader["zone"],"n":leader["n"],
       "pct":leader["pct"],"matches_with_zone":leader["matches"],"total_actions":n,
       "matches_analyzed":matches},"n":n,"source":"STATSBOMB_EVENT_LOCATIONS",
      "confidence":"LOW" if matches < minimum_matches else "MEDIUM",
      "limitation":result["limitations"][0]})
    recovery=df[df["event_type"].isin(RECOVERIES)]
    result["recovery_count"]=int(len(recovery))
    if len(recovery):
        top=max(rows,key=lambda z:z["recoveries"])
        result["recovery_zone"]=top["zone"]
        result["recovery_zone_count"]=top["recoveries"]
        result["recovery_zone_pct"]=round(100*top["recoveries"]/len(recovery),1)
    else:
        result["recovery_zone"]=None
    pressure=df[df["event_type"].eq("Pressure")]
    result["pressure_count"]=int(len(pressure))
    result["high_pressure_share"]=(round(100*float(pressure["location_x"].ge(80).mean()),1)
                                   if len(pressure) else None)
    return result
