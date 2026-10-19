from __future__ import annotations
import numpy as np
import pandas as pd

LOSS_PASS_OUTCOMES = {'Incomplete','Out','Pass Offside'}
LOSS_TYPES = {'Dispossessed','Miscontrol'}
RECOVERY_TYPES = {'Ball Recovery','Interception','Pressure'}


def add_event_clock(events: pd.DataFrame) -> pd.DataFrame:
    e = events.copy()
    # StatsBomb minute is cumulative across regulation periods in this dataset.
    e['event_seconds'] = pd.to_numeric(e['minute'], errors='coerce').fillna(0)*60 + pd.to_numeric(e['second'], errors='coerce').fillna(0)
    return e


def mark_losses(events: pd.DataFrame) -> pd.DataFrame:
    e = events.copy()
    pass_loss = e['event_type_name'].eq('Pass') & e['outcome_name'].isin(LOSS_PASS_OUTCOMES)
    dribble_loss = e['event_type_name'].eq('Dribble') & e['outcome_name'].eq('Incomplete')
    explicit_loss = e['event_type_name'].isin(LOSS_TYPES)
    e['is_loss'] = pass_loss | dribble_loss | explicit_loss
    return e


def build_pre_event_windows(events: pd.DataFrame, n: int = 5, target_types=None) -> pd.DataFrame:
    e = events.sort_values(['match_id','period','index'], kind='stable').copy()
    if target_types is None:
        target_types = {'Shot'}
    targets = e[e['event_type_name'].isin(target_types)]
    rows=[]
    for idx,row in targets.iterrows():
        same = e[(e.match_id.eq(row.match_id)) & (e.possession.eq(row.possession)) & (e['index'] < row['index'])]
        pre = same.tail(n)
        for rank,(_,p) in enumerate(pre.iterrows(), start=max(1,n-len(pre)+1)):
            rows.append({
                'target_event_id': row['id'], 'target_type': row['event_type_name'], 'match_id': row['match_id'],
                'possession': row['possession'], 'pre_rank': rank, 'event_id': p['id'], 'event_type_name': p['event_type_name'],
                'team_name': p.get('team_name'), 'player_name': p.get('player_name'), 'location_x': p.get('location_x'),
                'location_y': p.get('location_y'), 'end_location_x': p.get('end_location_x'), 'end_location_y': p.get('end_location_y'),
                'obv_total_net': p.get('obv_total_net')
            })
    return pd.DataFrame(rows)


def build_loss_responses(events: pd.DataFrame, max_seconds: float = 5.0) -> pd.DataFrame:
    e = add_event_clock(mark_losses(events)).sort_values(['match_id','period','index'], kind='stable').copy()
    losses=e[e.is_loss].copy()
    responses=e[e.event_type_name.isin(RECOVERY_TYPES)].copy()
    # Pre-index response events by match/period/team for O(log n) lookup per loss.
    response_groups={}
    for key,g in responses.groupby(['match_id','period','team_name'],dropna=False):
        gg=g.sort_values(['event_seconds','index'],kind='stable')
        response_groups[key]=(gg['event_seconds'].to_numpy(float),gg)
    opp_groups={}
    for key,g in e.groupby(['match_id','period'],dropna=False):
        gg=g.sort_values(['event_seconds','index'],kind='stable')
        opp_groups[key]=gg
    rows=[]
    for _,loss in losses.iterrows():
        key=(loss.match_id,loss.period,loss.team_name)
        r=None
        if key in response_groups:
            secs,gg=response_groups[key]
            pos=int(np.searchsorted(secs,float(loss.event_seconds),side='left'))
            while pos < len(gg):
                cand=gg.iloc[pos]
                if cand['index'] <= loss['index']:
                    pos += 1; continue
                delta=float(cand.event_seconds-loss.event_seconds)
                if delta < 0:
                    pos += 1; continue
                if delta <= max_seconds:
                    r=cand
                break
        period_group=opp_groups.get((loss.match_id,loss.period),pd.DataFrame())
        if len(period_group):
            opp=period_group[(period_group['index']>loss['index']) & (~period_group.team_name.eq(loss.team_name))].head(1)
            opp_in=bool(len(opp) and float(opp.iloc[0].event_seconds-loss.event_seconds)<=max_seconds)
        else: opp_in=False
        rows.append({
            'loss_event_id':loss.id,'match_id':loss.match_id,'period':loss.period,'team_name':loss.team_name,
            'player_name':loss.get('player_name'),'loss_type':loss.event_type_name,'loss_x':loss.get('location_x'),
            'loss_y':loss.get('location_y'),'loss_second':loss.event_seconds,
            'response_event_id': None if r is None else r.id,
            'response_type': None if r is None else r.event_type_name,
            'response_delta_s': np.nan if r is None else float(r.event_seconds-loss.event_seconds),
            'response_within_5s': bool(r is not None),
            'opponent_event_within_5s': opp_in
        })
    return pd.DataFrame(rows)

def build_sequences(events: pd.DataFrame) -> pd.DataFrame:
    e=add_event_clock(events).sort_values(['match_id','possession','period','index'],kind='stable').copy()
    g=e.groupby(['match_id','possession'],dropna=False)
    seq=g.agg(
        possession_team=('possession_team_name','first'), period=('period','first'), start_second=('event_seconds','min'),
        end_second=('event_seconds','max'), start_x=('location_x','first'), end_x=('end_location_x','last'),
        n_events=('id','nunique'), n_passes=('event_type_name',lambda s:int((s=='Pass').sum())),
        n_shots=('event_type_name',lambda s:int((s=='Shot').sum())), obv_total=('obv_total_net','sum'),
        mean_control=('control_degree','mean'), directness=('possession_directness','mean')
    ).reset_index()
    seq['duration_s']=(seq.end_second-seq.start_second).clip(lower=0)
    seq['net_x']=seq.end_x-seq.start_x
    maxx=e.groupby(['match_id','possession'],dropna=False)['location_x'].max().reset_index(name='max_location_x')
    seq=seq.merge(maxx,on=['match_id','possession'],how='left')
    seq['reached_final_third']=seq.end_x.gt(80) | seq.max_location_x.gt(80)
    return seq
