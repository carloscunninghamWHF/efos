from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

KEEP = [
'id','index','match_id','period','timestamp','minute','second','event_type_name','possession',
'possession_team_id','possession_team_name','play_pattern_name','team_id','team_name','player_id','player_name',
'player_position_name','location_x','location_y','end_location_x','end_location_y','duration','under_pressure',
'counterpress','substituted_player_id','substituted_player_name','pass_recipient_id','pass_recipient_name','pass_length',
'pass_height_name','pass_cross','pass_cut_back','pass_switch','key_pass_id','statsbomb_xg','obv_for_net','obv_against_net',
'obv_total_net','outcome_name','freeze_frame_player_id','freeze_frame_player_name','freeze_frame_player_position_name',
'freeze_frame_teammate','freeze_frame_x','freeze_frame_y','formation_player_id','formation_player_name','formation_position_name',
'formation_jersey_number','pass_cluster_id','pass_cluster_label','pass_cluster_probability','pass_success_probability',
'shot_execution_xg','gk_positioning_xg_suppression','set_piece_phase','attacking_direction',
'defensive_responsibility_probability_sum','control_degree','is_transition','is_controlled_possession',
'player_possession_directness','possession_directness','location_bucket'
]

def _read(path):
    cols=pd.read_csv(path,nrows=0).columns
    use=[c for c in KEEP if c in cols]
    return pd.read_csv(path,usecols=use,low_memory=False)

def load_competition_csvs(paths):
    raw=pd.concat([_read(p).assign(source_file=Path(p).name) for p in paths],ignore_index=True)
    raw['id']=raw['id'].astype(str)
    frame_cols=['id','match_id','freeze_frame_player_id','freeze_frame_player_name','freeze_frame_player_position_name','freeze_frame_teammate','freeze_frame_x','freeze_frame_y']
    frame_cols=[c for c in frame_cols if c in raw.columns]
    frames=raw.loc[raw.get('freeze_frame_player_id',pd.Series(index=raw.index,dtype=float)).notna(),frame_cols].copy()
    # one analytical row per event id; expanded freeze-frame rows remain in frames
    events=(raw.sort_values(['match_id','period','index'],kind='stable')
              .drop_duplicates('id',keep='first').copy())
    events['match_seconds']=events['minute'].fillna(0)*60+events['second'].fillna(0)
    return raw, events, frames

def validate(raw,events,frames,expected_matches=38):
    issues=[]
    if events['id'].duplicated().any(): issues.append('event_id_not_unique')
    matches=int(events['match_id'].nunique())
    if matches != expected_matches: issues.append(f'expected_{expected_matches}_matches_got_{matches}')
    for c,lo,hi in [('location_x',0,120),('end_location_x',0,120),('location_y',0,80),('end_location_y',0,80)]:
        if c in events and events[c].dropna().between(lo,hi).mean() < 1: issues.append(f'{c}_out_of_bounds')
    orphan=int((~frames['id'].isin(events['id'])).sum()) if len(frames) else 0
    if orphan: issues.append(f'{orphan}_orphan_frames')
    return {'raw_rows':len(raw),'unique_events':len(events),'freeze_frame_rows':len(frames),'matches':matches,
            'duplicate_rows_removed':len(raw)-len(events),'issues':issues,'passed':not issues}

def add_score_context(events, target_team='América'):
    e=events.sort_values(['match_id','period','index'],kind='stable').copy()
    is_goal=(e['event_type_name'].eq('Shot') & e['outcome_name'].astype(str).str.lower().eq('goal'))
    # StatsBomb emits paired Own Goal For / Against rows. Count only Own Goal For to avoid double counting.
    own_for=e['event_type_name'].eq('Own Goal For')
    e['goal_for_target']=((is_goal & e['team_name'].eq(target_team)) | (own_for & e['team_name'].eq(target_team))).astype(int)
    e['goal_against_target']=((is_goal & ~e['team_name'].eq(target_team)) | (own_for & ~e['team_name'].eq(target_team))).astype(int)
    # score BEFORE current event prevents a goal from retroactively changing its own context
    e['target_goals_before']=e.groupby('match_id')['goal_for_target'].cumsum()-e['goal_for_target']
    e['opp_goals_before']=e.groupby('match_id')['goal_against_target'].cumsum()-e['goal_against_target']
    d=e['target_goals_before']-e['opp_goals_before']
    e['score_state']=np.select([d>0,d<0],['winning','losing'],default='drawing')
    return e

def build_possessions(events):
    g=events.groupby(['match_id','possession'],dropna=False)
    out=g.agg(possession_team=('possession_team_name','first'),start_sec=('match_seconds','min'),end_sec=('match_seconds','max'),
              start_x=('location_x','first'),end_x=('end_location_x','last'),events=('id','nunique'),
              obv=('obv_total_net','sum')).reset_index()
    out['duration_s']=(out.end_sec-out.start_sec).clip(lower=0)
    out['progression_x']=out.end_x-out.start_x
    return out

def behavior_features(events,target_team='América'):
    t=events[events.team_name.eq(target_team)].copy()
    passes=t[t.event_type_name.eq('Pass')]
    buildup=passes[passes.location_x.lt(36)]
    prog=passes[(passes.location_x.lt(80)) & (passes.end_location_x.gt(80))]
    shots=t[t.event_type_name.eq('Shot')]
    pressures=t[t.event_type_name.eq('Pressure')]
    losses=t[t.event_type_name.isin(['Pass','Carry']) & t.outcome_name.astype(str).str.lower().isin(['incomplete','out'])]
    setpieces=t[t.play_pattern_name.isin(['From Corner','From Free Kick','From Throw In'])]
    return {
        'team_events':len(t),'passes':len(passes),'buildup_passes':len(buildup),'progressions_to_final_third':len(prog),
        'shots':len(shots),'xg':float(shots.statsbomb_xg.fillna(0).sum()),'pressures':len(pressures),
        'counterpress_events':int(t.counterpress.fillna(False).astype(bool).sum()),'recorded_losses':len(losses),
        'set_piece_events':len(setpieces),'under_pressure_events':int(t.under_pressure.fillna(False).astype(bool).sum())
    }

def run(paths, output_dir, target_team='América'):
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    raw,events,frames=load_competition_csvs(paths)
    audit=validate(raw,events,frames)
    ctx=add_score_context(events,target_team)
    poss=build_possessions(ctx)
    beh=behavior_features(ctx,target_team)
    # CSV for portability (parquet optional dependency not required)
    ctx.to_csv(output_dir/'events_unique.csv',index=False)
    frames.to_csv(output_dir/'freeze_frames.csv',index=False)
    poss.to_csv(output_dir/'possessions.csv',index=False)
    summary={'target_team':target_team,'audit':audit,'behavior':beh,
             'score_state_event_counts':ctx['score_state'].value_counts().to_dict()}
    with open(output_dir/'sprint2_summary.json','w',encoding='utf-8') as f: json.dump(summary,f,ensure_ascii=False,indent=2)
    return summary
