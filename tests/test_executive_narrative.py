"""UI storytelling must not exceed evidence and must work with arbitrary teams."""
import pandas as pd
from coach_story.executive_narrative import build_executive_chapters


def test_no_source_does_not_invent_results():
    out = build_executive_chapters({'focal_team': 'Cualquier Equipo'})
    assert len(out) == 3
    assert all(x['status'] == 'INSUFFICIENT' for x in out)
    assert 'Cualquier Equipo' not in str(out)


def test_chapters_respect_counts_and_unknown_defensive_rows():
    result = {
        'focal_team':'Club B',
        'offensive_story':{'status':'DESCRIPTIVE','n_possessions':25,'n_matches':3,
            'entry':{'lane':'Derecha','count':12,'denominator':20,'share':.6},'productivity':{'shots':4}},
        'defensive_open_play_possessions':pd.DataFrame({'scenario':['Defensa ante contraataque','Otro juego abierto'],
            'shot':[1,0],'match_id':['A','A']}),
        'transitions':pd.DataFrame({'team_lost':['Club B','Club B','Rival'],'response_within_5s':[True,False,True],
            'match_id':['A','A','A']})}
    out = build_executive_chapters(result)
    assert len(out)==3
    assert '12 de 20' in out[0]['observation']
    assert '1 de 1' in out[1]['observation']
    assert '1 sin clasificación' in out[1]['evidence']
    assert '1 de 2' in out[2]['observation']
    assert all(x['module'] in ('Ataque Organizado','Defensa Organizada','Transiciones') for x in out)


def test_unsourced_recommendations_not_created():
    out = build_executive_chapters({})
    assert 'presionarle' not in str(out).lower()
    assert 'vulnerabilidad clave' not in str(out).lower()
