"""Regression tests for the native StatsBomb upload path (no Streamlit dependency)."""
import pandas as pd
from ui.auto_csv import inspect_uploaded_paths, match_labels
from ingestion.statsbomb_auxiliary import extract_statsbomb_auxiliary
from ingestion.input_adapter import load_event_csvs
from run_sprint4 import run


def _native_sample(path):
    data = pd.DataFrame([
        {"id":"shot1", "match_id":100,"index":1,"period":1,"minute":1,"second":1.,
         "event_type_name":"Shot","team_name":"Guadalajara","possession_team_name":"Guadalajara",
         "location_x":80, "location_y":30,"freeze_frame_player_name":"A", "freeze_frame_x":80.,"freeze_frame_y":40.,
         "formation_player_name":None},
        {"id":"shot1", "match_id":100,"index":1,"period":1,"minute":1,"second":1.,
         "event_type_name":"Shot","team_name":"Guadalajara","possession_team_name":"Guadalajara",
         "location_x":80,"location_y":30,"freeze_frame_player_name":"B", "freeze_frame_x":85.,"freeze_frame_y":44.,
         "formation_player_name":None},
        {"id":"lineup", "match_id":100,"index":2,"period":1,"minute":1,"second":2.,
         "event_type_name":"Starting XI","team_name":"Rival","possession_team_name":"Rival",
         "formation_player_name":"C"},
        {"id":"lineup", "match_id":100,"index":2,"period":1,"minute":1,"second":2.,
         "event_type_name":"Starting XI","team_name":"Rival","possession_team_name":"Rival",
         "formation_player_name":"D"},
    ])
    data.to_csv(path,index=False)
    return path


def test_native_detection_and_labels_and_auxiliary(tmp_path):
    path=_native_sample(tmp_path/"Liga_MX_2026_2027_Guadalajara_p1.csv")
    summary=inspect_uploaded_paths([path])
    assert summary['recognized']
    assert summary['formats']==['STATSBOMB_WIDE']
    assert summary['rows']==4 and summary['unique_events']==2
    assert summary['matches']==['100']
    assert match_labels(summary,'Guadalajara')['100'].endswith('vs Rival')
    shots,lineups=extract_statsbomb_auxiliary([path])
    assert len(shots)==2 and shots.event_id.nunique()==1
    assert len(lineups)==2 and lineups.event_id.nunique()==1
    # A canonical event remains one event, rather than two shot-frame rows.
    event_rows,_=load_event_csvs([path])
    assert len(event_rows)==2


def test_unsupported_schema_uses_fallback(tmp_path):
    path=tmp_path/'other.csv'
    pd.DataFrame({'equipo':['X'], 'accion':['Pase']}).to_csv(path,index=False)
    summary=inspect_uploaded_paths([path])
    assert summary['recognized'] is False
    assert summary['unsupported']==['other.csv']


def test_multi_file_preview_deduplicates_ids(tmp_path):
    a=_native_sample(tmp_path/'a.csv')
    b=_native_sample(tmp_path/'b.csv')
    summary=inspect_uploaded_paths([a,b])
    assert summary['unique_events']==2
    assert summary['rows']==8


def test_runner_filters_only_selected_matches(tmp_path):
    # Use a known working EFOS-normalized test fixture and do not fabricate frames.
    source=pd.read_csv('data/raw/csv_demo/events.csv')
    chosen=str(source['match_id'].astype(str).iloc[0])
    path=tmp_path/'events.csv'; source.to_csv(path,index=False)
    result=run(path,focal_team='Team A',match_ids=[chosen])
    assert result['events'].match_id.nunique()==1
    assert result['input_metadata']['selected_match_ids']==[chosen]
    assert result['shot_freeze_frames'].empty
    assert result['frames360_loaded']==0
