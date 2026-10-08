"""Perfil de entrenador: invariantes básicos del motor de encaje."""
import numpy as np
import pandas as pd

from coach_story.coach_fit import STYLE_AXES, build_story, coach_fit, style_by_match, style_profile
from config_loader import get_coach_archetypes


def _events(team_a="Team A", team_b_prefix="Rival", n_matches=6, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for m in range(n_matches):
        for tm, n_pass, n_press in ((team_a, 60, 20), (f"{team_b_prefix} {m}", 40, 20)):
            for _ in range(n_pass):
                rows.append({"match_id": m, "team": tm, "event_type": "Pass", "location_x": rng.uniform(0, 120),
                             "pass_length": rng.uniform(5, 50), "counterpress": False, "statsbomb_xg": np.nan})
            for i in range(n_press):
                rows.append({"match_id": m, "team": tm, "event_type": "Pressure", "location_x": rng.uniform(0, 120),
                             "pass_length": np.nan, "counterpress": i % 4 == 0, "statsbomb_xg": np.nan})
            for _ in range(5):
                rows.append({"match_id": m, "team": tm, "event_type": "Shot", "location_x": 105.0,
                             "pass_length": np.nan, "counterpress": False, "statsbomb_xg": rng.uniform(0.02, 0.3)})
    return pd.DataFrame(rows)


def test_profile_has_all_axes_and_bounded_index():
    prof = style_profile(style_by_match(_events(), "Team A"))
    assert set(STYLE_AXES) <= set(prof["eje"])
    assert prof["indice"].between(0, 100).all()
    # Team A hace 60 de cada 100 pases en cada partido
    assert abs(prof.set_index("eje").loc["posesion", "equipo"] - 60) < 1e-9


def test_fit_is_sorted_and_covers_all_archetypes():
    arch = get_coach_archetypes()
    fit = coach_fit(style_profile(style_by_match(_events(), "Team A")), arch)
    assert len(fit) == len(arch["arquetipos"])
    assert fit["encaje"].is_monotonic_decreasing
    assert fit["encaje"].between(0, 100).all()


def test_team_name_does_not_change_results():
    arch = get_coach_archetypes()
    a = coach_fit(style_profile(style_by_match(_events("Team A"), "Team A")), arch)
    b = coach_fit(style_profile(style_by_match(_events("Manchester City"), "Manchester City")), arch)
    assert np.allclose(a["encaje"].values, b["encaje"].values)
    assert list(a["clave"]) == list(b["clave"])


def test_story_texts_present():
    arch = get_coach_archetypes()
    prof = style_profile(style_by_match(_events(), "Team A"))
    story = build_story("Team A", prof, coach_fit(prof, arch), 6, arch["margen_empate"])
    for k in ("identidad", "entrenador", "cambio", "necesidad"):
        assert story[k] and "Team A" in story["identidad"]
