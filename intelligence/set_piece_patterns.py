"""EFOS v0.4.9 — Set Piece Story Engine.

One accountable restart = one event, not every pass with a From Corner play pattern.
P0 is the restart; P1 is the first *recorded* event (not true physical contact);
P2 is a shot by the kicking team in the same possession within 10 s.
Coordinates in StatsBomb units 120x80. All region cutoffs are exploratory.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from intelligence.corner_engine import CornerConfig, build_corner_sequences
from config_loader import get_thresholds

KIND_CORNER = "Córners"
KIND_FREE = "Tiros libres"
KIND_THROW = "Saques laterales peligrosos"
KINDS = [KIND_CORNER, KIND_FREE, KIND_THROW]
FLANKS = ["Izquierda", "Derecha"]
SCOPE = ["A favor", "En contra"]

def _cfg(key, fallback):
    return get_thresholds().get("set_piece_story", {}).get(key, fallback)


def _corner_config():
    return CornerConfig(shot_window_seconds=float(_cfg("shot_window_seconds",10.0)),
                        p1_window_seconds=float(_cfg("p1_window_seconds",6.0)),
                        short_delivery_max_units=float(_cfg("short_delivery_max_units",15.0)),
                        min_zone_examples=int(_cfg("min_zone_examples",5)))


def _min_flank():return int(_cfg("min_flank_examples",8))
def _min_zone():return int(_cfg("min_zone_examples",5))
def _min_pattern():return int(_cfg("min_pattern_examples",5))
def _min_compare():return int(_cfg("min_context_examples",10))
def _shot_window():return float(_cfg("shot_window_seconds",10.0))
def _p1_window():return float(_cfg("p1_window_seconds",6.0))
def _danger_x():return float(_cfg("attacking_third_min_x",80.0))

INTERVENTIONS = {
    "Ball Receipt*", "Pass", "Shot", "Carry", "Carries", "Dribble", "Duel",
    "Clearance", "Interception", "Ball Recovery", "Miscontrol", "Dispossessed", "Block",
}
FIELDS = [
    "set_piece_id", "kind", "side", "flank", "match_id", "period", "possession",
    "minute", "t0", "attacking_team", "executor", "start_x", "start_y", "end_x", "end_y",
    "pass_height_name",
    "target_zone", "first_registered_player", "first_registered_team", "first_registered_event",
    "shot_generated", "shot_count", "shot_x", "shot_y", "shot_zone", "first_shooter",
    "xg", "xg_coverage", "goal", "score_state", "n_360_visible", "source", "limitations",
]


def _n(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _flank(y):
    v = _n(y)
    if not math.isfinite(v):
        return "Sin posición"
    # With attacking direction x increasing: y=0 upper sideline is attacker's left.
    # Stable across both teams only when events are attack-normalized to +x.
    return "Izquierda" if v < 40 else "Derecha"


def _zone(x0, y0, x1, y1):
    c = _corner_config()
    values = [_n(v) for v in (x0,y0,x1,y1)]
    if not all(math.isfinite(v) for v in values):
        return "Sin destino registrado"
    x0,y0,x1,y1 = values
    if math.hypot(x1-x0,y1-y0) <= c.short_delivery_max_units:
        return "Corto"
    if x1 < c.box_min_x or not c.box_min_y <= y1 <= c.box_max_y:
        return "Fuera del área"
    rel = y1 if y0 < 40 else 80-y1
    if rel < c.near_post_cut_y:
        return "Primer palo (aprox.)"
    if rel <= c.far_post_cut_y:
        return "Zona central (aprox.)"
    return "Segundo palo (aprox.)"


def _shot_zone(x, y):
    x,y = _n(x),_n(y)
    if not (math.isfinite(x) and math.isfinite(y)):
        return "Remate sin posición"
    if x < 102 or not 18 <= y <= 62:
        return "Fuera del área"
    if y < 31:
        return "Sector superior del área"
    if y > 49:
        return "Sector inferior del área"
    return "Centro del área"


def _prep(events):
    req = {"match_id", "period", "possession", "team", "event_type", "type_name", "timestamp_seconds"}
    absent = req.difference(events.columns)
    if absent:
        raise ValueError("Faltan columnas en Set Piece Story: " + ", ".join(sorted(absent)))
    e = events.copy().reset_index(drop=True)
    for col in ("event_id", "player", "minute", "score_state", "location_x", "location_y",
                "end_location_x", "end_location_y", "statsbomb_xg", "shot_outcome", "pass_height_name"):
        if col not in e:
            e[col] = np.nan
    if "outcome_name" not in e:
        e["outcome_name"] = np.nan
    e["_t"] = pd.to_numeric(e["timestamp_seconds"], errors="coerce")
    e["_ord"] = pd.to_numeric(e["index"],errors="coerce") if "index" in e else np.arange(len(e))
    e["_ord"] = e["_ord"].fillna(pd.Series(np.arange(len(e)),index=e.index))
    e["_match"] = e["match_id"].astype(str)
    e["_period"] = pd.to_numeric(e["period"],errors="coerce").fillna(-1)
    e["_poss"] = pd.to_numeric(e["possession"],errors="coerce").fillna(-1)
    e = e.sort_values(["_match","_period","_t","_ord"],kind="stable").reset_index(drop=True)
    e["_restart"] = (e["event_type"].eq("Pass") &
                     e["type_name"].isin(["Corner","Free Kick","Throw-in","Throw In","Throw-In"])) | (
                     e["event_type"].eq("Shot") & e["type_name"].eq("Free Kick"))
    return e


def _event_context(e, focal_team):
    all_matches = set(e.loc[e["team"].eq(focal_team),"_match"])
    e = e[e["_match"].isin(all_matches)]
    return e, {k:v.reset_index(drop=True) for k,v in e.groupby(["_match","_period","_poss"],sort=False)}


def _follow(group, t0, order, window=None):
    if group is None or group.empty:
        return pd.DataFrame()
    if window is None:window=_shot_window()
    later = group[(group["_t"] >= t0) & ((group["_t"] > t0) | (group["_ord"] > order))].copy()
    later = later.sort_values(["_t","_ord"],kind="stable")
    restarts = later[later["_restart"]]
    if len(restarts):
        first = restarts.iloc[0]
        later = later[(later["_t"] < first["_t"]) | ((later["_t"] == first["_t"]) & (later["_ord"] < first["_ord"]))]
    return later[later["_t"] <= t0+window]


def _attacking_shots(follow, attacker):
    if follow.empty:
        return follow
    return follow[follow["event_type"].eq("Shot") & follow["team"].eq(attacker)]


def _shot_values(shots):
    if shots.empty:
        return {"shot_generated":False,"shot_count":0,"shot_x":math.nan,"shot_y":math.nan,
                "shot_zone":None,"first_shooter":None,"xg":0.0,"xg_coverage":"NO_SHOT","goal":False}
    first = shots.iloc[0]
    vals = pd.to_numeric(shots["statsbomb_xg"],errors="coerce")
    return {
        "shot_generated":True,"shot_count":int(len(shots)),
        "shot_x":_n(first["location_x"]),"shot_y":_n(first["location_y"]),
        "shot_zone":_shot_zone(first["location_x"],first["location_y"]),
        "first_shooter":first.get("player"),
        "xg":float(vals.sum()) if vals.notna().all() else math.nan,
        "xg_coverage":"COMPLETE" if vals.notna().all() else "MISSING_SHOT_XG",
        "goal":bool(shots["shot_outcome"].eq("Goal").any() | shots["outcome_name"].eq("Goal").any()),
    }


def _first_intervention(follow, t0):
    f = follow[(follow["_t"] <= t0 + _p1_window()) & (follow["event_type"].isin(INTERVENTIONS))]
    if f.empty:
        return {"first_registered_player":None,"first_registered_team":None,"first_registered_event":None}
    first = f.iloc[0]
    return {"first_registered_player":first["player"],"first_registered_team":first["team"],
            "first_registered_event":first["event_type"]}


def build_set_piece_sequences(events:pd.DataFrame, focal_team:str, corners:pd.DataFrame|None=None)->pd.DataFrame:
    """Standardized event trace. For corners, reuse authoritative Corner Engine measurements."""
    e = _prep(events)
    if e.empty:
        return pd.DataFrame(columns=FIELDS)
    e,groups = _event_context(e,focal_team)
    if corners is None:
        corners = build_corner_sequences(events, focal_team, config=_corner_config())
    # Match corner trace back to P0 event UUID (or ID generated from original row when missing).
    corner_lookup = {str(r["corner_id"]):r for _,r in corners.iterrows()}
    kick_events = e[e["_restart"] & e["_t"].notna() & e["_period"].ne(-1) & e["_poss"].ne(-1)]
    rows=[]
    for _,kick in kick_events.iterrows():
        kind = KIND_CORNER if kick["type_name"]=="Corner" else (KIND_FREE if kick["type_name"]=="Free Kick" else KIND_THROW)
        if kind==KIND_THROW and (_n(kick["location_x"])<_danger_x() or not math.isfinite(_n(kick["location_x"]))):
            continue
        # Exclude routine deep free kicks: only attacking-third set pieces enter the story.
        if kind==KIND_FREE and (_n(kick["location_x"])<_danger_x() or not math.isfinite(_n(kick["location_x"]))):
            continue
        attacker = str(kick["team"])
        flank = _flank(kick["location_y"])
        side = "A favor" if attacker==focal_team else "En contra"
        eid = kick["event_id"]
        eid = str(eid) if pd.notna(eid) else f"{kick['_match']}_{int(kick['_ord'])}"
        grouped = groups.get((kick["_match"],kick["_period"],kick["_poss"]))
        follow = _follow(grouped,float(kick["_t"]),float(kick["_ord"]))
        shots = _attacking_shots(follow,attacker)
        measurements = _shot_values(shots)
        p1 = _first_intervention(follow,float(kick["_t"]))
        if kind==KIND_CORNER:
            record = corner_lookup.get(eid)
            if record is None:
                # Do not manufacture a rival definition of corners when the canonical engine excluded P0.
                continue
            measurements.update({"shot_generated":bool(record["shot_generated"]),
                "shot_count":int(record["shot_count"]),"xg":_n(record["corner_xg"]),
                "xg_coverage":record["xg_coverage"],"goal":bool(record["goal"]),
                "first_shooter":record["first_shooter"]})
            p1 = {"first_registered_player":record["first_registered_player"],
                  "first_registered_team":record["first_registered_team"],
                  "first_registered_event":record["first_registered_event"]}
        if kick["event_type"]=="Shot":
            # A direct free kick IS its own P0 shot: not a subsequent P2 shot.
            measurements=_shot_values(pd.DataFrame([kick]))
            p1={"first_registered_player":None,"first_registered_team":None,"first_registered_event":None}
        row = dict(set_piece_id=eid,kind=kind,side=side,flank=flank,
            match_id=kick["match_id"],period=kick["period"],possession=kick["possession"],
            minute=_n(kick["minute"]),t0=float(kick["_t"]),attacking_team=attacker,
            executor=kick["player"],pass_height_name=kick.get("pass_height_name"),
            start_x=_n(kick["location_x"]),start_y=_n(kick["location_y"]),
            end_x=_n(kick["end_location_x"]),end_y=_n(kick["end_location_y"]),
            target_zone=("Tiro directo" if kick["event_type"]=="Shot" else _zone(kick["location_x"],kick["location_y"],kick["end_location_x"],kick["end_location_y"])),
            score_state=kick["score_state"],n_360_visible=(bool(record["has_360_snapshot"]) if kind==KIND_CORNER else None) if kind==KIND_CORNER else None,
            source="STATSBOMB_EVENTS",limitations="Zona estimada por coordenadas; P1 = primera intervención registrada, no contacto confirmado."
        )
        row.update(measurements);row.update(p1)
        rows.append(row)
    return pd.DataFrame(rows,columns=FIELDS)


def _int(v):
    return int(v) if v is not None and pd.notna(v) else 0


def summarize_sample(d:pd.DataFrame)->dict:
    if d.empty:
        return {"n":0,"n_matches":0,"shot_rate_pct":None,"xg_per_valid":None,"xg_coverage_pct":None,"goal_count":0}
    valid=d[d["xg_coverage"].isin(["COMPLETE","NO_SHOT"])]
    return {"n":int(len(d)),"n_matches":int(d["match_id"].nunique()),
        "shot_rate_pct":round(float(d["shot_generated"].mean())*100,1),
        "xg_per_valid":round(float(valid["xg"].mean()),3) if len(valid) else None,
        "xg_coverage_pct":round(100*len(valid)/len(d),1),"goal_count":int(d["goal"].sum())}


def narrative_findings(df:pd.DataFrame,side:str,kind:str)->list[dict]:
    """Evidence-first, 0-4 compact human insights. No ranking of one-off lucky goals."""
    d=df[(df["kind"]==kind)&(df["side"]==side)].copy() if len(df) else pd.DataFrame(columns=FIELDS)
    if d.empty:
        return [{"title":"Sin ejecuciones identificadas","detail":"No se observaron jugadas de este tipo en la selección.","status":"missing","n":0}]
    findings=[]
    for flank in FLANKS:
        f=d[(d["flank"]==flank)&~d["target_zone"].eq("Sin destino registrado")]
        n=len(f)
        if n<_min_flank():
            findings.append({"title":f"{flank}: muestra insuficiente",
                "detail":f"{n} ejecuciones con destino; se necesitan al menos {_min_flank()} para describir la distribución.",
                "status":"limited","n":n,"matches":int(f["match_id"].nunique())})
            continue
        counts=f["target_zone"].value_counts()
        winner,count=str(counts.index[0]),int(counts.iloc[0]);share=count/n
        if count<_min_zone():
            detail=f"Desde {flank.lower()} la muestra se reparte entre varias zonas ({n} destinos observados)."
            title=f"{flank}: repertorio variable"
        elif share<float(_cfg("high_destination_share",.40)):
            detail=(f"Desde {flank.lower()}, el destino más frecuente es {winner.lower()} "
                    f"({count} de {n}, {share:.0%}), sin una concentración dominante.")
            title=f"{flank}: más hacia {winner}"
        else:
            detail=f"Desde {flank.lower()}, {count} de {n} servicios ({share:.0%}) van hacia {winner.lower()}."
            title=f"{flank} → {winner}"
        m=int(f["match_id"].nunique())
        if m<3:
            detail+=f" Observado solo en {m} partido(s): hallazgo exploratorio."
        findings.append({"title":title,"detail":detail,"status":"observed" if m>=3 else "limited",
                         "n":n,"matches":m,"numerator":count,"share_pct":round(100*share,1)})
    # Frequent spatial pattern across matches: (flank, zone); never infer intended tactical movement.
    pat=d[~d["target_zone"].eq("Sin destino registrado")].groupby(["flank","target_zone"]).agg(
        n=("set_piece_id","count"),matches=("match_id","nunique"),shots=("shot_generated","sum")
    ).reset_index().sort_values(["n","matches"],ascending=False)
    pat=pat[(pat["n"]>=_min_pattern())&pat["flank"].isin(FLANKS)]
    if len(pat):
        r=pat.iloc[0]
        findings.append({"title":"Patrón más repetido",
            "detail":f"{r['flank']} → {r['target_zone']}: {int(r['n'])} ejecuciones en {int(r['matches'])} partidos. "
                     "Repetición observada, no intención demostrada.",
            "status":"observed" if int(r["matches"])>=3 else "limited","n":int(r["n"]),"matches":int(r["matches"])})
    # Most productive only among sufficiently sampled patterns and with real xG coverage.
    cand=d[d["flank"].isin(FLANKS)&~d["target_zone"].eq("Sin destino registrado")]
    v=cand.assign(xg_valid=cand["xg_coverage"].isin(["COMPLETE","NO_SHOT"]))
    if len(v):
        productive=v.groupby(["flank","target_zone"]).agg(n=("set_piece_id","count"),
            nvalid=("xg_valid","sum"),xg_sum=("xg","sum"),shots=("shot_generated","sum"),
            matches=("match_id","nunique")).reset_index()
        productive=productive[(productive["n"]>=_min_pattern())&
                              (productive["nvalid"]/productive["n"]>=float(_cfg("min_xg_coverage_share",.8)))&(productive["shots"]>=2)].copy()
        if len(productive):
            productive["xg_per_valid"]=productive["xg_sum"]/productive["nvalid"]
            best=productive.sort_values(["xg_per_valid","n"],ascending=False).iloc[0]
            findings.append({"title":"Patrón con mayor xG por ejecución",
                "detail":f"{best['flank']} → {best['target_zone']}: {best['xg_per_valid']:.3f} xG por ejecución cubierta "
                         f"({int(best['n'])} jugadas, {int(best['matches'])} partidos). Comparación descriptiva.",
                "status":"observed" if int(best["matches"])>=3 else "limited",
                "n":int(best["n"]),"matches":int(best["matches"])})
    # Defensive shot origin, not marking style or zones merely receiving the service.
    if side=="En contra":
        shots=d[d["shot_generated"] & d["shot_zone"].notna() & ~d["shot_zone"].eq("Remate sin posición")]
        if len(shots)>=3:
            z=shots["shot_zone"].value_counts(); winner=str(z.index[0]);count=int(z.iloc[0])
            findings.append({"title":"Zona de remate rival observada",
                "detail":f"En {count} de {len(shots)} ejecuciones que acabaron en remate registrado, "
                         f"el primer tiro rival se produjo en {winner.lower()}. No identifica tipo de marcaje.",
                "status":"observed","n":len(shots),"matches":int(shots["match_id"].nunique())})
    if len(findings)<2:
        findings.append({"title":"Qué conviene revisar",
            "detail":"Ampliar muestra y contrastar los servicios y remates con vídeo antes de extraer conclusiones.",
            "status":"limited","n":len(d)})
    return findings


def context_finding(df:pd.DataFrame,kind:str,side:str)->dict|None:
    d=df[(df["kind"]==kind)&(df["side"]==side)]
    if d.empty or "score_state" not in d: return None
    states={s:g for s,g in d.groupby("score_state") if s in ("winning","drawing","losing") and len(g)>=_min_compare()}
    if len(states)<2:return None
    shares={s:float(g["target_zone"].eq("Corto").mean()) for s,g in states.items()}
    hi=max(shares,key=shares.get);lo=min(shares,key=shares.get)
    if shares[hi]-shares[lo]<.15:return None
    labels={"winning":"ganando","drawing":"empatando","losing":"perdiendo"}
    return {"title":"Variante según marcador","detail":f"El servicio corto aparece en {shares[hi]:.0%} de las jugadas {labels[hi]} "
            f"(n={len(states[hi])}) y {shares[lo]:.0%} {labels[lo]} (n={len(states[lo])}). Asociación observada, no causalidad.",
            "status":"observed","n":len(states[hi])+len(states[lo])}


def build_set_piece_evidence(df:pd.DataFrame,team:str)->list[dict]:
    claims=[]
    for kind in KINDS:
        for side in SCOPE:
            d=df[(df["kind"]==kind)&(df["side"]==side)]
            if d.empty:continue
            for i,f in enumerate(narrative_findings(df,side,kind)):
                if f.get("status")!="observed" or f["title"].endswith("insuficiente"):
                    continue
                claims.append({"id":f"sp_{KINDS.index(kind)}_{SCOPE.index(side)}_{i}",
                    "section":"set_piece_patterns","claim":f["detail"],
                    "evidence":{"kind":kind,"side":side,"n":f["n"],"n_matches":f.get("matches"),
                                "numerator":f.get("numerator"),"share_pct":f.get("share_pct")},
                    "n":f["n"],"source":"SET_PIECE_STORY_EVENTS",
                    "confidence":"MEDIUM" if f["n"]>=30 else "LOW",
                    "limitation":"Asociación descriptiva; zonas geométricas aproximadas, P1 no es contacto verificado. "
                                 "No permite inferir intención ni causalidad."})
            ctx=context_finding(df,kind,side)
            if ctx:
                claims.append({"id":f"sp_context_{KINDS.index(kind)}_{SCOPE.index(side)}",
                    "section":"set_piece_patterns","claim":ctx["detail"],
                    "evidence":{"kind":kind,"side":side,"n":ctx["n"]},"n":ctx["n"],
                    "source":"SET_PIECE_STORY_EVENTS","confidence":"LOW",
                    "limitation":"Muestras por contexto no controlan rivales ni selección de partido."})
    return claims


def summarize_set_pieces(df:pd.DataFrame)->dict:
    return {"version":"EFOS_SET_PIECE_STORY_v0.4.9","observations":int(len(df)),
        "by_kind":{"%s | %s"%(k,s):summarize_sample(df[(df["kind"]==k)&(df["side"]==s)])
                   for k in KINDS for s in SCOPE},
        "method":"Anclas StatsBomb por evento; corte por siguiente reinicio, posesión y 10s. "
                 "Flancos: atacando +x, y<40=izquierda, y>=40=derecha; requires confirmed direction normalization.",
        "limits":["Sin inferencia de bloqueo, marcaje, movimiento sin balón ni primer contacto físico.",
            "Los puntos representan destino REGISTRADO del pase, no punto real de caída.",
            "Saques laterales peligrosos: inicio en último tercio, x>=80 (umbral EFOS).",
            "Tiros libres analizados: sólo en último tercio ofensivo, x>=80; directo = evento tiro.",
            "Patrones productivos requieren muestras y cobertura mínimas configuradas en thresholds.yaml.",
            "Los roles izquierda/derecha requieren confirmar orientación StatsBomb y normalización a +x."]}


def analyze_set_pieces(events:pd.DataFrame,team:str,corners:pd.DataFrame|None=None):
    detail=build_set_piece_sequences(events,team,corners)
    return detail,summarize_set_pieces(detail),build_set_piece_evidence(detail,team)


def premium_story_profile(df: pd.DataFrame, kind: str, side: str) -> dict:
    """UI-ready, evidence-led story. No causal claims or invented first contacts.

    Pattern rankings compare flank + observed pass endpoint zone. The frequent
    sequence is a real observed tuple, not independent modal values stitched
    into a fictitious play. Full denominators and sample limits are returned.
    """
    d = df[(df["kind"].eq(kind)) & (df["side"].eq(side))].copy()
    result = {"n": int(len(d)), "n_matches": int(d["match_id"].nunique()),
              "headline": "", "intro": "", "by_flank": [],
              "frequent": None, "productive": None, "sequence": None}
    if d.empty:
        result["headline"] = "No hay ejecuciones registradas"
        result["intro"] = "La selección actual no contiene evidencia para este tipo de acción."
        return result

    eligible = d[d["flank"].isin(FLANKS) & ~d["target_zone"].isin(["Sin destino registrado", "Tiro directo"])].copy()
    result["valid_destinations"] = int(len(eligible))
    for flank in FLANKS:
        f = eligible[eligible["flank"].eq(flank)]
        n, nm = int(len(f)), int(f["match_id"].nunique())
        rec = {"flank": flank, "n": n, "n_matches": nm, "zone": None,
               "count": 0, "share_pct": None, "status": "insufficient"}
        if n:
            counts = f["target_zone"].value_counts()
            rec.update({"zone": str(counts.index[0]), "count": int(counts.iloc[0]),
                        "share_pct": round(100 * int(counts.iloc[0]) / n, 1)})
            if n >= _min_flank() and nm >= 3 and rec["count"] >= _min_zone():
                rec["status"] = "observed"
            elif n:
                rec["status"] = "exploratory"
        result["by_flank"].append(rec)
    if eligible.empty:
        result["headline"] = "Sin destinos de pase suficientes"
        result["intro"] = "Hay ejecuciones, pero los datos no permiten comparar de forma fiable sus destinos registrados."
        return result

    grouped = eligible.groupby(["flank", "target_zone"], dropna=False).agg(
        n=("set_piece_id", "count"), matches=("match_id", "nunique"),
        shots=("shot_generated", "sum"), goals=("goal", "sum")
    ).reset_index()
    ordered = grouped.sort_values(["n", "matches", "flank", "target_zone"],
                                  ascending=[False, False, True, True])
    frequent = ordered.iloc[0]
    sufficient = int(frequent["n"]) >= _min_pattern() and int(frequent["matches"]) >= 3
    if sufficient:
        result["frequent"] = {"flank": str(frequent["flank"]), "zone": str(frequent["target_zone"]),
                              "n": int(frequent["n"]), "n_matches": int(frequent["matches"]),
                              "shots": int(frequent["shots"]), "goals": int(frequent["goals"])}
        result["headline"] = f"{frequent['flank']} → {frequent['target_zone']}"
        result["intro"] = (f"Es el destino de servicio más repetido en esta muestra: "
                           f"{int(frequent['n'])} ejecuciones en {int(frequent['matches'])} partidos. "
                           "Es una regularidad observada, no una intención táctica demostrada.")
    else:
        result["headline"] = "Un repertorio aún por caracterizar"
        result["intro"] = (f"Se identificaron {len(eligible)} destinos, pero ninguna combinación "
                           "banda–zona alcanza la muestra mínima en tres partidos distintos.")

    eligible["_valid_xg"] = eligible["xg_coverage"].isin(["COMPLETE", "NO_SHOT"])
    eligible["_covered_xg"] = pd.to_numeric(eligible["xg"], errors="coerce").where(eligible["_valid_xg"])
    prod = eligible.groupby(["flank", "target_zone"]).agg(
        n=("set_piece_id", "count"), matches=("match_id", "nunique"),
        nvalid=("_valid_xg", "sum"), xg_sum=("_covered_xg", "sum"),
        shots=("shot_generated", "sum"), goals=("goal", "sum")
    ).reset_index()
    prod = prod[(prod["n"] >= _min_pattern()) & (prod["matches"] >= 3) &
                (prod["shots"] >= 2) & (prod["nvalid"] / prod["n"] >= float(_cfg("min_xg_coverage_share", .8)))].copy()
    if not prod.empty:
        prod["xg_mean"] = prod["xg_sum"] / prod["nvalid"]
        top = prod.sort_values(["xg_mean", "n", "flank"], ascending=[False,False,True]).iloc[0]
        result["productive"] = {"flank": str(top["flank"]), "zone": str(top["target_zone"]),
            "n": int(top["n"]), "n_matches": int(top["matches"]),
            "n_xg_valid": int(top["nvalid"]), "xg_mean": round(float(top["xg_mean"]),4),
            "shots": int(top["shots"]), "goals": int(top["goals"])}

    # An observed sequence: require all names to be present and recurrence over matches.
    # Do not synthesize A->B->C by independently taking the most frequent names.
    trace = eligible.dropna(subset=["executor", "first_registered_player", "first_shooter"])
    if not trace.empty:
        chain = trace.groupby(["flank", "target_zone", "executor", "first_registered_player", "first_shooter"]).agg(
            n=("set_piece_id", "count"), matches=("match_id", "nunique")
        ).reset_index().sort_values(["n","matches"], ascending=False)
        chain = chain[(chain["n"] >= 3) & (chain["matches"] >= 2)]
        if len(chain):
            t = chain.iloc[0]
            result["sequence"] = {k:str(t[k]) for k in ["flank","target_zone","executor","first_registered_player","first_shooter"]}
            result["sequence"].update({"n":int(t["n"]),"n_matches":int(t["matches"])})
    return result
