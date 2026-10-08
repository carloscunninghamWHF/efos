"""Tests del adaptador del CSV ancho de StatsBomb y de las correcciones v0.3.1."""
import pandas as pd
import pytest
from ingestion.statsbomb_wide_csv import load_statsbomb_wide
from context.game_context import add_score_state
from objects.transitions import detect_transitions


def wide_csv(tmp_path):
    rows = [
        # id, index, period, minute, second, type, team, poss_team, outcome
        ("a", 1, 1, 0, 1.0, "Pass", "A", "A", None),
        ("a", 1, 1, 0, 1.0, "Pass", "A", "A", None),          # fila repetida (freeze frame)
        ("b", 2, 1, 46, 30.0, "Shot", "A", "A", "Goal"),       # añadido del 1T
        ("c", 3, 2, 45, 5.0, "Pass", "B", "B", None),          # arranque 2T
        ("d", 4, 2, 60, 0.0, "Own Goal For", "B", "B", None),
    ]
    df = pd.DataFrame(rows, columns=["id", "index", "period", "minute", "second", "event_type_name",
                                     "team_name", "possession_team_name", "outcome_name"])
    df["match_id"] = 1; df["location_x"] = 50.0; df["location_y"] = 40.0
    p = tmp_path / "wide.csv"; df.to_csv(p, index=False)
    return p


def test_dedup_rename_and_monotonic_time(tmp_path):
    ev = load_statsbomb_wide([wide_csv(tmp_path)])
    assert len(ev) == 4 and {"event_type", "team", "possession_team", "event_id"} <= set(ev.columns)
    ts = ev.sort_values("index").timestamp_seconds.tolist()
    assert ts == sorted(ts)                     # el 2T va después del añadido del 1T
    assert ev.loc[ev.event_id == "b", "shot_outcome"].iloc[0] == "Goal"


def test_own_goal_counts_for_benefiting_team(tmp_path):
    ev = add_score_state(load_statsbomb_wide([wide_csv(tmp_path)]), "A")
    last = ev.sort_values("timestamp_seconds").iloc[-1]
    assert (last.focal_goals, last.opponent_goals, last.score_state) == (1, 1, "drawing")


def test_no_transition_at_period_change(tmp_path):
    ev = add_score_state(load_statsbomb_wide([wide_csv(tmp_path)]), "A")
    tr = detect_transitions(ev)
    assert tr.empty and "score_state" not in tr or len(tr) == 0


def test_unknown_team_fails_loudly(tmp_path):
    from run_sprint2 import run
    ev = load_statsbomb_wide([wide_csv(tmp_path)]); p = tmp_path / "n.csv"; ev.to_csv(p, index=False)
    with pytest.raises(ValueError, match="no aparece"):
        run(p, "Club América")
