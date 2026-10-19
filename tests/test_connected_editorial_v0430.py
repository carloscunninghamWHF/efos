"""Safeguards for the simplified cross-module EFOS editorial report."""
from __future__ import annotations
from io import BytesIO
import pandas as pd
from visualization.connected_diagnosis import choose_events, coherent_observations
from coach_story.connected_pdf import build_connected_pdf


def _sample():
    events=pd.DataFrame({'match_id':['A','A','B','B'],'team':['América','Rival A','América','Rival B']})
    pos=pd.DataFrame({'shots':[1,0,0,1,0],'box_entries':[1,1,0,1,0]})
    d=pd.DataFrame({'scenario':['Posicional']*12 + ['Contraataque']*4,'shot':[1,0]*6+[0]*4})
    transitions=pd.DataFrame({'match_id':['A','A','B','B'],
                              'team_lost':['América','Rival A','América','Rival B'],
                              'response_within_5s':[True,True,False,False]})
    return {'events':events,'focal_team':'América','organized_attack_data':(pd.DataFrame(),pos),
            'defensive_open_play_possessions':d,'transitions':transitions,
            'offensive_story':{'connection':{'from':'Uno','to':'Dos','completed':4}}}


def test_global_match_filter_is_exact():
    ev=_sample()['events']
    assert len(choose_events(ev,['A'])) == 2
    assert choose_events(ev,['C']).empty
    assert len(choose_events(ev,None))==4


def test_editorial_has_three_observed_facts_and_no_causal_shortcuts():
    report=coherent_observations(_sample())
    assert report['matches']==2
    assert len(report['findings'])==3
    attack,defense,loss=report['findings']
    assert '2 de 5 posesiones' in attack['text']
    assert 'Uno → Dos (4 pases)' in attack['text']
    assert '6 de 12' in defense['text']
    assert '1 de 2 pérdidas' in loss['text']
    assert 'intervención' in loss['text']
    assert 'recuperación' in loss['meaning']
    assert not any('presión exitosa' in f['text'] for f in report['findings'])


def test_transitions_exclude_opponent_loss_and_no_global_fallback():
    r=_sample()
    r['transitions']=pd.DataFrame({'match_id':['B'], 'team_lost':['Rival'], 'response_within_5s':[True]})
    assert 'perdida' not in {f['id'] for f in coherent_observations(r)['findings']}


def test_pdf_uses_same_observations_one_page():
    import fitz
    report=coherent_observations(_sample())
    contents=build_connected_pdf(report)
    page=fitz.open(stream=contents,filetype='pdf')
    assert len(page)==1
    body=page[0].get_text()
    assert '2 partidos' in body
    assert 'Uno' in body
    assert 'Muestra:' in body
    for f in report['findings']:
        assert f['title'][:20] in body
