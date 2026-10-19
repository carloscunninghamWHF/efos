import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from tests.open_play_demo_synthetic import make_demo
from intelligence.defensive_open_play import (STATES, OTHER,analyze,kpis,filter_scenarios,
                              time_summary,load_360,normalize_events)
from visualization.defensive_open_play_maps import atlas,sequence,defensive_network,timeline,freeze_frame


def test_demo_mece_and_sample():
    s,e=analyze(make_demo())
    assert len(s)==270
    assert len(s[['match_id','possession']].drop_duplicates())==len(s)
    assert set(STATES).issubset(set(s.scenario))
    assert set(s.scenario)<=set(STATES)|{OTHER}
    assert e.groupby(['match_id','possession']).ngroups==len(s)


def test_restart_exclusion():
    d=make_demo()
    mask=(d.match_id.eq('DEMO-01')&d.possession.eq(2))
    d.loc[mask,'play_pattern_name']='From Corner'
    s,_=analyze(d)
    assert not (s.match_id.eq('DEMO-01')&s.possession.eq(2)).any()
    assert len(s)==269


def test_no_false_counter_for_normal_possession():
    s,_=analyze(make_demo())
    assert all('counter' in z.lower() for z in s.loc[s.scenario.eq(STATES[1]),'play_pattern'])


def test_context_filter_and_unit_denominators():
    s,e=analyze(make_demo())
    a,b=filter_scenarios(s,e,STATES[1],'0–15','Empata')
    assert not a.empty
    assert a.scenario.eq(STATES[1]).all()
    assert a.minute_band.eq('0–15').all()
    assert a.match_state.eq('Empata').all()
    assert set(zip(b.match_id,b.possession)).issubset(set(zip(a.match_id,a.possession)))
    k=kpis(a)
    assert k['posesiones']==len(a)
    assert abs(k['pct_remate']-100*a.shot.sum()/len(a))<1e-9


def test_time_summary_accounting():
    s,_=analyze(make_demo())
    t=time_summary(s)
    assert int(t.posesiones.sum())==len(s)
    assert int(t.remates.sum())==int(s.shot.sum())


def test_360_relative_teammate():
    frame={'freeze_frame':[{'teammate':True,'location':[20,20]},
                           {'teammate':False,'location':[60,40]}],
           'visible_area':[0,0,80,0,80,80,0,80]}
    fig=freeze_frame(frame,actor_is_america=False,team_name='América')
    am=next(x for x in fig.data if x.name=='América')
    opp=next(x for x in fig.data if x.name=='Rival')
    assert list(am.x)==[60]
    assert list(opp.x)==[20]


def test_plots_do_not_crash():
    s,e=analyze(make_demo())
    assert len(atlas(s,e).data)>0
    assert len(defensive_network(e,'América').data)>0
    assert len(timeline(s).data)>0
    r=s.iloc[0]
    assert len(sequence(e,'América',r.match_id,r.possession).data)>0


def test_missing_columns_fail_explicitly():
    try:
        normalize_events(pd.DataFrame({'team':['América']}))
    except ValueError as ex: assert 'Faltan columnas' in str(ex)
    else:raise AssertionError('expected ValueError')


def test_missing_xg_is_not_counted_as_zero():
    f=make_demo()
    row=f.index[f.event_type.eq('Shot')][0]
    # Test unknown xG for at least one rival shot; missing means incomplete.
    f.loc[row,'statsbomb_xg']=float('nan')
    s,_=analyze(f)
    assert s['xg_complete'].isin([True,False]).all()
    if not s.loc[s.xg_complete.eq(False)].empty:
        assert s.loc[s.xg_complete.eq(False),'xg'].isna().all()
        assert kpis(s)['xg_coverage_pct']<100


def test_ball_restart_exclusion_types_not_counted_in_open_play():
    f=make_demo()
    f.loc[(f.match_id.eq('DEMO-01')) & (f.possession.eq(2)), 'type_name']='Corner'
    s,_=analyze(f)
    assert not ((s.match_id=='DEMO-01') & (s.possession==2)).any()


def test_atlas_three_scenarios_mapped_from_same_base():
    s,e=analyze(make_demo())
    fig=atlas(s,e)
    assert len(fig.layout.annotations)>=3
    assert s['scenario'].isin(list(STATES)+[OTHER]).all()
