"""Explorador de acciones: filtros, ventanas de transición, balón parado y alineaciones."""
import numpy as np
import pandas as pd

import visualization.action_explorer as X
from coach_story.coach_profile import _formation


def _row(**k):
    base = {"match_id": 1, "team": "A", "period": 1, "minute": 0, "second": 0, "timestamp_seconds": 0.0, "possession": 1,
            "event_type": "Pass", "type_name": np.nan, "location_x": 50.0, "location_y": 40.0, "end_location_x": 60.0,
            "end_location_y": 40.0, "pass_outcome": np.nan, "outcome_name": np.nan, "player": "P1", "statsbomb_xg": np.nan,
            "obv_total_net": 0.01, "shot_outcome": np.nan, "pass_recipient_name": np.nan, "technique_name": np.nan,
            "play_pattern_name": "Regular Play", "counterpress": False}
    base.update(k); return base


def _events(team="A"):
    rows = [
        _row(team=team, timestamp_seconds=10, possession=2, event_type="Ball Recovery", location_x=70),
        _row(team=team, timestamp_seconds=14, possession=2, event_type="Pass", location_x=72, end_location_x=105, end_location_y=40),
        _row(team=team, timestamp_seconds=20, possession=2, event_type="Shot", location_x=108, statsbomb_xg=0.3, shot_outcome="Goal"),
        _row(team=team, timestamp_seconds=40, possession=3, event_type="Dispossessed", location_x=30),
        _row(team=team, timestamp_seconds=42, possession=4, event_type="Pressure", location_x=35, counterpress=True),
        _row(team="B", timestamp_seconds=45, possession=4, event_type="Shot", location_x=100, statsbomb_xg=0.1, player="R1"),
        _row(team=team, timestamp_seconds=60, possession=5, event_type="Pass", type_name="Corner", location_x=120, location_y=0,
             end_location_x=112, end_location_y=38, player="Taker"),
        _row(team=team, timestamp_seconds=63, possession=5, event_type="Shot", location_x=112, location_y=38, statsbomb_xg=0.2, player="Header"),
        _row(team=team, timestamp_seconds=80, possession=6, event_type="Pass", type_name="Free Kick", location_x=90, location_y=10, player="Taker"),
        _row(team=team, timestamp_seconds=90, possession=7, event_type="Pass", type_name="Free Kick", location_x=70, location_y=40, player="Taker"),
        _row(team=team, timestamp_seconds=95, possession=8, event_type="Shot", type_name="Penalty", location_x=108, statsbomb_xg=0.78, player="P9"),
        _row(team=team, timestamp_seconds=99, possession=9, event_type="Shot", type_name="Free Kick", location_x=95, statsbomb_xg=0.05, player="P9"),
    ]
    return X.prepare(pd.DataFrame(rows))


def test_transition_windows():
    e = _events(); tf = X.transition_frames(e, "A")
    assert set(tf["off"]["event_type"]) >= {"Pass", "Shot"}          # 4 s y 10 s tras recuperar, misma posesión
    assert tf["def_win"]["event_type"].tolist() == ["Pressure"]       # contrapresión 2 s tras perder
    assert len(tf["opp_shots_after_loss"]) == 1                         # tiro rival 5 s tras la pérdida
    acts = X.transition_actions(e, "A", tf)
    assert len(acts["Recuperaciones que acaban en tiro"][1]) == 1


def test_set_piece_classification_and_shooter():
    sp = X.set_piece_table(_events(), "A")
    kinds = dict(zip(sp["tipo"], sp["ejecutor"]))
    assert set(sp["tipo"]) == {"Tiro de esquina", "Tiro libre lateral", "Tiro libre lejano", "Penalti", "Tiro libre directo"}
    corner = sp[sp["tipo"].eq("Tiro de esquina")].iloc[0]
    assert corner["ejecutor"] == "Taker" and corner["rematador"] == "Header" and abs(corner["xg"] - 0.2) < 1e-9
    assert kinds["Penalti"] == "P9"


def test_scope_and_value_are_team_name_invariant():
    a, b = _events("A"), _events("Manchester City")
    va = X.value_by_match(a[a.team.eq("A")], a[a.team.eq("A") & a.event_type.eq("Shot")], {1: "J01"})
    vb = X.value_by_match(b[b.team.eq("Manchester City")], b[b.team.eq("Manchester City") & b.event_type.eq("Shot")], {1: "J01"})
    assert np.allclose(va[["OBV", "xG"]].values, vb[["OBV", "xG"]].values)
    only = X.apply_scope(a, [1], "Taker")
    assert set(only["player"]) == {"Taker"}


def test_lineups_by_formation():
    xi = ["Goalkeeper", "Right Back", "Right Center Back", "Left Center Back", "Left Back", "Right Defensive Midfield",
          "Left Defensive Midfield", "Right Wing", "Center Attacking Midfield", "Left Wing", "Center Forward"]
    starters = {m: {f"J{i}": p for i, p in enumerate(xi)} for m in range(3)}
    lu = X.lineups_by_formation(starters, _formation)
    assert list(lu) == ["4-2-3-1"] and lu["4-2-3-1"]["partidos"] == 3 and len(lu["4-2-3-1"]["slots"]) == 11
    fig = X.lineup_pitch("4-2-3-1", lu["4-2-3-1"], "A")
    assert fig is not None


def test_key_moments_cover_phases_and_goals():
    e = _events()
    km = X.key_moments(e, "A", 1)
    phases = set(km["fase"].astype(str))
    assert {"Transiciones", "Balón parado"} <= phases
    goal = km[km["gol"]]
    assert len(goal) == 1 and goal.iloc[0]["fase"] == "Transiciones" and goal.iloc[0]["lado"] == "A favor"
    assert (km[~km["gol"]].groupby(["fase", "lado"], observed=True).size() <= 3).all()
    assert X.match_score(e, "A", 1) == (1, 0)
