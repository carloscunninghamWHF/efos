"""Perfil del entrenador: funciona con cualquier equipo y no inventa secciones sin datos."""
import numpy as np
import pandas as pd

from coach_story.coach_fit import coach_fit, style_by_match, style_profile
from coach_story.coach_profile import _formation, build_coach_profile, render_coach_profile_md
from config_loader import get_coach_archetypes

XI_4231 = ["Goalkeeper", "Right Back", "Right Center Back", "Left Center Back", "Left Back",
           "Right Defensive Midfield", "Left Defensive Midfield", "Right Wing", "Center Attacking Midfield",
           "Left Wing", "Center Forward"]


def _events(team="Team A", n_matches=6, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for m in range(n_matches):
        for side, tm in ((0, team), (1, f"Rival {m}")):
            for i, pos in enumerate(XI_4231):
                for k in range(8):
                    state = ["drawing", "winning", "losing"][k % 3] if side == 0 else ["drawing", "losing", "winning"][k % 3]
                    rows.append({"match_id": m, "team": tm, "event_type": "Pass" if k % 2 else "Pressure",
                                 "period": 1 if k < 4 else 2, "minute": 5 + k * 10, "player": f"{tm}-{i}",
                                 "player_position_name": pos, "location_x": rng.uniform(0, 120),
                                 "pass_length": rng.uniform(5, 50), "counterpress": k == 2, "statsbomb_xg": np.nan,
                                 "score_state": state})
            rows.append({"match_id": m, "team": tm, "event_type": "Substitution", "period": 2, "minute": 60 + m,
                         "player": f"{tm}-9", "player_position_name": "Center Forward", "location_x": np.nan,
                         "pass_length": np.nan, "counterpress": False, "statsbomb_xg": np.nan, "score_state": "drawing"})
    return pd.DataFrame(rows)


def _profile(ev, team):
    st = style_profile(style_by_match(ev, team))
    return build_coach_profile(ev, team, st, coach_fit(st, get_coach_archetypes()), 0.4)


def test_formation_reconstruction():
    assert _formation(XI_4231)[0] == "4-2-3-1"
    xi_433 = ["Goalkeeper", "Right Back", "Right Center Back", "Left Center Back", "Left Back",
              "Center Defensive Midfield", "Right Center Midfield", "Left Center Midfield",
              "Right Wing", "Center Forward", "Left Wing"]
    assert _formation(xi_433)[0] == "4-3-3"


def test_profile_sections_and_markdown():
    cp = _profile(_events(), "Team A")
    assert cp["estructura"]["dibujo_principal"] == "4-2-3-1"
    assert cp["gestion"]["cambios_por_partido"] == 1
    md = render_coach_profile_md(cp)
    for h in ("## Retrato", "## 1. Estructura", "## 3. Cómo reacciona", "## 4. Gestión"):
        assert h in md


def test_team_name_invariance():
    a = _profile(_events("Team A"), "Team A")
    b = _profile(_events("Manchester City"), "Manchester City")
    assert a["estructura"] == b["estructura"]
    assert a["perfil_tipo"] == b["perfil_tipo"]
    assert a["gestion"]["primer_cambio_mediana"] == b["gestion"]["primer_cambio_mediana"]


def test_missing_columns_are_skipped_not_invented():
    ev = _events().drop(columns=["player_position_name", "score_state"])
    cp = _profile(ev, "Team A")
    assert cp["estructura"] == {}
    assert cp["por_marcador"] == []
    assert cp["textos"]["retrato"]
