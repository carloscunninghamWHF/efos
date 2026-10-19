"""EFOS Smart Defensive Tactics · juego abierto · v0.4.13.

Event data only: observations; not a reconstructed formation or continuous tracking.
Entradas: StatsBomb/EFOS normalized wide CSV, un JSON native events -> use normalize_events.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

STATES = ('Reacción tras pérdida','Defensa ante contraataque','Defensa ante ataque posicional')
OTHER = 'Otro juego abierto'
SET_PIECES = ('corner','free kick','throw-in','throw in','goal kick','kick off','kick-off',
              'penalty','penalti','drop ball','falta','tiro libre','saque de banda','saque de esquina')
DEFENSE_TYPES = {'Pressure','Ball Recovery','Interception','Duel','Block','Clearance',
                 'Foul Committed','Dribbled Past','50/50','Shield','Error'}
MINUTE_BANDS = ('0–15','16–30','31–45+','46–60','61–75','76–90+')


def _string(v: object) -> str:
    if v is None or (not isinstance(v, (dict,list,tuple)) and pd.isna(v)): return ''
    return str(v)


def _num(v: object) -> float:
    try: return float(v)
    except (TypeError, ValueError): return float('nan')


def _key(v: object) -> str: return _string(v).strip().casefold()


def _is_restart(play_pattern: object, first_type: object, first_subtype: object) -> bool:
    combined = ' '.join((_key(play_pattern),_key(first_subtype)))
    # These labels mark set-piece-origin possession even when normal passes follow.
    if any(token in combined for token in SET_PIECES): return True
    # A generic foul only refers to a restart if a pass type identifies it.
    return _key(first_type) in {'starting xi','half start'}


def _minute_band(minute: float) -> str:
    if minute <= 15: return MINUTE_BANDS[0]
    if minute <= 30: return MINUTE_BANDS[1]
    if minute < 46: return MINUTE_BANDS[2]
    if minute <= 60: return MINUTE_BANDS[3]
    if minute <= 75: return MINUTE_BANDS[4]
    return MINUTE_BANDS[5]


def normalize_events(events: pd.DataFrame) -> pd.DataFrame:
    """Normalize a StatsBomb wide export without inventing missing fields."""
    e=events.copy()
    aliases={'id':'event_id','team_name':'team','possession_team_name':'possession_team',
             'event_type_name':'event_type','player_name':'player','shot_statsbomb_xg':'statsbomb_xg'}
    for old,new in aliases.items():
        if new not in e and old in e: e[new]=e[old]
    required=['match_id','period','index','possession','team','possession_team','event_type']
    missing=[c for c in required if c not in e.columns]
    if missing: raise ValueError(f'Faltan columnas StatsBomb: {", ".join(missing)}')
    for c in ['player','type_name','play_pattern_name','outcome_name','event_id',
              'shot_outcome','counterpress','pass_outcome','is_transition',
              'location_x','location_y','end_location_x','end_location_y',
              'minute','second','timestamp_seconds','statsbomb_xg']:
        if c not in e: e[c]=np.nan
    e['match_id']=e['match_id'].astype(str)
    for c in ['period','index','possession','minute','second','timestamp_seconds',
              'location_x','location_y','end_location_x','end_location_y','statsbomb_xg']:
        e[c]=pd.to_numeric(e[c],errors='coerce')
    e=e.dropna(subset=['period','index','possession','team','possession_team'])
    e=e.drop_duplicates(['match_id','period','index']).sort_values(['match_id','period','index']).reset_index(drop=True)
    e['minute']=e['minute'].fillna(0)
    e['second']=e['second'].fillna(0)
    # Original StatsBomb minute is normally match-clock; avoid period 2 local-clock collisions.
    h2=(e['period'].eq(2) & e.groupby(['match_id','period'])['minute'].transform('median').lt(45))
    e.loc[h2,'minute']+=45
    e['clock_seconds']=e['minute']*60+e['second']
    # Respect the stable native game-clock convention for clock reporting.
    e['minute_band']=e['minute'].map(_minute_band)
    return e


def with_score_state(e: pd.DataFrame, team: str) -> pd.DataFrame:
    """Score state *before* each event, within one match, excluding shootouts."""
    e=e.copy()
    states=pd.Series(index=e.index,dtype='object')
    for _, g in e.groupby('match_id',sort=False):
        ours=theirs=0
        for idx,row in g.iterrows():
            states.at[idx]=('Gana' if ours>theirs else ('Pierde' if ours<theirs else 'Empata'))
            kind=_key(row['event_type'])
            if int(row['period'])>=5:continue
            scorer=None
            if kind=='shot' and (_key(row['shot_outcome'])=='goal' or _key(row['outcome_name'])=='goal'):
                scorer=_string(row['team'])
            elif kind=='own goal for':
                scorer=_string(row['team'])
            elif kind=='own goal against':
                scorer='__other__' if row['team']==team else team
            if scorer is not None:
                if scorer==team: ours+=1
                else: theirs+=1
    e['match_state']=states
    return e


def _turnover(prev: pd.Series, team: str) -> bool:
    if prev['possession_team']!=team:return False
    # Avoid interpreting a generic possession switch after a dead ball as a loss.
    if _is_restart(prev['play_pattern_name'],prev['event_type'],prev['type_name']):return False
    kind=_key(prev['event_type']); outcome=_key(prev['outcome_name'])
    return (kind in ('dispossessed','miscontrol','error') or
            (kind=='pass' and outcome in ('incomplete','out','pass offside','unknown')) or
            (kind=='duel' and outcome in ('lost in play','lost out')))


def analyze(events: pd.DataFrame, team: str='América') -> tuple[pd.DataFrame,pd.DataFrame]:
    """Return (one row/opponent possession, event rows included in those possessions).

    MECE order: labelled counterattack > clear turnover reaction > positional > other.
    Positional operational definition: at least 4 rival on-ball actions OR >=12 sec.
    Out-of-play restarts are excluded at possession level.
    """
    e=with_score_state(normalize_events(events),team)
    if team not in set(e['team'].dropna()):
        raise ValueError(f'No se encontró {team!r}. Equipos: {sorted(e.team.dropna().unique().tolist())}')
    e=e[e['period'].le(4)].copy()
    # All possessions sorted in true match order; possession_team is the StatsBomb owner.
    g_all=e.groupby(['match_id','possession'],sort=False)
    groups=list(g_all)
    summaries=[]; ids=[]
    for i,((match_id,poss),part) in enumerate(groups):
        a=part.iloc[0]; owner=a['possession_team']
        if owner==team: continue
        first_owner=part[part['team'].eq(owner)]
        if first_owner.empty:continue
        fst=first_owner.iloc[0]
        pattern=next((v for v in part['play_pattern_name'] if _string(v) and _key(v)!='nan'),'')
        # explicit restart labels can appear throughout the possession
        restart=any(_is_restart(v,'','') for v in part['play_pattern_name'].dropna().unique())
        restart=restart or _is_restart(pattern,fst['event_type'],fst['type_name'])
        if restart:continue
        first_t=_num(fst['clock_seconds']); last_t=_num(part.iloc[-1]['clock_seconds'])
        dur=max(0.,last_t-first_t) if np.isfinite(first_t) and np.isfinite(last_t) else 0.
        prevpart=groups[i-1][1] if i>0 and groups[i-1][0][0]==match_id else pd.DataFrame()
        prev=prevpart.iloc[-1] if not prevpart.empty else None
        prev_last=float(prev['clock_seconds']) if prev is not None else float('nan')
        prox=prev is not None and first_t>=prev_last and first_t-prev_last<=8
        # Explicit 'from' recovery tags refer to how rival obtained possession.
        tagged_recovery=any(x in _key(pattern) for x in ('interception','ball recovery','miscontrol','dispossessed'))
        defev=part[part.team.eq(team) & part.event_type.isin(DEFENSE_TYPES)]
        firstdef=defev.iloc[0] if len(defev) else None
        first_delay=(float(firstdef['clock_seconds'])-first_t) if firstdef is not None else np.inf
        cp=any(_key(v) in ('true','1','yes') for v in defev['counterpress'])
        # A documented quick defensive reaction, not simply any possession
        # following América's last contact with the ball.
        after_loss=(tagged_recovery or (prox and prev is not None and _turnover(prev,team))) and (cp or 0<=first_delay<=5)
        is_counter=('counter' in _key(pattern) or _key(pattern) in ('from counter','from counterattack'))
        # Fallback on-ball activity: passes, carries, dribbles, shots by owner.
        onball=int(first_owner['event_type'].isin(['Pass','Carry','Dribble','Shot']).sum())
        if is_counter:scenario=STATES[1]
        elif after_loss:scenario=STATES[0]
        elif onball>=4 or dur>=12:scenario=STATES[2]
        else:scenario=OTHER
        shots=first_owner[first_owner.event_type.eq('Shot')]
        pass_carry=first_owner[first_owner.event_type.isin(['Pass','Carry'])]
        endx=pd.to_numeric(pass_carry['end_location_x'],errors='coerce')
        startx=pd.to_numeric(pass_carry['location_x'],errors='coerce')
        # Opponent attacks to 120 in the native StatsBomb convention.
        progression=float(max(0,(endx-startx).max())) if len(pass_carry) and (endx-startx).notna().any() else np.nan
        reached_final=bool(((endx>=80)|(startx>=80)).fillna(False).any())
        next_team=groups[i+1][1].iloc[0]['possession_team'] if i+1<len(groups) and groups[i+1][0][0]==match_id else None
        xg_complete = bool(shots['statsbomb_xg'].notna().all())  # no shots -> 0 xG is observed
        xg_value = float(shots['statsbomb_xg'].sum()) if xg_complete else np.nan
        summaries.append(dict(match_id=match_id,period=int(fst['period']),possession=poss,
            scenario=scenario,play_pattern=_string(pattern),minute=float(fst['minute']),
            minute_band=_minute_band(float(fst['minute'])),match_state=fst['match_state'],
            n_defensive_actions=len(defev),n_pressures=int(defev.event_type.eq('Pressure').sum()),
            shot=int(len(shots)>0),shots=int(len(shots)),xg=xg_value,xg_complete=xg_complete,
            rival_actions=onball,progression_max=progression,reached_final_third=reached_final,
            duration_sec=dur,first_contact_x=float(firstdef['location_x']) if firstdef is not None else np.nan,
            first_contact_y=float(firstdef['location_y']) if firstdef is not None else np.nan,
            first_contact_type=firstdef['event_type'] if firstdef is not None else '',
            first_contact_player=_string(firstdef['player']) if firstdef is not None else '',
            next_possession_america=bool(next_team==team),
            source='StatsBomb events',sample_id=f'{match_id}:{poss}'))
        ids.append((match_id,poss))
    summary=pd.DataFrame(summaries)
    if summary.empty:return summary,e.iloc[0:0]
    eligible=pd.MultiIndex.from_tuples(ids,names=['match_id','possession'])
    ev=e.set_index(['match_id','possession'])
    ev=ev[ev.index.isin(eligible)].reset_index()
    return summary,ev


def filter_scenarios(summary,events,scenario=None,period=None,match_state=None):
    s=summary.copy()
    if scenario and scenario!='Todos':s=s[s.scenario.eq(scenario)]
    if period and period!='Todos':s=s[s.minute_band.eq(period)]
    if match_state and match_state!='Todos':s=s[s.match_state.eq(match_state)]
    if s.empty:return s,events.iloc[:0].copy()
    keys=pd.MultiIndex.from_frame(s[['match_id','possession']])
    e=events[events.set_index(['match_id','possession']).index.isin(keys)].copy()
    return s,e


def kpis(s: pd.DataFrame) -> dict:
    if s.empty:return dict(posesiones=0,partidos=0,pct_remate=0,presiones_100=0,xg_pos=None,xg_coverage_pct=0)
    n=len(s)
    valid=s[s['xg_complete']].copy()
    return dict(posesiones=n,partidos=int(s.match_id.nunique()),
        pct_remate=float(s.shot.sum()*100/n),
        presiones_100=float(s.n_pressures.sum()*100/n),
        xg_pos=float(valid.xg.mean()) if len(valid) else None,
        xg_coverage_pct=float(len(valid)*100/n))


def time_summary(s):
    if s.empty:return pd.DataFrame()
    out=s.groupby('minute_band',observed=True).agg(posesiones=('shot','size'),
          partidos=('match_id','nunique'),remates=('shot','sum'),presiones=('n_pressures','sum'),
          xg=('xg','sum'),xg_covered=('xg_complete','sum')).reindex(MINUTE_BANDS,fill_value=0).reset_index()
    out['pct_remate']=out.remates.div(out.posesiones.replace(0,np.nan))*100
    out['presiones_100']=out.presiones.div(out.posesiones.replace(0,np.nan))*100
    out['xg_pos']=out.xg.div(out.xg_covered.replace(0,np.nan))
    out['xg_coverage_pct']=100*out.xg_covered.div(out.posesiones.replace(0,np.nan))
    return out


def event_detail(e,match_id,poss):
    return e[e.match_id.eq(str(match_id)) & e.possession.eq(poss)].sort_values(['period','index'])


def load_360(path_or_file):
    """StatsBomb 360 native JSON list. No interpolation is performed."""
    if hasattr(path_or_file,'read'):
        raw=path_or_file.read()
        if isinstance(raw,bytes):raw=raw.decode('utf-8')
        frames=json.loads(raw)
    else:frames=json.loads(Path(path_or_file).read_text(encoding='utf-8'))
    return {str(x['event_uuid']):x for x in frames if isinstance(x,dict) and x.get('event_uuid')}
