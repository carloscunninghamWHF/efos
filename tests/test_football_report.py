"""Informe para cuerpo técnico: genérico, sin siglas en el texto principal y con PDF válido."""
from coach_story.coach_fit import coach_fit, style_by_match, style_profile
from coach_story.coach_profile import build_coach_profile, _starters
from coach_story.football_pdf import build_football_pdf
from coach_story.football_report import build_football_report, render_football_report_md
from config_loader import get_coach_archetypes
from tests.test_coach_profile import _events

DIMS = {"OC": 60.0, "HPS": 70.0, "RPS": 90.0, "DS": 80.0, "DER": 65.0}


def _report(team):
    ev = _events(team)
    st = style_profile(style_by_match(ev, team)); fit = coach_fit(st, get_coach_archetypes())
    cp = build_coach_profile(ev, team, st, fit, 0.4)
    return build_football_report(ev, team, cp, fit, DIMS, 72.0, None, None, 0.4, _starters(ev, team))


def test_sections_follow_moments_of_the_game():
    md = render_football_report_md(_report("Team A"))
    order = ["## Ficha", "## 1. El entrenador", "## 2. Ataque organizado", "## 3. Transición defensiva",
             "## 4. Defensa organizada", "## 5. Transición ofensiva", "## 6. Balón parado", "## 9. Conclusiones"]
    pos = [md.index(h) for h in order]
    assert pos == sorted(pos)


def test_main_text_avoids_technical_acronyms():
    md = render_football_report_md(_report("Team A"))
    body = md.split("## Glosario")[0]
    for acronym in ("ESI", "HPS", "RPS", "DER", "PCI", "DTC", "LAP", "CTS", "OBV"):
        assert f" {acronym} " not in body and f"({acronym})" not in body


def test_team_name_invariance_and_pdf():
    a, b = _report("Team A"), _report("Manchester City")
    assert a["ficha"] == b["ficha"]
    assert [x["titulo"] for x in a["fortalezas"]] == [x["titulo"] for x in b["fortalezas"]]
    pdf = build_football_pdf(b)
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000
