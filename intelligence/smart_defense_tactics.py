"""EFOS Smart Defensive Tactics v0.4.12.

Observational comparison of opponent possessions, defensive actions and players.
No intent, individual marking, spatial formations, interception causality or
counterattack classification are inferred beyond the underlying event labels.
An opponent possession is indexed by match, period, possession number and
explicit possession_team; rival actions and América's on-ball defensive actions
are kept distinct. All spatial coordinates are StatsBomb 120x80 event positions.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
from collections import defaultdict
import math
import numpy as np
import pandas as pd

SITUATIONS = (
    "Ataque posicional / otros", "Contraataque etiquetado",
    "Tras recuperación rival", "Córner rival", "Tiro libre rival",
    "Saque lateral rival",
)
DEFENSIVE_ACTIONS = frozenset({"Pressure", "Interception", "Duel", "Block", "Clearance", "Ball Recovery", "Dribbled Past"})
PLAYER_ACTIONS = DEFENSIVE_ACTIONS - {"Dribbled Past"}
RECOVERY_ACTIONS = frozenset({"Ball Recovery", "Interception"})
ONBALL_OPP = frozenset({"Pass", "Carry", "Carries", "Dribble", "Shot"})
RESTART_PATTERN = {
    "From Corner": "Córner rival", "From Free Kick": "Tiro libre rival",
    "From Throw In": "Saque lateral rival",
}
RESTART_TYPE = {"Corner": "Córner rival", "Free Kick": "Tiro libre rival", "Throw-in": "Saque lateral rival"}
MOMENTS = ("00–15", "16–30", "31–45+", "46–60", "61–75", "76–90+")


@dataclass(frozen=True)
class DefensiveConfig:
    min_matches_for_recurrence: int = 3
    min_possessions_for_claim: int = 12
    min_player_actions: int = 6
    recovery_followup_seconds: float = 5.0
    near_start_recovery_seconds: float = 4.0
    third_start_x: float = 80.0
    penalty_area_x: float = 102.0
    penalty_area_y_low: float = 18.0
    penalty_area_y_high: float = 62.0


def configured_defensive_settings() -> DefensiveConfig:
    """Configurable thresholds; defaults remain explicit when YAML is unavailable."""
    from config_loader import get_thresholds
    opts=get_thresholds().get('smart_defensive_tactics', {})
    defaults=DefensiveConfig()
    values={f.name: opts.get(f.name,getattr(defaults,f.name)) for f in fields(DefensiveConfig)}
    return DefensiveConfig(**values)


def _num(v):
    try:
        f=float(v)
        return f if math.isfinite(f) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _moment(minute):
    if math.isnan(minute):
        return "Sin minuto"
    if minute < 16: return "00–15"
    if minute < 31: return "16–30"
    if minute < 46: return "31–45+"
    if minute < 61: return "46–60"
    if minute < 76: return "61–75"
    return "76–90+"


def _scenario(opp:pd.DataFrame, config:DefensiveConfig) -> tuple[str,str]:
    """Use explicit source first. An isolated recovery is NOT called a counterattack."""
    if opp.empty:
        return "Ataque posicional / otros", "OTHER"
    head=opp.head(min(7,len(opp)))
    names=head.get("play_pattern_name",pd.Series(dtype=object)).dropna().astype(str)
    for pattern,label in RESTART_PATTERN.items():
        if names.eq(pattern).any(): return label,"PLAY_PATTERN"
    kicks=head[(head["event_type"].eq("Pass")) & (head["type_name"].isin(RESTART_TYPE))]
    if len(kicks):
        return RESTART_TYPE[str(kicks.iloc[0]["type_name"])],"RESTART_EVENT"
    if names.eq("From Counter").any(): return "Contraataque etiquetado","PLAY_PATTERN"
    first=opp.iloc[0]
    t0=_num(first["timestamp_seconds"])
    recover=opp[opp["event_type"].isin(RECOVERY_ACTIONS)]
    if len(recover) and math.isfinite(t0) and ((pd.to_numeric(recover["timestamp_seconds"],errors="coerce")-t0).between(0,config.near_start_recovery_seconds)).any():
        return "Tras recuperación rival","RECOVERY_EVENT_NOT_COUNTERATTACK"
    return "Ataque posicional / otros","NO_EXPLICIT_PATTERN"


def _zone(x):
    if not math.isfinite(x):return "Sin ubicación"
    if x < 40:return "Tercio propio de América"
    if x < 80:return "Tercio medio"
    return "Campo rival de América"


def build_smart_defense(events:pd.DataFrame, team:str, config:DefensiveConfig|None=None):
    """Return per-rival-possession and observed defender interventions tables."""
    cfg=config or DefensiveConfig()
    mandatory={"match_id","period","possession","team","event_type","timestamp_seconds"}
    if not mandatory.issubset(events.columns):
        raise ValueError("Faltan columnas para Smart Defense: "+str(sorted(mandatory-set(events.columns))))
    if "possession_team" not in events.columns or not events["possession_team"].notna().any():
        return (pd.DataFrame(),pd.DataFrame(),{"status":"NOT_COMPUTABLE","missing":"possession_team (titular explícito)"})
    e=events.copy()
    for c in ("location_x","location_y","end_location_x","end_location_y","statsbomb_xg","minute"):
        if c not in e:e[c]=np.nan
        e[c]=pd.to_numeric(e[c],errors="coerce")
    for c in ("type_name","play_pattern_name","player","score_state","shot_outcome","event_id"):
        if c not in e:e[c]=None
    e["timestamp_seconds"]=pd.to_numeric(e["timestamp_seconds"],errors="coerce")
    if "index" not in e:e["index"]=np.arange(len(e))
    e=e[e["match_id"].notna() & e["period"].notna() & e["possession"].notna()]
    e=e.sort_values(["match_id","period","timestamp_seconds","index"],kind="stable")
    # Explicit enemy possession owner; every event in each possession carries the same possession_team.
    e=e[e["possession_team"].notna()]
    if len(e)==0: return pd.DataFrame(),pd.DataFrame(),{"status":"NO_POSSESSIONS"}
    focal_matches=set(e.loc[e["team"].eq(team),"match_id"].astype(str))
    e=e[e["match_id"].astype(str).isin(focal_matches)]
    # match / period maps allow a short-lag opponent->focal recovery at the boundary
    match_period={key:g for key,g in e.groupby(["match_id","period"],sort=False)}
    results=[]; player_rows=[]
    for (match_id,period,poss),g in e.groupby(["match_id","period","possession"],sort=False):
        owners=g["possession_team"].dropna().astype(str)
        if owners.empty or owners.nunique()!=1:
            continue # avoid mismatched ownership
        enemy=owners.iloc[0]
        if enemy==team:continue
        opponent=g[g["team"].astype(str).eq(enemy)]
        opp_actions=opponent[opponent["event_type"].isin(ONBALL_OPP)]
        if opp_actions.empty:continue
        def_actions=g[g["team"].eq(team) & g["event_type"].isin(DEFENSIVE_ACTIONS)]
        st=opp_actions.iloc[0];minute=_num(st["minute"]); t0=_num(st["timestamp_seconds"])
        scenario,source=_scenario(opponent,cfg)
        sx=opp_actions["location_x"]
        ex=opp_actions["end_location_x"]
        max_x=pd.concat([sx,ex]).max(skipna=True)
        valid_x=pd.notna(max_x)
        visits_final=bool(max_x>=cfg.third_start_x) if valid_x else None
        in_area=opponent[opponent["location_x"].ge(cfg.penalty_area_x) & opponent["location_y"].between(cfg.penalty_area_y_low,cfg.penalty_area_y_high)]
        earea=opp_actions[opp_actions["end_location_x"].ge(cfg.penalty_area_x) & opp_actions["end_location_y"].between(cfg.penalty_area_y_low,cfg.penalty_area_y_high)]
        visits_box=bool(len(in_area) or len(earea)) if sx.notna().any() or ex.notna().any() else None
        shots=opponent[opponent["event_type"].eq("Shot")]
        xg=pd.to_numeric(shots["statsbomb_xg"],errors="coerce")
        xg_complete=not len(shots) or bool(xg.notna().all())
        xg_value=float(xg.sum()) if xg_complete else None
        # First recorded focal recovery after the last opponent action; NOT proof it ended the possession.
        end_t=_num(opp_actions.iloc[-1]["timestamp_seconds"])
        found_recovery=False
        if math.isfinite(end_t):
            gp=match_period[(match_id,period)]
            future=gp[(gp["team"].eq(team)) & gp["event_type"].isin(RECOVERY_ACTIONS) &
                      gp["timestamp_seconds"].between(end_t,end_t+cfg.recovery_followup_seconds)]
            found_recovery=bool(len(future))
        defensive_geo=def_actions[def_actions["location_x"].between(0,120) & def_actions["location_y"].between(0,80)]
        pressure=def_actions[def_actions["event_type"].eq("Pressure")]
        valid_pressure=pressure[pressure["location_x"].between(0,120)]
        zones=defensive_geo["location_x"].apply(lambda x:_zone(float(x)))
        zone_top=zones.value_counts().index[0] if len(zones) else None
        pid=f"{match_id}:{period}:{poss}"
        results.append({
            "possession_id":pid,"match_id":match_id,"period":period,"possession":poss,
            "opponent":enemy,"scenario":scenario,"scenario_source":source,
            "minute":minute,"moment":_moment(minute),"score_state":st.get("score_state"),
            "t_start":t0,"t_end":end_t,
            "opponent_onball_events":len(opp_actions),"defensive_events":len(def_actions),
            "pressures":len(pressure),"defensive_location_events":len(defensive_geo),
            "defense_high_pressure_count":int(valid_pressure["location_x"].ge(80).sum()),
            "registered_followup_recovery_5s":found_recovery,
            "reached_final_third":visits_final,"reached_box":visits_box,
            "shot_count":int(len(shots)),"shot_conceded":bool(len(shots)),
            "xg_conceded":xg_value,"xg_complete":xg_complete,
            "defensive_action_zone":zone_top,
            "sample_type":"EVENT_POSSESSION","limitations":"Sin reconstrucción continua del bloque; sin causalidad atribuida a intervención."
        })
        if len(def_actions):
            for (player,kind),g2 in def_actions[def_actions["player"].notna() &
                    def_actions["event_type"].isin(PLAYER_ACTIONS)].groupby(["player","event_type"],sort=False):
                # Original sequence positions, not motion tracking. Each individual action is evidence.
                for _,r in g2.iterrows():
                    player_rows.append({"possession_id":pid,"match_id":match_id,"opponent":enemy,
                                        "scenario":scenario,"moment":_moment(minute),"player":player,"action":kind,
                                        "event_id":r.get("event_id"),"minute":_num(r["minute"]),
                                        "x":_num(r["location_x"]),"y":_num(r["location_y"])})
    detail=pd.DataFrame(results)
    players=pd.DataFrame(player_rows,columns=["possession_id","match_id","opponent","scenario","moment","player","action","event_id","minute","x","y"])
    return detail,players,{"status":"OK","method":"EFOS_SMART_DEFENSE_v1","team":team,
                           "scenario_rule":"From Counter (explicit) > restart > recovery-rival > other; see scenario_source",
                           "limitations":["Tipo defensivo = patrón de eventos; NO marcaje zonal/individual ni formación reconstruida.",
                             "Intervenciones, presiones y participaciones por jugador no equivalen a éxito ni calidad defensiva.",
                             "La ausencia de remate no prueba intervención eficaz; tras recuperación no implica contraataque.",
                             "360 solo permite posiciones en instantes disponibles, si se carga; no hay tracking continuo.",
                             "No se establecen efectos causales de acciones individuales."]}


def summarize_smart_defense(detail:pd.DataFrame, players:pd.DataFrame, cfg:DefensiveConfig|None=None)->dict:
    cfg=cfg or DefensiveConfig()
    result={"method":"EFOS_SMART_DEFENSE_v1","scenarios":{},"n_possessions":len(detail),
            "data_status":"OK" if len(detail) else "INSUFFICIENT"}
    if detail.empty:return result
    for scenario in SITUATIONS:
        d=detail[detail["scenario"].eq(scenario)]
        n=len(d)
        if not n:continue
        p=players[players["scenario"].eq(scenario)] if len(players) else players
        covered=d[d["xg_complete"].eq(True)]
        valid_score=d["score_state"].dropna().value_counts().to_dict()
        matches=d["match_id"].nunique()
        top=p.groupby("player",dropna=True).size().sort_values(ascending=False).head(5) if len(p) else pd.Series(dtype=int)
        types=p["action"].value_counts().to_dict() if len(p) else {}
        zone_counts=(p["x"].dropna().apply(_zone).value_counts().to_dict() if len(p) else {})
        dominant_zone=max(zone_counts,key=zone_counts.get) if zone_counts else None
        lead_type=max(types,key=types.get) if types else None
        vals={
            "dominant_action_type":lead_type,
            "dominant_action_type_share_pct":round(100*types[lead_type]/len(p),1) if lead_type else None,
            "dominant_action_zone":dominant_zone,
            "dominant_action_zone_share_pct":(round(100*zone_counts[dominant_zone]/sum(zone_counts.values()),1) if dominant_zone else None),
            "action_zones":{str(k):int(v) for k,v in zone_counts.items()},
            "n_possessions":n,"matches":int(matches),"opponents":int(d["opponent"].nunique()),
            "n_shot_possessions":int(d["shot_conceded"].sum()),
            "shot_rate_pct":round(100*float(d["shot_conceded"].mean()),1),
            "xg_per_possession_complete":round(float(covered["xg_conceded"].mean()),4) if len(covered) else None,
            "xg_coverage_pct":round(100*len(covered)/n,1),
            "defensive_events":int(d["defensive_events"].sum()),
            "pressures":int(d["pressures"].sum()),
            "pressures_per_100_possessions":round(100*float(d["pressures"].sum())/n,1),
            "post_recovery_5s_pct":round(100*float(d["registered_followup_recovery_5s"].mean()),1),
            "score_contexts":{str(k):int(v) for k,v in valid_score.items()},
            "moments":{str(k):int(v) for k,v in d["moment"].value_counts().items()},
            "players": [{"player":str(name),"events":int(val),"share_of_observed_actions_pct":round(100*val/len(p),1),
                          "matches":int(p[p["player"].eq(name)]["match_id"].nunique()),
                          "dominant_action":str(p[p["player"].eq(name)]["action"].value_counts().index[0])} for name,val in top.items()],
            "actions_by_type":{str(k):int(v) for k,v in types.items()},
            "status":"RECURRING_SAMPLE" if matches>=cfg.min_matches_for_recurrence and n>=cfg.min_possessions_for_claim else "EXPLORATORY",
            "limits":"Indicadores descriptivos sobre posesiones del rival, no esquema zonal/hombre ni intención comprobada."
        }
        result["scenarios"][scenario]=vals
    return result


def defensive_findings(summary:dict,team:str, cfg:DefensiveConfig|None=None)->list[dict]:
    cfg=cfg or DefensiveConfig()
    findings=[]
    for label,stats in summary.get("scenarios",{}).items():
        n=stats["n_possessions"]
        if stats["status"]!="RECURRING_SAMPLE":continue
        text=(f"Frente a {label.lower()}, {team} registró {stats['pressures_per_100_possessions']:.0f} "
              f"acciones de presión por cada 100 posesiones rivales; en {stats['shot_rate_pct']:.1f}% "
              f"de esas posesiones recibió al menos un remate "
              f"({n} posesiones, {stats['matches']} partidos).")
        findings.append({"id":"smart_defense_"+str(SITUATIONS.index(label)),"section":"defensive_context",
                         "claim":text,"evidence":stats,"n":n,"source":"STATSBOMB_EVENT_POSSESSIONS",
                         "confidence":"MEDIUM", "limitation":"Frecuencias descriptivas; sin efectos causales, marcaje observado ni tracking defensivo."})
    return findings


def analyze_smart_defense(events:pd.DataFrame,team:str,config:DefensiveConfig|None=None):
    necessary={"match_id","period","possession","team","event_type","timestamp_seconds","possession_team"}
    missing=sorted(necessary.difference(events.columns))
    if missing:
        detail=pd.DataFrame();players=pd.DataFrame()
        meta={"status":"NOT_COMPUTABLE","missing_columns":missing}
    else:
        detail,players,meta=build_smart_defense(events,team,config)
    summary=summarize_smart_defense(detail,players,config)
    summary["provenance"]=meta
    return detail,players,summary,defensive_findings(summary,team,config)
