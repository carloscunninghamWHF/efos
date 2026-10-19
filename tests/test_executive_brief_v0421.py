"""Executive-first presentation must stay sourced, consistent, and portable."""
import pandas as pd

from coach_story.executive_brief import build_executive_brief
from coach_story.executive_pdf import build_executive_pdf
from visualization.efos_smart_attack_graphs import figure_executive_lane_origins, figure_pass_network


def _sample():
    # Right is the largest lane but not a majority. Different denominators
    # cannot be added as if they were the same population.
    possessions = pd.DataFrame({'lane': ['Derecha'] * 4 + ['Centro'] * 3 + ['Izquierda'] * 2 +
                                ['Sin coordenadas'], 'match_id': ['m1'] * 10})
    defense = pd.DataFrame({'scenario': ['Defensa ante contraataque', 'Otro juego abierto'],
                            'shot': [True, False], 'match_id': ['m1', 'm1']})
    transitions = pd.DataFrame({'team_lost': ['B', 'B', 'Rival'],
                                'response_within_5s': [True, False, True],
                                'match_id': ['m1', 'm1', 'm1']})
    return {
        'focal_team': 'B',
        'organized_attack_data': (pd.DataFrame(), possessions),
        'offensive_story': {
            'status': 'SMALL_SAMPLE', 'n_possessions': 10, 'n_matches': 1,
            'entry': {'lane': 'Derecha', 'count': 4, 'denominator': 9, 'share': 4/9},
            'productivity': {'shots': 2},
        },
        'defensive_open_play_possessions': defense,
        'transitions': transitions,
        'football_report': {'equipo': 'B', 'ficha': {'partidos': 1},
                            'como_jugarle': ['Presionarle sin pensar en la muestra.']},
    }


def test_brief_displays_valid_denominators_without_majority_claim():
    b = build_executive_brief(_sample())
    assert b['schema'] == 'EFOS_EXECUTIVE_BRIEF_0421'
    assert [x['value'] for x in b['signals']] == ['44%', '100.0%', '50.0%']
    assert b['signals'][0]['caption'].startswith('4 de 9')
    assert 'más frecuente' in b['signals'][0]['insight']
    assert 'predomina' not in b['signals'][0]['insight']
    assert b['signals'][0]['status'] == 'SMALL_SAMPLE'
    assert 'recuperaciones reales' in b['story']
    assert b['main_visual'] == 'lane_origins'
    assert 'Presionarle' not in str(b)


def test_empty_result_does_not_invent_football_identity():
    b = build_executive_brief({'focal_team': 'Club sin datos'})
    assert b['coverage'] == 0
    assert b['main_visual'] == 'none'
    assert all(s['value'] == '—' and s['status'] == 'INSUFFICIENT' for s in b['signals'])
    assert 'no ofrece cobertura' in b['story']


def test_pitch_represents_exact_counts_no_invented_routes():
    df = _sample()['organized_attack_data'][1]
    fig = figure_executive_lane_origins(df)
    chart = fig.to_json()
    assert '4 de 9' in chart and '3 de 9' in chart and '2 de 9' in chart
    assert len(fig.data) == 0  # No fake player dots, routes or extrapolated tracking.
    assert fig.layout.height == 400


def test_pdf_uses_new_brief_and_remains_one_page(tmp_path):
    result = _sample()
    result['events'] = pd.DataFrame([{'team': 'B', 'match_id': 'm1'}])
    doc = tmp_path / 'ejecutivo.pdf'
    data = build_executive_pdf(result, {'coach': 'DT B', 'league': 'Liga', 'period': 'Temporada'}, doc)
    assert data.startswith(b'%PDF')
    assert b'/Count 1' in data
    assert doc.read_bytes() == data
    # Same rendering contract with no inputs: no output fabricated.
    empty = build_executive_pdf({'focal_team': 'Sin datos'})
    assert empty.startswith(b'%PDF') and b'/Count 1' in empty


def test_pass_network_default_is_unchanged_and_horizontal_variant_available():
    d = pd.DataFrame(columns=['_type','location_x','location_y','end_location_x','end_location_y',
                              '_pass_done','pass_recipient_name','player'])
    old = figure_pass_network(d)
    compact = figure_pass_network(d, vertical=False, height=460)
    assert old.layout.height == 690
    assert compact.layout.height == 460
