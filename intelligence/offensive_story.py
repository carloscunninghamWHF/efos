"""EFOS v0.4.19: evidence-first offensive narrative shared by dashboard and Coach Story.

Consumes observed open-play possession slices. No changes to ESI, CTS, OC,
StatsBomb coordinates or possession reconstruction. Titles are descriptive,
not tactical intent or causal attribution. All denominators explicit.
"""
from __future__ import annotations
import math
import pandas as pd
from intelligence import organized_attack as A

MIN_MATCHES_FOR_IDENTITY = 3
MIN_POSSESSIONS_FOR_IDENTITY = 20


def _name(v):
    return str(v).strip() if pd.notna(v) else ""


def readable_match_labels(events: pd.DataFrame, focal_team: str, match_ids) -> dict:
    """Display genuine opponent/date if present, otherwise anonymous ordinal labels.

    Never equates numeric match IDs with actual matchday IDs.
    """
    ids = list(dict.fromkeys(str(v) for v in match_ids))
    use_cols=[c for c in ("match_id","team","match_date") if c in events.columns]
    src = events[use_cols].copy()
    if "match_id" not in src.columns:
        return {mid: f"Partido {i:02d} · Rival no identificado" for i,mid in enumerate(ids,1)}
    src["_match_label_id"] = src["match_id"].astype(str)
    teams = src.groupby("_match_label_id", sort=False)["team"].agg(lambda s: [str(x) for x in s.dropna().unique()]) if "team" in src else {}
    labels={}
    for i,mid in enumerate(ids,1):
        rivals=[x for x in teams.get(mid,[]) if x != focal_team]
        rival=rivals[0] if len(rivals)==1 else "Rival no identificado"
        date=""
        if "match_date" in src.columns:
            v=src.loc[src["_match_label_id"].eq(mid),"match_date"].dropna()
            date=f" · {str(v.iloc[0])[:10]}" if len(v) else ""
        labels[mid]=f"Partido {i:02d} · vs {rival}{date}"
    return labels


def identity_ready(n:int, matches:int) -> bool:
    return n >= MIN_POSSESSIONS_FOR_IDENTITY and matches >= MIN_MATCHES_FOR_IDENTITY


