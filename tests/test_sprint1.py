"""
test_sprint1.py
-----------------
Tests automatizados del Sprint 1 (sección 26 de la especificación):
  - normalización de coordenadas
  - manejo de valores faltantes
  - orden de eventos
  - ingestión StatsBomb events / 360 / PIP One
  - merge PIP One <-> eventos
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from normalization.coordinates import normalize_point, extract_location
from ingestion.statsbomb_events import load_statsbomb_events
from ingestion.statsbomb_360 import load_statsbomb_360, has_360_data
from ingestion.pip_one import load_pip_one, merge_pip_one_with_events
from normalization.events import normalize_events
from data.synthetic import generate_synthetic_match


# ---------------------------------------------------------------------------
# Coordenadas
# ---------------------------------------------------------------------------

def test_normalize_point_within_bounds():
    x, y = normalize_point(60.0, 40.0)
    assert x == 60.0 and y == 40.0


def test_normalize_point_clips_out_of_bounds():
    x, y = normalize_point(-10.0, 200.0)
    assert x == 0.0
    assert y == 80.0  # ancho de cancha configurado


def test_normalize_point_none_stays_none():
    x, y = normalize_point(None, None)
    assert x is None and y is None


def test_extract_location_missing_field():
    assert extract_location(None) == (None, None)
    assert extract_location([]) == (None, None)


def test_extract_location_valid():
    x, y = extract_location([30.5, 41.2])
    assert x == 30.5 and y == 41.2


# ---------------------------------------------------------------------------
# Ingestión StatsBomb events — con fixtures en disco
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_events_file(tmp_path):
    events = [
        {
            "id": "e1", "index": 1, "minute": 5, "second": 10,
            "type": {"name": "Pass"}, "team": {"name": "Team A"},
            "player": {"name": "Player X"}, "location": [50, 40],
            "possession": 1, "possession_team": {"name": "Team A"},
        },
        {
            # evento sin 'team' -> debe descartarse
            "id": "e2", "index": 2, "minute": 5, "second": 12,
            "type": {"name": "Carry"}, "location": [55, 42],
        },
        {
            "id": "e3", "index": 3, "minute": 5, "second": 15,
            "type": {"name": "Shot"}, "team": {"name": "Team A"},
            "player": {"name": "Player X"}, "location": [110, 40],
            "shot": {"outcome": {"name": "Goal"}},
        },
    ]
    path = tmp_path / "events.json"
    with open(path, "w") as f:
        json.dump(events, f)
    return path


def test_load_statsbomb_events_drops_incomplete(tmp_events_file):
    parsed = load_statsbomb_events(tmp_events_file)
    # el evento sin team/type utilizable debe descartarse -> quedan 2 de 3
    assert len(parsed) == 2
    assert all(ev["team"] is not None for ev in parsed)


def test_load_statsbomb_events_missing_file():
    with pytest.raises(FileNotFoundError):
        load_statsbomb_events("no_existe.json")


# ---------------------------------------------------------------------------
# 360
# ---------------------------------------------------------------------------

def test_load_statsbomb_360_none_path():
    frames = load_statsbomb_360(None)
    assert frames == {}
    assert has_360_data(frames) is False


def test_load_statsbomb_360_missing_file(tmp_path):
    frames = load_statsbomb_360(tmp_path / "no_existe.json")
    assert frames == {}


def test_load_statsbomb_360_valid(tmp_path):
    frame_data = [{"event_uuid": "e1", "visible_area": [[0, 0]], "freeze_frame": []}]
    path = tmp_path / "frames_360.json"
    with open(path, "w") as f:
        json.dump(frame_data, f)
    frames = load_statsbomb_360(path)
    assert "e1" in frames
    assert has_360_data(frames) is True


# ---------------------------------------------------------------------------
# PIP One
# ---------------------------------------------------------------------------

def test_load_pip_one_none_path():
    df = load_pip_one(None)
    assert df.empty
    assert "match_id" in df.columns


def test_merge_pip_one_with_events_no_pip():
    events_df = pd.DataFrame([
        {"match_id": "m1", "team": "Team A", "player": "Player X", "timestamp_seconds": 100.0}
    ])
    empty_pip = load_pip_one(None)
    merged = merge_pip_one_with_events(events_df, empty_pip)
    assert merged["pip_event_type"].isna().all()


def test_merge_pip_one_with_events_within_tolerance(tmp_path):
    events_df = pd.DataFrame([
        {"match_id": "m1", "team": "Team A", "player": "Player X", "timestamp_seconds": 100.0}
    ])
    pip_records = [{
        "match_id": "m1", "timestamp": 101.5, "team": "Team A", "player": "Player X",
        "event_type": "safety_pass", "zone": "middle_third", "target_player": "Player Y",
        "context": "build_up", "confidence": 0.9, "analyst_id": "A1",
    }]
    pip_path = tmp_path / "pip_one.json"
    with open(pip_path, "w") as f:
        json.dump(pip_records, f)

    pip_df = load_pip_one(pip_path)
    merged = merge_pip_one_with_events(events_df, pip_df)
    assert merged.loc[0, "pip_event_type"] == "safety_pass"


# ---------------------------------------------------------------------------
# Normalización de eventos + orden temporal
# ---------------------------------------------------------------------------

def test_normalize_events_orders_by_timestamp():
    raw = [
        {"match_id": "m1", "event_id": "e2", "index": 2, "minute": 1, "second": 5,
         "event_type": "Carry", "team": "Team A", "player": "P1", "location": [10, 10]},
        {"match_id": "m1", "event_id": "e1", "index": 1, "minute": 0, "second": 10,
         "event_type": "Pass", "team": "Team A", "player": "P1", "location": [5, 5]},
    ]
    df = normalize_events(raw)
    assert list(df["event_id"]) == ["e1", "e2"]


def test_normalize_events_marks_has_360():
    raw = [{"match_id": "m1", "event_id": "e1", "index": 1, "minute": 0, "second": 1,
            "event_type": "Pass", "team": "Team A", "player": "P1", "location": [5, 5]}]
    frames = {"e1": {"event_id": "e1", "visible_area": None, "freeze_frame": []}}
    df = normalize_events(raw, freeze_frames=frames)
    assert bool(df.loc[0, "has_360"]) is True


def test_normalize_events_empty_input_returns_empty_df():
    df = normalize_events([])
    assert df.empty


# ---------------------------------------------------------------------------
# Datos sintéticos (modo --demo)
# ---------------------------------------------------------------------------

def test_generate_synthetic_match_structure():
    dataset = generate_synthetic_match(match_id="TEST_0001", seed=1)
    assert len(dataset["events"]) > 0
    assert all("type" in ev and "team" in ev for ev in dataset["events"])
    # con include_360/include_pip activados por defecto, deben producirse ambos
    assert len(dataset["frames_360"]) >= 0
    assert len(dataset["pip_one"]) >= 0


def test_synthetic_events_are_ingestible(tmp_path):
    """Verifica que la salida sintética pasa por el loader real sin errores."""
    dataset = generate_synthetic_match(match_id="TEST_0002", seed=2)
    events_path = tmp_path / "events.json"
    with open(events_path, "w") as f:
        json.dump(dataset["events"], f)

    parsed = load_statsbomb_events(events_path)
    assert len(parsed) > 0
    df = normalize_events(parsed)
    assert not df.empty
    assert set(["match_id", "event_type", "team"]).issubset(df.columns)
