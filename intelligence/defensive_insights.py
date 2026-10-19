"""Auditable event-only defensive insights; no fitted tactical-gap score.

Native StatsBomb coordinates are actor-relative (+x in attack). Returned insight
coordinates use opponent attack toward +x, i.e. the focal team's goal at x=120.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from intelligence.defensive_open_play import normalize_events, DEFENSE_TYPES, _is_restart

CONTROL = {'Pass', 'Carry', 'Dribble', 'Shot'}
STOPS = {'Foul Committed', 'Foul Won', 'Offside', 'Half End', 'Ball Out', 'Injury Stoppage'}


def truth(value):
    return str(value).strip().lower() in {'true', '1', '1.0', 'yes'}


def valid_xy(x,y):
    return pd.notna(x) and pd.notna(y) and 0 <= x <= 120 and 0 <= y <= 80


def zone(x,y):
    if not valid_xy(x,y): return 'Sin ubicación'
    depth = 'Lejos de portería propia' if x < 40 else 'Zona media' if x < 80 else 'Cerca de portería propia'
    # Explicit diagram lanes avoid undocumented left/right conventions.
    lane = 'franja inferior' if y < 80/3 else 'carril central' if y < 160/3 else 'franja superior'
    return depth + ' · ' + lane


def enrich(summary, events, team):
    """One row per eligible rival possession plus first final-third entries.

    Counterpress is an explicit provider tag on a focal defensive event. A return
    of control needs an on-ball action in the immediately following own open-play
    possession, same half, <=5s after the last rival event, with no recorded stop.
    Recovery coordinates are the FIRST CONTROL observation, not an inferred steal.
    """
    if summary.empty: return summary.copy()
    e=normalize_events(events)
    groups=list(e.groupby(['match_id','possession'],sort=False))
    wanted={(str(r.match_id),r.possession):r for r in summary.itertuples(index=False)}
    rows=[]
    for i,(key,g) in enumerate(groups):
        if key not in wanted: continue
        row=wanted[key]._asdict()
        own=g[g.team.eq(team)&g.event_type.isin(DEFENSE_TYPES)]
        cp=own[own.counterpress.map(truth)]
        first=cp.iloc[0] if len(cp) else None
        row.update(counterpress_observed=bool(len(cp)),counterpress_actions=len(cp),
            cp_event_id=str(first.event_id) if first is not None else '',
            cp_x=120-first.location_x if first is not None else np.nan,
            cp_y=80-first.location_y if first is not None else np.nan,
            control_confirmed=False,control_x=np.nan,control_y=np.nan,control_event_id='',
            control_player='',control_seconds=np.nan,control_within_10s=False,
            entry_zone='Sin entrada observada',entry_event_id='',entry_x=np.nan,entry_y=np.nan,
            shot_after_entry=False,xg_after_entry=np.nan,entry_xg_complete=False)
        # A tagged recovery event with no confirmed subsequent control is not a recovery success.
        if first is not None and i+1<len(groups):
            nk,ng=groups[i+1]
            controls=ng[ng.team.eq(team)&ng.event_type.isin(CONTROL)]
            if (nk[0]==key[0] and ng.iloc[0].possession_team==team and not controls.empty):
                c=controls.iloc[0]
                tail=pd.concat([g[g['index'].ge(first['index'])],ng[ng['index'].le(c['index'])]])
                restarts=any(_is_restart(r.play_pattern_name,r.event_type,r.type_name)
                             for r in ng[ng['index'].le(c['index'])].itertuples())
                stopped=tail.event_type.isin(STOPS).any() or tail.outcome_name.fillna('').str.lower().isin(
                    ['out','lost out','success out','pass offside','goal']).any()
                failed_recovery=any(tail[col].map(truth).any() for col in
                    ['ball_recovery_recovery_failure','recovery_failure'] if col in tail)
                gap=c.clock_seconds-g.iloc[-1].clock_seconds
                elapsed=c.clock_seconds-first.clock_seconds
                if (c.period==first.period and 0<=gap<=5 and elapsed>=0 and
                    not restarts and not stopped and not failed_recovery):
                    row.update(control_confirmed=True,control_x=120-c.location_x,
                        control_y=80-c.location_y,control_event_id=str(c.event_id),control_player=c.player,
                        control_seconds=float(elapsed),control_within_10s=bool(elapsed<=10))
        # MECE lane of FIRST completed pass/carry entering attacking final third.
        rival=g[g.team.ne(team)]
        paths=rival[rival.event_type.isin(['Pass','Carry'])]
        outcome=paths.outcome_name.fillna('').str.lower()
        successful=paths.event_type.eq('Carry') | outcome.isin(['','complete','success','success in play'])
        valid=paths.location_x.between(0,120)&paths.location_y.between(0,80)&paths.end_location_x.between(0,120)&paths.end_location_y.between(0,80)
        entries=paths[successful & valid & paths.location_x.lt(80)&paths.end_location_x.ge(80)]
        if len(entries):
            ent=entries.iloc[0]
            later=rival[rival['index'].gt(ent['index']) & rival.event_type.eq('Shot')]
            complete=later.statsbomb_xg.notna().all()
            row.update(entry_zone=zone(ent.end_location_x,ent.end_location_y),
                entry_event_id=str(ent.event_id),entry_x=ent.end_location_x,entry_y=ent.end_location_y,
                shot_after_entry=bool(len(later)),entry_xg_complete=bool(complete),
                xg_after_entry=float(later.statsbomb_xg.sum()) if complete else np.nan)
        row['control_zone']=zone(row['control_x'],row['control_y']) if row['control_confirmed'] else 'Sin control confirmado'
        row['cp_zone']=zone(row['cp_x'],row['cp_y']) if row['counterpress_observed'] else 'Sin contrapresión etiquetada'
        rows.append(row)
    return pd.DataFrame(rows)


def zone_exposure(d):
    """Each possession counted once by first entry lane; missing coverage explicit."""
    eligible=d[d.entry_event_id.ne('')]
    rows=[]
    for lane,g in eligible.groupby('entry_zone',sort=True):
        n=len(g); shots=int(g.shot_after_entry.sum())
        complete=g[g.entry_xg_complete]
        rows.append(dict(zona=lane,posesiones=n,partidos=g.match_id.nunique(),
            con_remate=shots,pct_remate=100*shots/n,
            xg_pos=float(complete.xg_after_entry.mean()) if len(complete) else np.nan,
            cobertura_xg=100*len(complete)/n,
            evidencia='Exploratoria' if n<30 or g.match_id.nunique()<5 else 'Descriptiva; no causal'))
    return pd.DataFrame(rows,columns=['zona','posesiones','partidos','con_remate','pct_remate','xg_pos','cobertura_xg','evidencia'])


def recovery_stats(d):
    cp=d[d.counterpress_observed]
    rec=cp[cp.control_confirmed]
    return dict(n=len(cp),recovered=len(rec),fast=int(cp.control_within_10s.sum()),
        located=int((rec.control_x.between(0,120)&rec.control_y.between(0,80)).sum()),
        median_seconds=float(rec.control_seconds.median()) if len(rec) else None)


def pattern_table(d):
    rows=[]
    for label,g in d[d.counterpress_observed].groupby('cp_zone',sort=True):
        rows.append({'Inicio de contrapresión':label,'Posesiones':len(g),'Partidos':g.match_id.nunique(),
            'Control confirmado después':int(g.control_confirmed.sum()),
            'Control en ≤10 s':int(g.control_within_10s.sum()),'Posesiones con remate rival':int(g.shot.sum())})
    return pd.DataFrame(rows)
