"""
test_csv_events.py
--------------------
Tests del loader de eventos en formato CSV (ingestion.csv_events),
verificando que produce el mismo tipo de dict que el loader StatsBomb
y que se integra sin cambios con normalization.events.normalize_events.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.csv_events import load_csv_events, load_csv_pip_one
from normalization.events import normalize_events
from ingestion.pip_one import merge_pip_one_with_events


@pytest.fixture()
def tmp_csv_events(tmp_path):
    content = (
        "match_id,event_id,index,possession,team,player,minute,second,event_type,x,y,shot_outcome\n"
        "M1,e1,1,1,Team A,Player 1,0,2.0,Pass,45.0,40.0,\n"
        "M1,e2,2,1,Team A,Player 2,0,4.5,Shot,110.0,40.0,Goal\n"
        "M1,e3,3,1,,Player 3,0,6.0,Carry,50.0,40.0,\n"  # sin team -> se descarta
    )
    path = tmp_path / "events.csv"
    path.write_text(content)
    return path


def test_load_csv_events_drops_missing_team(tmp_csv_events):
    parsed = load_csv_events(tmp_csv_events)
    assert len(parsed) == 2
    assert all(ev["team"] for ev in parsed)


def test_load_csv_events_missing_file():
    with pytest.raises(FileNotFoundError):
        load_csv_events("no_existe.csv")


def test_load_csv_events_missing_required_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("foo,bar\n1,2\n")
    with pytest.raises(ValueError):
        load_csv_events(path)


def test_load_csv_events_alias_columns(tmp_path):
    """Columnas con nombres alternativos (type, loc_x, loc_y) deben mapearse."""
    content = "match,team_name,player_name,type,loc_x,loc_y,minute,second\nM1,Team A,P1,Pass,10,20,0,1.0\n"
    path = tmp_path / "aliased.csv"
    path.write_text(content)
    parsed = load_csv_events(path)
    assert len(parsed) == 1
    assert parsed[0]["team"] == "Team A"
    assert parsed[0]["event_type"] == "Pass"
    assert parsed[0]["location"] == [10.0, 20.0]


def test_csv_events_feed_into_normalize_events(tmp_csv_events):
    parsed = load_csv_events(tmp_csv_events)
    df = normalize_events(parsed)
    assert not df.empty
    assert set(["match_id", "team", "event_type", "location_x", "location_y"]).issubset(df.columns)
    assert df.loc[df["event_type"] == "Shot", "shot_outcome"].iloc[0] == "Goal"


def test_load_csv_pip_one_and_merge(tmp_path, tmp_csv_events):
    pip_content = (
        "match_id,timestamp,team,player,event_type,zone,target_player,context,confidence,analyst_id\n"
        "M1,2.5,Team A,Player 1,safety_pass,defensive_third,Player 2,build_up,0.9,A1\n"
    )
    pip_path = tmp_path / "pip_one.csv"
    pip_path.write_text(pip_content)

    events_df = normalize_events(load_csv_events(tmp_csv_events))
    pip_df = load_csv_pip_one(pip_path)
    merged = merge_pip_one_with_events(events_df, pip_df)

    row = merged[(merged["team"] == "Team A") & (merged["player"] == "Player 1")]
    assert row.iloc[0]["pip_event_type"] == "safety_pass"
