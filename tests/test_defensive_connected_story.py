"""Connected defensive workflow: keep contextual filters and drilldowns usable."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tests.open_play_demo_synthetic import make_demo
from intelligence.defensive_open_play import analyze, STATES
from visualization.defensive_open_play_app import comparison_table


def test_missing_scenario_is_not_displayed_as_zero_risk():
    summary, _ = analyze(make_demo())
    table = comparison_table(summary[summary.scenario.eq(STATES[0])])
    assert table.loc[table.Posesiones.eq(0), 'Con remate (%)'].isna().all()


def test_connected_filters_and_empty_context():
    root = str(Path(__file__).resolve().parents[1])
    code = f"""
import sys
sys.path.insert(0, {root!r})
from tests.open_play_demo_synthetic import make_demo
from visualization.defensive_open_play_app import render_defensive_module
render_defensive_module(make_demo(), 'América')
"""
    app = AppTest.from_string(code).run(timeout=30)
    assert not app.exception
    assert len(app.tabs) == 3
    app.selectbox(key='open_play_time').set_value('16–30').run()
    app.selectbox(key='open_play_drill_match').set_value('DEMO-02').run()
    app.selectbox(key='open_play_time_metric').set_value('xG rival por posesión cubierta').run()
    assert not app.exception
    possession = app.selectbox(key='open_play_possession').value
    assert possession.startswith('DEMO-02:')
    app.selectbox(key='open_play_score').set_value('Pierde').run()
    assert not app.exception
