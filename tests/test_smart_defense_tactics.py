import numpy as np
import pandas as pd
import pytest
from intelligence.smart_defense_tactics import analyze_smart_defense,build_smart_defense
from visualization.smart_defense_maps import scenario_events,scenario_map


def e(**kw):
    v=dict(match_id='m1',period=1,possession=1,possession_team='Rival',team='Rival',
           index=1,minute=10, timestamp_seconds=600,event_type='Pass',type_name=None,
           play_pattern_name='Regular Play',location_x=50.,location_y=35.,end_location_x=90.,
           end_location_y=35.,score_state='drawing',statsbomb_xg=np.nan,player='Opp',event_id='id1')
    v.update(kw);return v


def fixture():
    return pd.DataFrame([
        e(index=1,play_pattern_name='From Counter'),
        e(index=2,team='America',player='Def1',event_type='Pressure',location_x=55,timestamp_seconds=602,event_id='id2'),
        e(index=3,team='Rival',event_type='Shot',location_x=108,location_y=34,statsbomb_xg=.3,timestamp_seconds=604,event_id='id3'),
        e(index=4,possession=2,possession_team='America',team='America',event_type='Ball Recovery',player='Def2',timestamp_seconds=605,event_id='id4'),
        e(index=5,possession=3,play_pattern_name='From Corner',type_name='Corner',timestamp_seconds=800,minute=14,event_id='id5'),
        e(index=6,possession=3,team='America',event_type='Clearance',player='Def2',timestamp_seconds=801,event_id='id6'),
        e(index=7,possession=3,team='Rival',event_type='Pass',location_x=103,location_y=44,timestamp_seconds=802,event_id='id7'),
        e(index=8,possession=4,possession_team='America',team='America',event_type='Pass',timestamp_seconds=810,event_id='id8'),
        e(index=9,match_id='m2',possession=1,possession_team='Rival2',team='Rival2',timestamp_seconds=600,event_id='id9'),
    ])


def test_explicit_counter_and_corner():
    d,p,meta=build_smart_defense(fixture(),'America')
    assert len(d)==2
    assert set(d['scenario'])=={'Contraataque etiquetado','Córner rival'}
    assert d.loc[d.scenario.eq('Contraataque etiquetado'),'shot_count'].iloc[0]==1
    assert d.loc[d.scenario.eq('Contraataque etiquetado'),'xg_conceded'].iloc[0]==.3
    assert set(p.player)=={'Def1','Def2'}


def test_explicit_owner_required():
    d,p,meta=build_smart_defense(fixture().drop(columns=['possession_team']),'America')
    assert d.empty and p.empty and meta['status']=='NOT_COMPUTABLE'


def test_no_xg_is_null_not_zero():
    f=fixture();f.loc[f.event_type.eq('Shot'),'statsbomb_xg']=np.nan
    d,_,_,_=analyze_smart_defense(f,'America')
    assert d.loc[d.shot_count.gt(0),'xg_conceded'].isna().all()
    assert not d.loc[d.shot_count.gt(0),'xg_complete'].any()


def test_roles_are_actions_not_player_quality():
    d,p,s,c=analyze_smart_defense(fixture(),'America')
    assert 'players' in s['scenarios']['Córner rival']
    assert s['scenarios']['Córner rival']['status']=='EXPLORATORY'
    assert not c  # One match; no repeatable-tactic claims


def test_no_leak_across_possessions_and_matches():
    d,_,_=build_smart_defense(fixture(),'America')
    assert d['match_id'].nunique()==1
    assert d['shot_count'].sum()==1
    assert d['registered_followup_recovery_5s'].sum()==1


def test_maps_align_coordinates():
    ev=fixture();d,_,_=build_smart_defense(ev,'America')
    interventions,shots=scenario_events(ev,d,'America')
    assert len(interventions)==2 and len(shots)==1
    fig=scenario_map(ev,d,'America')
    assert len(fig.axes)==2


def test_missing_mandatory_raises():
    with pytest.raises(ValueError):build_smart_defense(pd.DataFrame({'team':['America']}),'America')
