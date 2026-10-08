import json
import pandas as pd
from intelligence.pressure_context import build_pressure_context
from metrics.hps import compute_hps
from intelligence.trap_detection import detect_traps
from coach_story.principles import detect_principles
from intelligence.cts import compute_cts
from ingestion.defensive_responsibility import extract_defensive_responsibility


def sample():
    return pd.DataFrame([
        {'match_id':'m1','event_id':'1','index':1,'possession':1,'possession_team':'B','team':'B','timestamp_seconds':1.,'event_type':'Pass','location_x':50.,'location_y':40.,'end_location_x':55.,'end_location_y':20.,'under_pressure':True,'outcome_name':None,'pass_success_probability':.8,'obv_total_net':.01,'control_degree':.6,'pass_length':10.},
        {'match_id':'m1','event_id':'2','index':2,'possession':1,'possession_team':'B','team':'A','timestamp_seconds':2.,'event_type':'Pressure','location_x':60.,'location_y':20.,'end_location_x':None,'end_location_y':None,'under_pressure':False,'outcome_name':None,'pass_success_probability':None,'obv_total_net':0.,'control_degree':None,'pass_length':None},
        {'match_id':'m1','event_id':'3','index':3,'possession':1,'possession_team':'B','team':'B','timestamp_seconds':4.,'event_type':'Pass','location_x':60.,'location_y':10.,'end_location_x':45.,'end_location_y':5.,'under_pressure':True,'outcome_name':'Incomplete','pass_success_probability':.7,'obv_total_net':-.02,'control_degree':.4,'pass_length':35.},
        {'match_id':'m1','event_id':'4','index':4,'possession':2,'possession_team':'A','team':'A','timestamp_seconds':8.,'event_type':'Carry','location_x':40.,'location_y':40.,'end_location_x':55.,'end_location_y':40.,'under_pressure':True,'outcome_name':None,'pass_success_probability':None,'obv_total_net':.02,'control_degree':.7,'pass_length':None},
        {'match_id':'m1','event_id':'5','index':5,'possession':2,'possession_team':'A','team':'A','timestamp_seconds':10.,'event_type':'Dispossessed','location_x':55.,'location_y':40.,'end_location_x':None,'end_location_y':None,'under_pressure':True,'outcome_name':None,'pass_success_probability':None,'obv_total_net':-.03,'control_degree':.5,'pass_length':None},
    ])


def test_pressure_context_and_hps_v2():
    e=sample(); pc=build_pressure_context(e)
    assert {'pci','pressure_source','lane_closure','tti'} <= set(pc.columns)
    assert pc.pci.between(0,1).all()
    score,actions,meta=compute_hps(e,'A',pc)
    assert 0 <= score <= 100 and meta['n_actions']==2
    # Dispossessed must be a failed retained action even with missing outcome_name.
    assert actions.loc[actions.event_type.eq('Dispossessed'),'retention_stability'].iloc[0] == 0.0


def test_360_lane_closure_snapshot_only():
    e=sample(); frames={'1':{'event_id':'1','visible_area':[], 'freeze_frame':[{'teammate':False,'location':[52.,30.]},{'teammate':True,'location':[55.,20.]}]}}
    pc=build_pressure_context(e,frames)
    r=pc.loc[pc.event_id.eq('1')].iloc[0]
    assert pd.notna(r.lane_closure) and r.pressure_source=='360_SNAPSHOT'
    assert pd.isna(r.tti)  # no tracking => never invent TTI


def test_trap_engine_and_coach_story():
    e=sample(); pc=build_pressure_context(e)
    traps,meta=detect_traps(e,'A',pc)
    assert {'trap_attempts','successful_traps','DTE','trap_rate'} <= set(meta)
    p=detect_principles(e,'A',None,pc,traps)
    assert isinstance(p,pd.DataFrame)
    cts=compute_cts({'events':100,'build_up_passes':20,'deep_progressions':5,'final_third_events':20,'pressures':10},.5,meta,75.,{'mean_pci':.6})
    assert {'trap_efficiency','pressure_resistance','mean_pressure_context'} <= set(cts)


def test_defr_long_extraction(tmp_path):
    d=pd.DataFrame({'match_id':[1,1],'id':['e1','e2'],'10_pressure_like_defensive_responsibility_probability':[.4,None],'11_interception_like_defensive_responsibility_probability':[.2,.3]})
    p=tmp_path/'w.csv'; d.to_csv(p,index=False)
    out=extract_defensive_responsibility([p])
    assert len(out)==3 and {'defender_id','responsibility_type','probability'} <= set(out.columns)
