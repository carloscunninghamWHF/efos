import pandas as pd
import pytest
from intelligence.defensive_open_play import analyze
from intelligence.defensive_insights import enrich,zone_exposure,recovery_stats
from visualization.defensive_open_play_maps import _def_actions,freeze_frame


def fixture(restart=False, stopped=False, period=1):
    rows=[]
    for i,(owner,team,typ,sec,x,y,ex,ey,cp) in enumerate([
        ('A','A','Pass',0,40,40,60,40,False),
        ('B','B','Pass',1,60,10,90,10,False),
        ('B','A','Pressure',2,30,70,None,None,True),
        ('B','B','Carry',3,90,10,105,40,False),
        ('B','B','Shot',4,105,40,None,None,False),
        ('A','A','Pass',5,15,40,30,40,False)]):
        rows.append(dict(event_id=f'e{i}',index=i+1,match_id='M1',period=period if i==5 else 1,
            team=team,possession_team=owner,possession=1 if i==0 else 3 if i==5 else 2,
            event_type='Foul Won' if stopped and i==4 else typ,
            minute=0,second=sec,location_x=x,location_y=y,end_location_x=ex,end_location_y=ey,
            counterpress=cp,player=team+' player',play_pattern_name='From Free Kick' if restart and i==5 else 'From Counter' if 1<=i<=4 else 'Regular Play',
            outcome_name='Incomplete' if i==0 else '',statsbomb_xg=.2 if typ=='Shot' else None))
    return pd.DataFrame(rows)


def insights(e):
    s,_=analyze(e,'A')
    return enrich(s,e,'A')


def test_tagged_counterpress_across_counter_scenario_and_control_location():
    d=insights(fixture());r=d.iloc[0]
    assert r.counterpress_observed and r.control_confirmed
    assert r.control_seconds==3 and r.control_within_10s
    assert (r.control_x,r.control_y)==(105,40)
    assert r.control_event_id=='e5' and r.cp_event_id=='e2'
    assert r.entry_event_id=='e1' and r.shot_after_entry
    assert recovery_stats(d)['n']==1


@pytest.mark.parametrize('kw',[{'restart':True},{'stopped':True},{'period':2}])
def test_no_confirmed_control_across_restart_stop_or_half(kw):
    assert not insights(fixture(**kw)).iloc[0].control_confirmed


def test_no_next_control_is_unknown_not_success():
    e=fixture().iloc[:-1]
    d=insights(e)
    assert not d.iloc[0].control_confirmed
    assert pd.isna(d.iloc[0].control_x)


def test_incomplete_entry_excluded_and_missing_xg_not_zero():
    e=fixture(); e.loc[e.event_type.eq('Shot'),'statsbomb_xg']=float('nan')
    z=zone_exposure(insights(e))
    assert z.iloc[0].cobertura_xg==0 and pd.isna(z.iloc[0].xg_pos)
    e.loc[e.event_id.eq('e1'),'outcome_name']='Incomplete'
    assert zone_exposure(insights(e)).empty


def test_only_first_entry_counted():
    e=fixture();e.loc[e.event_id.eq('e3'),['location_x','end_location_x','end_location_y']]=[70,100,75]
    z=zone_exposure(insights(e))
    assert z.posesiones.sum()==1 and z.iloc[0].zona.endswith('franja inferior')


def test_defender_and_360_use_rival_attacking_direction():
    e=fixture();d=_def_actions(e,'A')
    assert list(d.location_x)==[90] and list(d.location_y)==[10]
    fig=freeze_frame({'freeze_frame':[{'teammate':True,'location':[20,30]}]},True,'A')
    assert list(fig.data[0].x)==[100] and list(fig.data[0].y)==[50]
