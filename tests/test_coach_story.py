import json
import pandas as pd
from coach_story.story_builder import build_coach_story
from coach_story.report_generator import render_coach_story_md


def _result():
    events=pd.DataFrame([
        {'match_id':'m1','team':'A','event_type':'Pass','timestamp_seconds':1.,'possession':1,'location_x':20.,'location_y':40.},
        {'match_id':'m2','team':'A','event_type':'Pass','timestamp_seconds':1.,'possession':1,'location_x':30.,'location_y':20.},
        {'match_id':'m3','team':'A','event_type':'Pressure','timestamp_seconds':1.,'possession':2,'location_x':90.,'location_y':10.},
    ])
    pc=pd.DataFrame([
        {'match_id':'m1','team':'A','pci':.3,'lane_closure':None},
        {'match_id':'m2','team':'A','pci':.7,'lane_closure':None},
        {'match_id':'m3','team':'A','pci':.5,'lane_closure':None},
    ])
    mw=pd.DataFrame([
        {'match_id':'m1','ESI':60.,'OC':50.,'HPS':55.,'RPS':70.,'DS':65.,'DER':60.},
        {'match_id':'m2','ESI':65.,'OC':55.,'HPS':60.,'RPS':75.,'DS':68.,'DER':62.},
        {'match_id':'m3','ESI':70.,'OC':60.,'HPS':67.,'RPS':78.,'DS':72.,'DER':66.},
    ])
    principles=pd.DataFrame([{'principle':'High-block pressure','value_pct':45.,'confidence':72.,'evidence_n':120,'source':'PATTERN_ENGINE'}])
    traps=pd.DataFrame([{'successful':True,'outcome_type':'Backward pass','pressure_source':'EVENT_PROXY'}])
    return {
        'events':events,'pressure_context':pc,'pressure_summary':{'mean_pci':.5,'high_pressure_rate':1/3,'lane_closure_coverage':0.},
        'hps_meta':{'retention':.8,'progression':.6,'value_preservation':.55,'decision_stability':.7,'n_actions':300,'mean_pci':.5},
        'esi_dimensions':{'OC':55.,'HPS':65.,'RPS':80.,'DS':70.,'DER':60.},'ESI':66.,
        'traps':traps,'trap_metrics':{'trap_attempts':1,'successful_traps':1,'DTE':100.,'trap_rate':10.},
        'cts':{'construction':50.,'progression':60.,'attack':70.,'defense':55.,'transition':75.,'adaptation':0.,'trap_efficiency':100.,'pressure_resistance':65.,'mean_pressure_context':50.,'confidence':80.},
        'principles':principles,'match_windows':mw,
    }


def test_story_is_evidence_first_and_serializable():
    story,evidence=build_coach_story(_result(),'A')
    assert story['team']=='A'
    assert evidence['method']=='Data -> Rule -> Evidence -> Narrative'
    assert len(evidence['claims'])>=8
    assert all({'claim','evidence','confidence','limitation'} <= set(c) for c in evidence['claims'])
    json.dumps(story,ensure_ascii=False); json.dumps(evidence,ensure_ascii=False)


def test_markdown_has_required_sections():
    story,evidence=build_coach_story(_result(),'A')
    md=render_coach_story_md(story,evidence)
    for title in ['Identidad general','Comportamiento bajo presión','Defensive Traps','Coach Tactical Signature','Evolución dentro de la muestra','Límites metodológicos']:
        assert title in md
    assert 'claims auditables' in md


def test_temporal_order_is_explicit_when_dates_missing():
    story,_=build_coach_story(_result(),'A')
    assert story['temporal_evolution']['ordering']=='dataset_order'