def build_offensive_story(d: pd.DataFrame, possessions: pd.DataFrame) -> dict:
    """Narrative valid strictly for the same filtered data/sample as its charts."""
    if possessions.empty:
        return {"status":"INSUFFICIENT","overview":"No hay secuencias de ataque evaluables en esta selección.",
                "insights":[],"n_possessions":0,"n_matches":0,"connection":None,"route":None,
                "schema":"EFOS_OFFENSIVE_STORY_1"}
    t=possessions
    n=int(len(t)); nm=int(t.match_id.nunique());ready=identity_ready(n,nm)
    insights=[]
    lane=t[t.lane.isin(["Izquierda","Centro","Derecha"])].lane.value_counts()
    entry=None
    if len(lane):
        zone=str(lane.index[0]);num=int(lane.iloc[0]);valid_n=int(lane.sum())
        frequency=num/valid_n
        qualifier="predomina" if ready and frequency>=.50 else "es el más frecuente"
        title=f"El inicio por {zone.lower()} {qualifier} en la selección"
        text=(f"{num} de {valid_n} secuencias con origen identificado empiezan por {zone.lower()} "
              f"({frequency:.0%}), observadas en {int(t.loc[t.lane.eq(zone),'match_id'].nunique())} partidos. "
              "Es la zona de la primera intervención registrada, no una formación del equipo.")
        entry={"lane":zone,"count":num,"denominator":valid_n,"share":round(frequency,4),
               "matches":int(t.loc[t.lane.eq(zone),'match_id'].nunique())}
        insights.append({"id":"attack_start_lane","title":title,"text":text,
                         "n":num,"denominator":valid_n,"n_matches":entry['matches'],
                         "source":"STATSBOMB_POSSESSION_START_PROXY",
                         "limitation":"Zona de la primera acción observada, no estructura simultánea.",
                         "keys":t.loc[t.lane.eq(zone),'key'].tolist()})
    connection=None
    if d.attrs.get('outcome_available') and 'pass_recipient_name' in d.attrs.get('source_columns',[]):
        links=A.connections(d)
        links=links[links.completados.gt(0)] if len(links) else links
        if len(links):
            r=links.iloc[0]
            a,b=_name(r.player),_name(r.pass_recipient_name)
            count=int(r.completados); attempts=int(r.intentos); matches=int(r.partidos)
            connection={"from":a,"to":b,"completed":count,"attempts":attempts,"matches":matches,
                        "obv":float(r.obv) if pd.notna(r.obv) else None,"obv_coverage":int(r.cobertura_obv)}
            link=d[d['_type'].eq('pass')&d.player.eq(a)&d.pass_recipient_name.eq(b)&d['_pass_done']]
            keys=list(dict.fromkeys(link['_poss_key'].tolist()))
            qualifier="conexión recurrente" if identity_ready(count,matches) else "conexión destacada en esta selección"
            insights.append({"id":"attack_connection","title":f"{a} → {b}: {qualifier}",
                             "text":f"{count} pases completos de {attempts} intentos registrados con destinatario en {matches} {'partido' if matches==1 else 'partidos'}. "
                                    "La cantidad de pases no demuestra por sí sola progresión, coordinación sin balón ni calidad del vínculo.",
                             "n":count,"denominator":attempts,"n_matches":matches,
                             "source":"STATSBOMB_COMPLETED_PASSES","limitation":"Conexión observada, no mecanismo causal; sujetos a cobertura de destinatario y resultado.",
                             "keys":keys})
    entered=t[t.box_entries.gt(0)]
    shot_pos=int(t.shots.gt(0).sum())
    shot_count=int(t.shots.sum())
    xg_known=int(t.xg_n.sum())
    known_shot_pos=int((t.xg_n.eq(t.shots) & t.shots.gt(0)).sum())
    xg_total=float(t.xg.sum(min_count=1)) if xg_known and pd.notna(t.xg.sum(min_count=1)) else None
    productivity={"n_possessions":n,"shot_possessions":shot_pos,"shots":shot_count,
                  "box_entry_possessions":int(len(entered)),"xg":xg_total,"shots_with_xg":xg_known,
                  "shot_possessions_with_complete_xg":known_shot_pos}
    insights.append({"id":"attack_outcomes","title":"De las secuencias a las ocasiones",
                     "text":f"En {n} secuencias observadas, {int(len(entered))} registran entrada al área mediante pase o conducción y "
                            f"{shot_pos} incluyen al menos un remate ({shot_count} remates). "
                            + (f"xG observado: {xg_total:.2f}, con dato en {xg_known} de {shot_count} tiros. " if xg_total is not None else "El xG no está disponible. ")
                            + "Una entrada y un remate dentro de la misma posesión no demuestran que la primera causó el segundo.",
                     "n":n,"denominator":n,"n_matches":nm,"source":"STATSBOMB_OPEN_PLAY_SEQUENCES",
                     "limitation":"Correlación dentro de posesión; xG sólo en tiros con cobertura.",
                     "keys":t.loc[t.shots.gt(0),'key'].tolist()})
    route=None
    if "lane" in t and "xg_n" in t:
        sample=t[t.lane.isin(["Izquierda","Centro","Derecha"])].copy()
        sample=sample[sample.shots.eq(0)|sample.xg_n.eq(sample.shots)]
        sample['covered_xg']=sample.xg.where(sample.shots.gt(0),0)
        choices=[]
        for lane_name,g in sample.groupby('lane'):
            if len(g)>=MIN_POSSESSIONS_FOR_IDENTITY and g.match_id.nunique()>=MIN_MATCHES_FOR_IDENTITY and (g.shots.gt(0).any()):
                choices.append((float(g.covered_xg.mean()),lane_name,int(len(g)),int(g.match_id.nunique())))
        if choices:
            v,z,k,m=sorted(choices,reverse=True)[0]
            route={"lane":z,"xg_per_eligible_possession":round(v,4),"eligible_possessions":k,
                   "matches":m,"definition":"Corredor de la primera acción; asociación descriptiva, no atribución causal."}
    prefix=("En la muestra seleccionada" if ready else "En esta selección limitada")
    overview=(f"{prefix}, se analizaron {n} secuencias de juego abierto en {nm} {'partido' if nm==1 else 'partidos'}. "
              +(f"El comienzo más frecuente está en el sector {entry['lane'].lower()} "
                f"({entry['count']}/{entry['denominator']}); " if entry else "No hay coordenadas de inicio suficientes; ")
              +(f"la conexión con más pases completos es {connection['from']} → {connection['to']} "
                f"({connection['completed']} en {connection['matches']} {'partido' if connection['matches']==1 else 'partidos'}). " if connection else "no existe cobertura suficiente para destacar una conexión fiable. ")
              +f"Se registraron {shot_count} remates en estas secuencias. "
              +("Estos hallazgos describen patrones observados; no establecen intenciones del entrenador."))
    return {"schema":"EFOS_OFFENSIVE_STORY_1","status":"DESCRIPTIVE" if ready else "SMALL_SAMPLE",
            "overview":overview,"n_possessions":n,"n_matches":nm,
            "entry":entry,"connection":connection,"productivity":productivity,"route":route,"insights":insights,
            "limitations":["Los sectores representan el inicio registrado, no formaciones simultáneas.",
                            "El promedio xG sólo se computa sobre secuencias con cobertura completa del remate.",
                            "La narrativa no atribuye causalidad ni intención táctica."]}


def coach_claims(story:dict) -> list[dict]:
    """Keep machine-verifiable provenance in the existing Evidence Layer schema."""
    return [{"id":x["id"],"section":"offensive_identity","claim":x["text"],
             "evidence":{"denominator":x["denominator"],"match_count":x["n_matches"],
                         "sequence_keys":[[str(a) for a in k] for k in x['keys'][:30]],
                         "more_sequences":max(0,len(x['keys'])-30)},
             "n":x["n"],"source":x["source"],
             "confidence":"MEDIUM" if identity_ready(x["n"],x["n_matches"]) else "LOW",
             "limitation":x["limitation"]} for x in story.get('insights',[])]
