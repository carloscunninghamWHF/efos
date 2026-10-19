"""v0.4.26 — CTS radar and score reaction filtered by formation / rival / match."""
import pandas as pd
import pytest

from visualization.coach_formation_ui import (RADAR_KEYS, cts_for_matches, formation_matches,
                                              score_reaction_for_matches, fig_radar_compare, fig_score_compare)


@pytest.fixture(scope='module')
def result():
    from run_sprint4 import run
    return run('data/raw/csv_demo/events.csv', 'Team A')


def test_all_matches_reproduce_season_signature(result):
    ids = result['events'].loc[result['events']['team'].eq('Team A'), 'match_id'].astype(str).unique()
    cts = cts_for_matches(result, ids)
    for k in RADAR_KEYS:
        season = result['cts'].get(k)
        if season is None:
            assert cts[k] is None
        else:
            assert cts[k] == pytest.approx(season)


def test_all_matches_reproduce_season_score_reaction(result):
    rows = result['coach_identity'].get('por_marcador') or []
    if not rows:
        pytest.skip('demo sample has no score segmentation')
    ids = result['events']['match_id'].astype(str).unique()
    sel = score_reaction_for_matches(result, ids).set_index('segmento')
    season = pd.DataFrame(rows).set_index('segmento')
    for seg in season.index:
        for col in ['posesion', 'presion_alta', 'pase_largo', 'altura_bloque']:
            a, b = season.loc[seg, col], sel.loc[seg, col]
            assert (pd.isna(a) and pd.isna(b)) or a == pytest.approx(b)


def test_formation_table_and_figures_build(result):
    fm = formation_matches(result)
    assert {'match_id', 'dibujo', 'rival', 'marcador', 'resultado', 'etiqueta'} <= set(fm.columns)
    one = fm['match_id'].iloc[0]
    sel = cts_for_matches(result, [one])
    fig = fig_radar_compare(result['cts'], sel, 'Team A', 'partido')
    assert len(fig.data) == 2
    # Missing dimensions are never drawn as numbers.
    from visualization.efos_figures import CTS_LABELS
    drawn = {str(t).replace(' (sin dato)', '') for t in fig.data[1].theta}
    for k in RADAR_KEYS:
        if sel.get(k) is None:
            assert CTS_LABELS[k] not in drawn
        else:
            assert CTS_LABELS[k] in drawn
    score = score_reaction_for_matches(result, [one])
    fig2 = fig_score_compare(result['coach_identity'].get('por_marcador') or [], score, 'Team A', 'P01', ['drawing'])
    assert len(fig2.data) >= 4


def test_season_readings_are_generated_from_data(result):
    from visualization.coach_season_reading import radar_season_reading, score_season_reading
    r = radar_season_reading(result)
    if r is not None:
        assert r['identity'] and r['lines'] and r['caveat']
        assert all('**' in line for line in r['lines'])
    s = score_season_reading(result, result['coach_identity'].get('por_marcador') or [])
    if s is not None:
        assert len(s['changes']) == 4
        assert 'no demuestra' in s['caveat']


def test_phase_profile_counts_match_raw_events(result):
    from visualization.phase_profile import phase_profile, METRICS, classify
    ev = result['events']; team = 'Team A'
    ids = ev.loc[ev['team'].eq(team), 'match_id'].astype(str).unique()
    p = phase_profile(result, ids)
    own = ev[ev['team'].eq(team)]; n = own['match_id'].nunique()
    assert p['n_matches'] == n
    assert p['team']['shots'] == pytest.approx((own['event_type'] == 'Shot').sum() / n)
    assert p['team']['passes'] == pytest.approx((own['event_type'] == 'Pass').sum() / n)
    # Symmetry: what the team concedes is what its rivals produce.
    assert p['team']['shots_against'] == pytest.approx(p['rivals']['shots'])
    assert p['team']['possession'] + p['rivals']['possession'] == pytest.approx(100.0)
    assert {m[0] for m in METRICS} == set(p['team'])
    assert classify('goals_against', 1.0, 2.0) == 'up' and classify('goals', 1.0, 2.0) == 'down'
    assert classify('pass_len', 10.0, 30.0) == 'mid'


def test_phase_reading_builds_for_season_and_filters(result):
    from visualization.phase_profile import phase_profile, phase_reading, ALL_SHAPES, ALL_RIVALS
    from visualization.coach_formation_ui import formation_matches
    fm = formation_matches(result)
    p = phase_profile(result, fm['match_id'])
    r = phase_reading(result, p, fm, ALL_SHAPES, ALL_RIVALS, None)
    assert r['title'] and r['happened'] and r['decide']
    one = fm.head(1)
    r1 = phase_reading(result, phase_profile(result, one['match_id']), one, ALL_SHAPES, one['rival'].iloc[0], None)
    assert one['rival'].iloc[0] in r1['title'] and 'patrón' in r1['note']
    for state in ('losing', 'drawing', 'winning'):
        ps = phase_profile(result, fm['match_id'], state)
        if ps['n_matches']:
            rs = phase_reading(result, ps, fm, ALL_SHAPES, ALL_RIVALS, state)
            assert not any(line.startswith('**Goles:**') for line in rs['happened'])
