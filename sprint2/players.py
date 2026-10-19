from __future__ import annotations
import numpy as np
import pandas as pd

CRITICAL_TYPES={'Pass','Carries','Dribble','Shot','Ball Receipt*'}


def lap_table(events: pd.DataFrame, target_team='América') -> pd.DataFrame:
    t=events[events.team_name.eq(target_team)].copy()
    crit=t[t.location_x.gt(80) & t.event_type_name.isin(CRITICAL_TYPES) & t.player_name.notna()].copy()
    total=len(crit)
    base=(crit.groupby(['player_id','player_name']).agg(
        critical_actions=('id','nunique'),matches=('match_id','nunique'),
        final_third_obv=('obv_total_net','sum')
    ).reset_index())
    base['LAP_share']=base.critical_actions/max(total,1)
    shots=t[t.event_type_name.eq('Shot') & t.player_name.notna()].groupby(['player_id','player_name']).agg(shots=('id','nunique'),xG=('statsbomb_xg','sum')).reset_index()
    # xA: shot xG attributed to the pass event referenced by key_pass_id.
    shot_keys=t[t.event_type_name.eq('Shot') & t.key_pass_id.notna()][['key_pass_id','statsbomb_xg']].copy()
    shot_keys['key_pass_id']=shot_keys.key_pass_id.astype(str)
    passes=t[t.event_type_name.eq('Pass') & t.player_name.notna()][['id','player_id','player_name']].copy(); passes['id']=passes.id.astype(str)
    xa=passes.merge(shot_keys,left_on='id',right_on='key_pass_id',how='inner').groupby(['player_id','player_name']).statsbomb_xg.sum().reset_index(name='xA')
    out=base.merge(shots,on=['player_id','player_name'],how='left').merge(xa,on=['player_id','player_name'],how='left')
    for c in ['shots','xG','xA']: out[c]=out[c].fillna(0)
    out['xG_xA']=out.xG+out.xA
    return out.sort_values(['LAP_share','xG_xA'],ascending=False).reset_index(drop=True)


def substitution_impacts(events: pd.DataFrame, target_team='América', window_minutes=15) -> pd.DataFrame:
    e=events.sort_values(['match_id','period','index'],kind='stable').copy()
    e['event_seconds']=pd.to_numeric(e.minute,errors='coerce').fillna(0)*60+pd.to_numeric(e.second,errors='coerce').fillna(0)
    subs=e[(e.event_type_name.eq('Substitution')) & (e.team_name.eq(target_team))].copy()
    rows=[]; w=window_minutes*60
    for _,s in subs.iterrows():
        m=e[(e.match_id.eq(s.match_id)) & (e.team_name.eq(target_team))]
        pre=m[(m.event_seconds>=s.event_seconds-w)&(m.event_seconds<s.event_seconds)]
        post=m[(m.event_seconds>s.event_seconds)&(m.event_seconds<=s.event_seconds+w)]
        def stats(x):
            shots=x[x.event_type_name.eq('Shot')]
            return {
                'events':len(x),'passes':int((x.event_type_name=='Pass').sum()),'pressures':int((x.event_type_name=='Pressure').sum()),
                'shots':len(shots),'xg':float(shots.statsbomb_xg.fillna(0).sum()),
                'obv':float(pd.to_numeric(x.obv_total_net,errors='coerce').fillna(0).sum())
            }
        a=stats(pre); b=stats(post)
        rows.append({'match_id':s.match_id,'minute':s.minute,'incoming_player':s.player_name,'outgoing_player':s.substituted_player_name,
                     **{f'pre_{k}':v for k,v in a.items()},**{f'post_{k}':v for k,v in b.items()},
                     'delta_xg':b['xg']-a['xg'],'delta_obv':b['obv']-a['obv'],'delta_pressures':b['pressures']-a['pressures']})
    return pd.DataFrame(rows)
