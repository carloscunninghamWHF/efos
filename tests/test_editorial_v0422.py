"""Focused regression tests for defensive rivalry scope and continuous 360 animation."""
import numpy as np
import pandas as pd

from intelligence.defense_scope import opponent_match_scope
from intelligence.transition_voronoi import voronoi_polygons
from visualization import transition_animation as TA
from visualization.defensive_open_play_maps import scenario_pitch
from intelligence.defensive_open_play import STATES


def _events():
    return pd.DataFrame([
        {'match_id':'m1','possession':4,'team':'A','event_type':'Pressure','location_x':35,'location_y':20,
         'end_location_x':np.nan,'end_location_y':np.nan},
        {'match_id':'m1','possession':4,'team':'B','event_type':'Pass','location_x':30,'location_y':32,
         'end_location_x':65,'end_location_y':33},
        {'match_id':'m2','possession':5,'team':'A','event_type':'Pressure','location_x':25,'location_y':22,
         'end_location_x':np.nan,'end_location_y':np.nan},
        {'match_id':'m2','possession':5,'team':'C','event_type':'Shot','location_x':103,'location_y':42,
         'end_location_x':np.nan,'end_location_y':np.nan},
    ])


def _summary():
    return pd.DataFrame([
        dict(match_id='m1',possession=4,scenario=STATES[0],shot=0,xg=0,xg_complete=True,
             n_pressures=1,first_contact_x=35,first_contact_y=20),
        dict(match_id='m2',possession=5,scenario=STATES[1],shot=1,xg=.15,xg_complete=True,
             n_pressures=1,first_contact_x=25,first_contact_y=22),
    ])


def test_opponents_and_match_filters_align_events_and_denominators():
    s,e,m=opponent_match_scope(_summary(),_events(),'A','B','Todos los partidos')
    assert len(s)==1 and len(e)==2
    assert s.iloc[0].shot==0 and e.match_id.unique().tolist()==['m1']
    assert m=={'m1':'B','m2':'C'}
    s,e,_=opponent_match_scope(_summary(),_events(),'A','Todos los rivales','m2')
    assert len(s)==1 and s.iloc[0].shot==1 and set(e.team)=={'A','C'}


def test_unknown_opponent_does_not_guess_or_blend():
    s,e,_=opponent_match_scope(_summary(),_events(),'A','Inexistente')
    assert s.empty and e.empty


def test_situation_pitches_use_selected_scenario_only():
    s,e,_=opponent_match_scope(_summary(),_events(),'A','B')
    fig=scenario_pitch(s,e,'A',STATES[0])
    assert fig.layout.title.text==STATES[0]
    assert any(t.type=='histogram2d' for t in fig.data)


def test_voronoi_cells_stay_on_pitch_and_partition():
    polys=voronoi_polygons(np.array([[25,40],[95,40]],float))
    assert len(polys)==2
    assert all((p>=-1e-6).all() and (p[:,0]<=120+1e-6).all() and (p[:,1]<=80+1e-6).all() for p in polys)
    assert abs(max(polys[0][:,0])-60)<1e-5


def _frame(x):
    return {'freeze_frame':[{'location':[x,28],'actor':True,'teammate':True},
                            {'location':[x+8,37],'actor':False,'teammate':True},
                            {'location':[x+24,33],'actor':False,'teammate':False}],
            'visible_area':[0,0,120,0,120,80,0,80]}


def test_360_animation_uses_real_event_frames_and_marks_interpolation():
    events=pd.DataFrame([
        dict(event_id='1',team='A',match_id='m1',period=1,timestamp_seconds=80,event_type='Ball Recovery',
             location_x=30,location_y=30,end_location_x=39,end_location_y=32,player='Uno'),
        dict(event_id='2',team='A',match_id='m1',period=1,timestamp_seconds=83,event_type='Pass',
             location_x=39,location_y=32,end_location_x=65,end_location_y=40,player='Dos'),
    ])
    steps=TA.build_sequence(events,{'1':_frame(30),'2':_frame(39)},'A','1')
    assert len(steps)==2
    timeline=TA.timeline(steps,fps=4)
    assert len(timeline)>len(steps)
    fig=TA.plotly_animation(steps,'A','Caso real',fps=4)
    assert len(fig.frames)==len(timeline)
    assert len(fig.data)==4


def test_360_missing_frames_does_not_make_up_positions():
    events=pd.DataFrame([dict(event_id='1',team='A',match_id='m1',period=1,timestamp_seconds=80,
                              event_type='Ball Recovery',location_x=30,location_y=30)])
    assert TA.build_sequence(events,{},'A','1')==[]
