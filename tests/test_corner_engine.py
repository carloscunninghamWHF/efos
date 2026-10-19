"""Tests puros del motor de córners; ejecutar `pytest -q tests/test_corner_engine.py`."""
import math
import numpy as np
import pandas as pd

from intelligence.corner_engine import analyze_corners, build_corner_sequences, CornerConfig


def event(**kw):
    x = dict(match_id='m1', period=1, possession=7, event_type='Pass',
             team='América', type_name=None, timestamp_seconds=0, index=0,
             location_x=110, location_y=0, end_location_x=112, end_location_y=34,
             statsbomb_xg=np.nan, shot_outcome=None, pass_outcome=None,
             player='J1', event_id=None, minute=10,
             pass_recipient_name=None, score_state='drawing')
    x.update(kw)
    return x


def dataset():
    return pd.DataFrame([
        event(index=1, event_id='C1', timestamp_seconds=600, type_name='Corner', player='E1', pass_recipient_name='Receptor-previsto'),
        event(index=2, event_id='R1', timestamp_seconds=601, event_type='Ball Receipt*', player='Atacante1'),
        event(index=3, event_id='S1', timestamp_seconds=604, event_type='Shot', player='Atacante2', statsbomb_xg=0.12),
        event(index=4, event_id='S2', timestamp_seconds=607, event_type='Shot', player='Atacante3', statsbomb_xg=0.08, shot_outcome='Goal'),
        event(index=5, event_id='S3', timestamp_seconds=609, event_type='Shot', team='Rival', player='Rival1', statsbomb_xg=0.42),
        event(index=6, event_id='X1', timestamp_seconds=610, event_type='Shot', possession=8, player='Atacante4', statsbomb_xg=0.4),
        event(index=7, event_id='X2', timestamp_seconds=605, event_type='Shot', match_id='m2', player='Atacante5', statsbomb_xg=0.5),
        event(index=8, event_id='X3', timestamp_seconds=608, event_type='Shot', period=2, player='Atacante6', statsbomb_xg=0.6),
        event(index=9, event_id='C2', timestamp_seconds=650, type_name='Corner', team='Rival', possession=9,
              location_y=80, end_location_y=39, player='E2'),
        event(index=10, event_id='A2', timestamp_seconds=652, event_type='Clearance', team='América', possession=9),
        event(index=11, event_id='C3', timestamp_seconds=720, type_name='Corner', possession=11, player='E3'),
        event(index=12, event_id='S4', timestamp_seconds=722, event_type='Shot', possession=11, player='A4', statsbomb_xg=np.nan),
    ])


def test_corner_p0_p1_p2_traceability():
    detail, summary, claims = analyze_corners(dataset(), 'América')
    assert len(detail) == 3
    c1 = detail[detail.corner_id.eq('C1')].iloc[0]
    assert c1['target_zone'] == 'Primer palo (proxy)'
    assert c1['recipient_declared'] == 'Receptor-previsto'
    assert c1['first_registered_player'] == 'Atacante1'
    assert c1['first_registered_player'] != c1['recipient_declared']
    assert c1['first_event_delay_s'] == 1
    assert c1['shot_count'] == 2
    assert c1['first_shooter'] == 'Atacante2'
    assert abs(c1['corner_xg'] - 0.20) < 1e-12
    assert c1['goal'] and c1['high_threat']
    assert c1['xg_coverage'] == 'COMPLETE'
    assert c1['p1_evidence'] == 'EVENT_SEQUENCE_PROXY'
    assert set(z['id'] for z in claims) == {'corner_sequence_for', 'corner_sequence_against'}
    assert summary['sides']['A favor']['n_corners'] == 2
    assert summary['sides']['En contra']['n_corners'] == 1


def test_opponent_clears_p1_is_opponent_for_corner_attacker():
    d = build_corner_sequences(dataset(), 'América')
    c2 = d[d.corner_id.eq('C2')].iloc[0]
    assert c2['side'] == 'En contra'
    assert c2['first_registered_team'] == 'América'
    assert not c2['p1_team_matches_attacker']
    assert c2['target_zone'] == 'Zona central (proxy)'
    assert c2['corner_xg'] == 0.0


def test_missing_xg_is_not_fabricated_zero():
    detail, summary, _ = analyze_corners(dataset(), 'América')
    c3 = detail[detail.corner_id.eq('C3')].iloc[0]
    assert c3['shot_generated']
    assert c3['xg_coverage'] == 'MISSING_SHOT_XG'
    assert math.isnan(c3['corner_xg'])
    assert c3['high_threat'] is None
    assert summary['sides']['A favor']['xg_coverage_pct'] == 50.0


def test_360_visible_areas_do_not_imply_marking():
    frame={'C1': {'freeze_frame': [
        {'teammate':True,'location':[109,34]},
        {'teammate':False,'location':[104,37]},
        {'teammate':False,'location':[80,30]},
    ]}}
    d=build_corner_sequences(dataset(), 'América', frames360=frame)
    c1=d[d.corner_id.eq('C1')].iloc[0]
    assert c1.has_360_snapshot
    assert c1.attackers_visible_in_box == 1
    assert c1.defenders_visible_in_box == 1
    assert not d[d.corner_id.eq('C2')].iloc[0].has_360_snapshot


def test_two_corners_one_possession_do_not_double_attribute_shot():
    ev=pd.DataFrame([
        event(event_id='c1',index=1,timestamp_seconds=1, type_name='Corner'),
        event(event_id='c2',index=2,timestamp_seconds=4, type_name='Corner'),
        event(event_id='s',index=3,timestamp_seconds=6, event_type='Shot',statsbomb_xg=0.2),
    ])
    d=build_corner_sequences(ev,'América').set_index('corner_id')
    assert d.loc['c1','shot_count'] == 0
    assert d.loc['c2','shot_count'] == 1


def test_event_columns_gate():
    try:
        build_corner_sequences(pd.DataFrame({'team':['América']}), 'América')
    except ValueError as exc:
        assert 'period' in str(exc) and 'match_id' in str(exc)
    else:
        raise AssertionError('Debió fallar por columnas faltantes')
