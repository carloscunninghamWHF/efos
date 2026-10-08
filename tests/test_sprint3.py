import pandas as pd
from metrics.esi import compute_dimensions,compute_esi
from intelligence.match_windows import compute_match_windows
from intelligence.dtc import build_dtc
from players.lap import compute_lap
from coach_story.principles import detect_principles
from objects.transitions import detect_transitions

def sample():
    rows=[]
    for i in range(1,21):
        team='A' if i<11 or i>13 else 'B'; poss=1 if i<11 else (2 if i<=13 else 3); et='Pass'
        if i==11: et='Pass'
        if i==12: et='Pressure'; team='A'
        if i==18: et='Pressure'
        if i==20: et='Shot'
        rows.append({'match_id':'m1','event_id':str(i),'index':i,'possession':poss,'possession_team':'A' if poss in [1,3] else 'B','team':team,'timestamp_seconds':float(i*2),'event_type':et,'location_x':float(min(110,i*6)),'location_y':40.,'end_location_x':float(min(115,i*6+20)),'end_location_y':40.,'under_pressure':i%3==0,'outcome_name':None,'pass_success_probability':.8,'score_state':'drawing','player':'P1','statsbomb_xg':.1 if et=='Shot' else 0.0})
    return pd.DataFrame(rows)

def test_esi_and_context_windows():
    e=sample(); tr=detect_transitions(e); d=compute_dimensions(e,'A',tr); assert set(d)=={'OC','HPS','RPS','DS','DER'}; assert 0<=compute_esi(d)<=100
    w=compute_match_windows(e,'A',tr); assert len(w)>=1 and 'ESI' in w

def test_dtc_lap_principles():
    e=sample(); tr=detect_transitions(e); w=compute_match_windows(e,'A',tr); states,m=build_dtc(w); assert 'state' in states
    lap=compute_lap(e,'A'); assert not lap.empty and 'LAP' in lap
    p=detect_principles(e,'A',tr); assert not p.empty and {'principle','confidence','value_pct'}.issubset(p.columns)
