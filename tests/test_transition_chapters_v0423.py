"""EFOS v0.4.23: event-scoped editorial transitions, no synthetic evidence."""
import numpy as np
import pandas as pd

from intelligence.transition_story import analyze_transitions, describe_transitions, find_360_anchors
from visualization.transition_animation import snapshot_figure, _step


def _e(mid,period,pos,owner,team,event,ts,event_id,**extra):
    return dict(match_id=mid,period=period,possession=pos,possession_team=owner,
                team=team,event_type=event,timestamp_seconds=ts,event_id=event_id,
                index=int(event_id[1:]),minute=4,player='Jugador',location_x=50,location_y=40,
                end_location_x=60,end_location_y=40,**extra)


def sample():
    # m1: 1 confirmed regain; 1 failed pass DOES NOT switch possession; 1 confirmed loss;
    # a shot against 9s later; regain in 5 s (but separate following possession).
    return pd.DataFrame([
        _e('m1',1,1,'Rival','Rival','Pass',1,'e1'),
        _e('m1',1,2,'Equipo','Equipo','Ball Recovery',4,'e2'),
        _e('m1',1,2,'Equipo','Equipo','Pass',6,'e3',pass_outcome='Incomplete'),
        _e('m1',1,2,'Equipo','Equipo','Pass',10,'e4'),
        _e('m1',1,2,'Equipo','Equipo','Shot',16,'e5',statsbomb_xg=.22),
        _e('m1',1,2,'Equipo','Equipo','Miscontrol',20,'e6'),
        _e('m1',1,3,'Rival','Rival','Pass',21,'e7'),
        _e('m1',1,3,'Rival','Equipo','Pressure',23,'e8'),
        _e('m1',1,3,'Rival','Rival','Shot',29,'e9',statsbomb_xg=.19),
        _e('m1',1,4,'Equipo','Equipo','Ball Recovery',30,'e10'),
        # Period boundary: next period is not allowed to extend windows.
        _e('m1',2,5,'Rival','Rival','Pass',1,'e11'),
        _e('m1',2,6,'Equipo','Equipo','Interception',3,'e12',outcome_name='Lost In Play'),
        # Other match must not contaminate the summary.
        _e('m2',1,1,'Rival','Rival','Pass',1,'e13'),
    ])


def test_uses_confirmed_possession_switches_and_real_shot_only():
    result=analyze_transitions(sample(),'Equipo')
    assert result['status']=='ok'
    off=result['offensive']; defense=result['defensive']
    assert len(off)==2  # e2, e10; failed interception e12 excluded
    assert len(defense)==1
    assert defense.iloc[0].event_id=='e6'  # NOT incomplete pass e3
    assert int(defense.iloc[0].pressures_5s)==1
    assert int(defense.iloc[0].rival_shots_15s)==1
    assert not defense.iloc[0].recovered_5s  # e10 at +10 s
    assert off.iloc[0].shots==1 and off.iloc[0].xg==.22
    assert off.iloc[0].first_ball_action == 'Pass'
    assert off.iloc[0].first_action_after_s == 2
    assert defense.iloc[0].first_pressure_after_s == 3
    assert len(off.iloc[0].event_ids)==3  # only within 15 s of e2


def test_denominators_and_no_invented_xg():
    r=analyze_transitions(sample(),'Equipo')
    offensive=describe_transitions(r,'offensive')
    defensive=describe_transitions(r,'defensive')
    assert offensive['n']==2 and offensive['shot_possessions']==1
    assert offensive['coverage']==(1,1) and offensive['rate']==.5
    assert defensive['n']==1 and defensive['coverage']==(1,1)
    missing=sample().drop(columns=['statsbomb_xg'])
    no_xg=describe_transitions(analyze_transitions(missing,'Equipo'),'offensive')
    assert no_xg['xg'] is None and no_xg['coverage']==(0,1)


def test_match_filter_and_invalid_input_no_synthetic_results():
    assert analyze_transitions(sample(),'Equipo',['m2'])['offensive'].empty
    assert analyze_transitions(pd.DataFrame(),'Equipo')['status']=='unavailable'
    assert describe_transitions(analyze_transitions(sample(),'Otro equipo'),'offensive')['n']==0


def test_snapshot_uses_observed_positions_only_without_interpolation():
    r=pd.Series(dict(team='Equipo',timestamp_seconds=60,event_type='Ball Recovery',player='A',
                     location_x=25,location_y=30,end_location_x=25,end_location_y=30))
    frame={'freeze_frame':[
        {'location':[20,20],'teammate':True,'actor':False},
        {'location':[30,20],'teammate':True,'actor':False},
        {'location':[50,40],'teammate':False,'actor':False},
        {'location':[60,45],'teammate':False,'actor':False},
    ],'visible_area':[0,0,120,0,120,80,0,80]}
    step=_step(r,frame,'Equipo',60)
    fig=snapshot_figure(step,'Equipo',show_voronoi=True)
    assert len(fig.data)==3
    assert len([sh for sh in fig.layout.shapes if sh.type=='path'])>=4
    assert not fig.frames
    absent=dict(frame);absent['visible_area']=None
    bare=snapshot_figure(_step(r,absent,'Equipo',60),'Equipo',show_voronoi=True)
    assert not [sh for sh in bare.layout.shapes if sh.type=='path']


def test_home_navigation_has_no_duplicate_transition_tab():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'visualization'/'efos_dashboard.py').read_text()
    lines=text.split('NAV_ITEMS = ',1)[1].split('# Old deep links',1)[0]
    assert 'Cómo ataca' in lines and 'Cómo defiende' in lines
    assert '"Transiciones"' not in lines


def test_360_photo_after_anchor_is_available_but_not_invented_at_t0():
    e=sample()
    # A real 360 photo can exist at the next observed pass, not the recovery.
    images={'e4', 'e9'}
    off=find_360_anchors(e,'Equipo','Tras recuperación',images,anchor_ids={'e2'})
    assert off.event_id.astype(str).tolist()==['e2']
    assert find_360_anchors(e,'Equipo','Tras recuperación',{'e13'},anchor_ids={'e2'}).empty
    defense=find_360_anchors(e,'Equipo','Tras pérdida',images,anchor_ids={'e6'})
    assert defense.event_id.astype(str).tolist()==['e6']
