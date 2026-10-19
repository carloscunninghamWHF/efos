"""Narrative must agree with the exact filtered StatsBomb sample and not invent context."""
from __future__ import annotations
import pandas as pd
import pytest
from intelligence import organized_attack as A
from intelligence.offensive_story import build_offensive_story,readable_match_labels,coach_claims
from visualization.attack_story_figures import figure_sequence_board,figure_attack_route,figure_attack_outcomes,sequence_script


def sample():
    rows=[]
    for match in ['m1','m2','m3']:
        for poss in range(1,11):
            for i,(a,b,x,nx,kind) in enumerate([('Central','Pivote',23,46,'Pass'),('Pivote','Extremo',46,86,'Pass'),('Extremo','Atacante',86,107,'Pass'),('Atacante',None,108,110,'Shot')]):
                rows.append({'event_id':f'{match}-{poss}-{i}','match_id':match,'period':1,'possession':poss,
                             'index':100*poss+i,'minute':poss+2,'second':i*2,'team':'A',
                             'possession_team':'A','event_type':kind,'player':a,'pass_recipient_name':b,
                             'location_x':x,'location_y':26,'end_location_x':nx,'end_location_y':35,
                             'play_pattern_name':'Regular Play', 'outcome_name':None,
                             'under_pressure':False,'is_controlled_possession':True,
                             'statsbomb_xg':.14 if kind=='Shot' else None})
    return pd.DataFrame(rows)


def test_story_has_denominators_and_claim_provenance():
    d=A.prepare_attack(sample(),'A');t=A.possession_table(d)
    story=build_offensive_story(d,t)
    assert story['n_possessions']==30 and story['n_matches']==3
    assert story['entry']['denominator']==30
    assert story['connection']['completed']==30
    assert story['connection']['matches']==3
    assert '30 secuencias' in story['overview']
    claims=coach_claims(story)
    assert claims and all(c['n']<=c['evidence']['denominator'] for c in claims)
    assert all(c['source'] for c in claims)


def test_story_recalculates_after_filter_and_marks_small_sample():
    d=A.prepare_attack(sample(),'A');t=A.possession_table(d)
    dd,tt=A.filter_sample(d,t,['m1'])
    s=build_offensive_story(dd,tt)
    assert s['n_possessions']==10 and s['n_matches']==1 and s['status']=='SMALL_SAMPLE'
    assert 'identidad consolidada' not in s['overview']


def test_match_labels_never_invent_matchday():
    e=pd.DataFrame([{'match_id':'40004042','team':'A'}, {'match_id':'40004042','team':'Rival'},
                    {'match_id':'40004043','team':'A'}])
    labels=readable_match_labels(e,'A',['40004042','40004043'])
    assert 'vs Rival' in labels['40004042']
    assert 'Rival no identificado' in labels['40004043']
    assert '40004042' not in labels['40004042']
    assert 'Jornada' not in labels['40004042']


def test_graphs_only_observed_actions():
    d=A.prepare_attack(sample(),'A');t=A.possession_table(d)
    key=t.iloc[0]['key']
    assert figure_sequence_board(d,key).to_json()
    assert figure_attack_route(d,'Construcción').to_json()
    assert figure_attack_outcomes(d,'Remates').to_json()
    assert sequence_script(d,key)
    assert not sequence_script(d,key)[0].startswith('Arrastre')


def test_absence_of_completion_prevents_connection_claim():
    raw=sample().drop(columns=['outcome_name'])
    d=A.prepare_attack(raw,'A');t=A.possession_table(d)
    st=build_offensive_story(d,t)
    assert st['connection'] is None


def test_empty_does_not_create_story():
    s=build_offensive_story(pd.DataFrame(),pd.DataFrame())
    assert s['status']=='INSUFFICIENT' and not s['insights']
