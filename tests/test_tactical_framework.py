import pandas as pd
from coach_story.tactical_framework import extract_tactical_framework
from interpretation.tactical_framework import interpret_tactical_framework


def _events(team='A'):
    rows=[
        # duplicated event to ensure tactical layer is idempotent to freeze-frame style row expansion
        {'event_id':'e1','match_id':'m1','index':1,'team':team,'event_type':'Pass','player':'P1','pass_recipient_name':'P2','possession':1,'timestamp_seconds':1.,'location_x':30.,'location_y':40.,'end_location_x':45.,'end_location_y':40.,'under_pressure':True,'outcome_name':None,'counterpress':False,'possession_directness':.5,'obv_total_net':.02},
        {'event_id':'e1','match_id':'m1','index':1,'team':team,'event_type':'Pass','player':'P1','pass_recipient_name':'P2','possession':1,'timestamp_seconds':1.,'location_x':30.,'location_y':40.,'end_location_x':45.,'end_location_y':40.,'under_pressure':True,'outcome_name':None,'counterpress':False,'possession_directness':.5,'obv_total_net':.02},
        {'event_id':'e2','match_id':'m1','index':2,'team':team,'event_type':'Pass','player':'P2','pass_recipient_name':'P3','possession':1,'timestamp_seconds':3.,'location_x':45.,'location_y':40.,'end_location_x':62.,'end_location_y':25.,'under_pressure':False,'outcome_name':None,'counterpress':False,'possession_directness':.6,'obv_total_net':.03},
        {'event_id':'e3','match_id':'m1','index':3,'team':team,'event_type':'Pressure','player':'P4','possession':2,'timestamp_seconds':10.,'location_x':90.,'location_y':10.,'under_pressure':False,'outcome_name':None,'counterpress':True,'obv_total_net':0.},
        {'event_id':'e4','match_id':'m1','index':4,'team':team,'event_type':'Shot','player':'P3','possession':3,'timestamp_seconds':20.,'location_x':105.,'location_y':40.,'under_pressure':False,'outcome_name':'Saved','counterpress':False,'statsbomb_xg':.25,'obv_total_net':.05},
        {'event_id':'e5','match_id':'m1','index':5,'team':'B','event_type':'Pass','player':'Q1','pass_recipient_name':'Q2','possession':4,'timestamp_seconds':30.,'location_x':50.,'location_y':40.,'end_location_x':70.,'end_location_y':40.,'under_pressure':True,'outcome_name':'Pass Offside','counterpress':False,'obv_total_net':-.01},
    ]
    return pd.DataFrame(rows)


def test_tactical_framework_dedupes_and_counts_scalars():
    tf=extract_tactical_framework(_events(),'A')
    assert tf['data_quality']['duplicates_removed']==1
    assert isinstance(tf['defensive_profile']['counterpress']['count'], int)
    assert tf['defensive_profile']['counterpress']['count']==1
    assert tf['defensive_profile']['opponent_offside_outcomes']['count']==1


def test_tactical_framework_labels_proxies_and_guardrails():
    tf=extract_tactical_framework(_events(),'A')
    assert tf['construction_progression']['pressure_attraction_passes']['source']=='EVENT_PROXY'
    assert tf['offensive_microconcepts']['cross_to_danger_zone_proxy']['confidence']=='LOW'
    assert 'no prueba' in tf['methodological_guardrail'].lower()
    interpreted=interpret_tactical_framework(tf)
    assert len(interpreted['claims']) >= 5
    assert any(c['source'] in {'EVENT_PROXY','SEQUENCE_PROXY','EVENT/SEQUENCE_PROXY'} for c in interpreted['claims'])


def test_team_name_does_not_change_tactical_math():
    a=extract_tactical_framework(_events('A'),'A')
    b=extract_tactical_framework(_events('Renamed'),'Renamed')
    assert a['defensive_profile']['counterpress']['count']==b['defensive_profile']['counterpress']['count']
    assert a['construction_progression']['pressure_attraction_passes']['count']==b['construction_progression']['pressure_attraction_passes']['count']
    assert a['value_purpose']['xg']['total']==b['value_purpose']['xg']['total']
