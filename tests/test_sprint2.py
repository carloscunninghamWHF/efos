import pandas as pd
from ingestion.validation import deduplicate_events, validate_events
from objects.possessions import build_possessions
from objects.sequences import build_sequences, contextual_windows
from objects.transitions import detect_transitions
from context.game_context import add_score_state
from behavior.tactical import tactical_summary
from intelligence.cts import compute_cts

def sample():
    return pd.DataFrame([
      {"match_id":"m1","event_id":"1","index":1,"possession":1,"possession_team":"A","team":"A","timestamp_seconds":1.,"event_type":"Pass","location_x":10.,"location_y":40.,"end_location_x":30.,"end_location_y":40.,"under_pressure":False,"shot_outcome":None},
      {"match_id":"m1","event_id":"2","index":2,"possession":1,"possession_team":"A","team":"A","timestamp_seconds":3.,"event_type":"Pass","location_x":30.,"location_y":40.,"end_location_x":90.,"end_location_y":40.,"under_pressure":False,"shot_outcome":None},
      {"match_id":"m1","event_id":"3","index":3,"possession":2,"possession_team":"B","team":"B","timestamp_seconds":5.,"event_type":"Pass","location_x":20.,"location_y":20.,"end_location_x":25.,"end_location_y":20.,"under_pressure":False,"shot_outcome":None},
      {"match_id":"m1","event_id":"4","index":4,"possession":2,"possession_team":"B","team":"A","timestamp_seconds":7.,"event_type":"Pressure","location_x":70.,"location_y":20.,"end_location_x":None,"end_location_y":None,"under_pressure":False,"shot_outcome":None},
      {"match_id":"m1","event_id":"5","index":5,"possession":3,"possession_team":"A","team":"A","timestamp_seconds":9.,"event_type":"Shot","location_x":100.,"location_y":40.,"end_location_x":None,"end_location_y":None,"under_pressure":False,"shot_outcome":"Goal"},
    ])

def test_dedup_and_validation():
    d=sample(); d=pd.concat([d,d.iloc[[0]]],ignore_index=True)
    clean,meta=deduplicate_events(d); assert len(clean)==5 and meta["duplicates_removed"]==1
    assert validate_events(clean, expected_matches=1)["ok"]

def test_possessions_and_phases():
    d=sample(); p=build_possessions(d); assert len(p)==3
    s=build_sequences(d); assert "phase" in s and set(s.phase).issuperset({"build_up","final_third"})

def test_transition_elapsed_time():
    tr=detect_transitions(sample(),5.0); assert len(tr)>=1
    assert tr.iloc[0].response_within_5s

def test_context_goal_and_summary():
    c=add_score_state(sample(),"A"); assert c.iloc[-1].score_state=="winning"
    sm=tactical_summary(c,"A"); assert sm["build_up_passes"]>=1
    cts=compute_cts(sm,1.0); assert 0<=cts["transition"]<=100

def test_contextual_windows():
    d=sample(); w=contextual_windows(d, lambda x: x.event_type.eq("Shot"), n=5)
    assert len(w)==4 and set(w.target_event_id)=={"5"}
