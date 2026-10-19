"""EFOS Story Engine: unit tests for observation windows, flanks and narrative safeguards."""
import math
import numpy as np
import pandas as pd
from intelligence.set_piece_patterns import (
    KIND_CORNER,KIND_FREE,KIND_THROW,analyze_set_pieces,build_set_piece_sequences,
    narrative_findings,context_finding,summarize_sample,
)
from visualization.set_piece_story_maps import dual_destination_map,shot_origin_map


def ev(**kw):
    v=dict(match_id='m1',period=1,possession=1,team='A',event_type='Pass',
           type_name=None,timestamp_seconds=1.0,index=1,event_id='e0',player='T',minute=2,
           score_state='drawing',location_x=120.0,location_y=0.0,end_location_x=109.0,
           end_location_y=40.0,statsbomb_xg=np.nan,shot_outcome=None)
    v.update(kw)
    return v


def events():
    return pd.DataFrame([
        ev(index=1,event_id='c1',type_name='Corner',timestamp_seconds=1),
        ev(index=2,event_id='r1',event_type='Ball Receipt*',player='R1',timestamp_seconds=2),
        ev(index=3,event_id='s1',event_type='Shot',timestamp_seconds=5,statsbomb_xg=.1,location_x=109,location_y=40),
        ev(index=4,event_id='c2',type_name='Corner',timestamp_seconds=20,location_y=80,possession=2),
        ev(index=5,event_id='s2',event_type='Shot',timestamp_seconds=21,possession=2,statsbomb_xg=np.nan),
        ev(index=6,event_id='f1',type_name='Free Kick',timestamp_seconds=40,possession=3,location_x=90,location_y=6),
        ev(index=7,event_id='fr',event_type='Shot',timestamp_seconds=44,possession=3,statsbomb_xg=.24),
        ev(index=8,event_id='th1',type_name='Throw-in',timestamp_seconds=60,possession=4,location_x=91,location_y=78),
        ev(index=9,event_id='th2',type_name='Throw-in',timestamp_seconds=70,possession=5,location_x=55,location_y=78),
        ev(index=10,event_id='rf',type_name='Free Kick',timestamp_seconds=78,team='B',possession=6,location_x=80,location_y=76),
        ev(index=11,event_id='dr',type_name='Free Kick',event_type='Shot',timestamp_seconds=92,team='B',possession=7,statsbomb_xg=.17),
        ev(index=12,event_id='c3',type_name='Corner',timestamp_seconds=100,team='B',possession=8,location_y=80),
        ev(index=13,event_id='p3',event_type='Shot',timestamp_seconds=107,team='B',possession=8,statsbomb_xg=.19),
        ev(index=14,event_id='outside',event_type='Shot',timestamp_seconds=8,team='A',possession=99,statsbomb_xg=.99),
    ])


def test_kinds_flanks_scope_and_windows():
    d,summary,claims=analyze_set_pieces(events(),'A')
    assert len(d)==7
    c=d.set_index('set_piece_id')
    assert c.loc['c1','flank']=='Izquierda'
    assert c.loc['c2','flank']=='Derecha'
    assert c.loc['c1','first_registered_player']=='R1'
    assert c.loc['c1','shot_count']==1 and abs(c.loc['c1','xg']-.1)<1e-10
    assert c.loc['c2','xg_coverage']=='MISSING_SHOT_XG' and math.isnan(c.loc['c2','xg'])
    assert c.loc['th1','kind']==KIND_THROW
    assert 'th2' not in c.index
    assert c.loc['f1','kind']==KIND_FREE
    assert c.loc['rf','side']=='En contra'
    assert c.loc['dr','shot_count']==1 and c.loc['dr','xg']==.17
    assert c.loc['c3','side']=='En contra'
    assert summary['observations']==7


def test_no_division_errors_or_confident_statements_on_single_match():
    d,summary,claims=analyze_set_pieces(events(),'A')
    findings=narrative_findings(d,'A favor',KIND_CORNER)
    assert any('insuficiente' in f['title'].lower() for f in findings)
    assert not any('patrón con mayor xG' in f['title'].lower() for f in findings)
    assert summary['by_kind']['Córners | A favor']['xg_coverage_pct']==50.0
    assert context_finding(d,KIND_CORNER,'A favor') is None
    assert summarize_sample(d.iloc[:0])['n']==0


def test_two_kicks_in_same_possession_separate_goals_and_xg():
    d=pd.DataFrame([
        ev(index=1,event_id='f1',possession=4,type_name='Free Kick',timestamp_seconds=12),
        ev(index=2,event_id='f2',possession=4,type_name='Free Kick',timestamp_seconds=14),
        ev(index=3,event_id='sh',possession=4,event_type='Shot',timestamp_seconds=16,statsbomb_xg=.3,shot_outcome='Goal'),
    ])
    res=build_set_piece_sequences(d,'A').set_index('set_piece_id')
    assert res.loc['f1','shot_count']==0
    assert res.loc['f2','shot_count']==1
    assert res.loc['f2','goal']


def test_narrative_requires_multiple_matches_and_coverage():
    sample=[]
    for i in range(35):
        sample.append(dict(kind=KIND_CORNER,side='A favor',flank='Izquierda',target_zone='Zona central (aprox.)',
                           match_id=f'm{i%5}',set_piece_id=str(i),shot_generated=i%3==0,
                           goal=False,shot_zone='Centro del área',xg=0.1 if i%3==0 else 0,
                           xg_coverage='COMPLETE',score_state='drawing'))
    d=pd.DataFrame(sample)
    findings=narrative_findings(d,'A favor',KIND_CORNER)
    assert any('Izquierda → Zona central' in f['title'] for f in findings)
    assert any(f['title']=='Patrón más repetido' for f in findings)
    assert any(f['title']=='Patrón con mayor xG por ejecución' for f in findings)


def test_maps_draw_without_mplsoccer():
    d,_,_=analyze_set_pieces(events(),'A')
    for mode in ('zonas','trayectorias'):
        fig=dual_destination_map(d,KIND_CORNER,'A favor',mode)
        assert len(fig.axes)==2
    fig=shot_origin_map(d,KIND_CORNER,'En contra')
    assert len(fig.axes)==1


def test_empty_and_invalid_data_graceful():
    cols=list(events().columns)
    empty=pd.DataFrame(columns=cols)
    d,summary,_=analyze_set_pieces(empty,'A')
    assert d.empty and summary['observations']==0
    try:
        build_set_piece_sequences(pd.DataFrame({'team':['A']}),'A')
    except ValueError as e:
        assert 'Faltan columnas' in str(e)
    else:
        assert False
