"""Regression: archived possession keys must preserve Plotly graph evidence."""
import pandas as pd
from ui.analysis_archive import archive, restore
from visualization.attack_story_figures import figure_sequence_board, sequence_script
from intelligence.organized_attack import filter_sample


def _events():
    key=('3939821',1,17,0)
    frame=pd.DataFrame([
        {'_poss_key':key,'match_id':'3939821','index':10,'_type':'pass','event_type':'Pass',
         'player':'A','minute':32,'location_x':48.,'location_y':35.,
         'end_location_x':75.,'end_location_y':40.,'_pass_done':True,
         'pass_recipient_name':'B'},
        {'_poss_key':key,'match_id':'3939821','index':11,'_type':'shot','event_type':'Shot',
         'player':'B','minute':32,'location_x':105.,'location_y':38.,
         'end_location_x':None,'end_location_y':None,'_pass_done':False,
         'pass_recipient_name':None},
    ])
    frame.attrs['source_columns']=['pass_recipient_name','outcome_name']
    frame.attrs['outcome_available']=True
    frame.attrs['team']='Guadalajara'
    table=pd.DataFrame([{'key':key,'match_id':'3939821','actions':2,'minute':32.,
                          'phase':'Juego abierto sin clasificación'}])
    return frame, table


def test_restored_hero_draws_real_actions():
    d,t=_events()
    blob=archive({'events':d,'focal_team':'Guadalajara','organized_attack_data':(d,t)})
    result=restore(blob)
    a,b=result['organized_attack_data']
    key=b.iloc[0]['key']
    assert isinstance(key,tuple)
    assert isinstance(a.iloc[0]['_poss_key'],tuple)
    assert a.attrs['outcome_available'] is True
    assert a.attrs['source_columns']==['pass_recipient_name','outcome_name']
    fig=figure_sequence_board(a,key)
    assert len(fig.data)>=2
    assert sequence_script(a,key)==['A pasa a B (completado)','B remata']
    filtered,_=filter_sample(a,b,matches=['3939821'])
    assert len(filtered)==2


def test_other_lists_unchanged_after_restore():
    key=('12',1,8,0)
    df=pd.DataFrame({'_poss_key':[key], 'freeze_frame':[[{'x':5,'y':22}]]})
    result=restore(archive({'events':df,'focal_team':'T'}))
    got=result['events']
    assert isinstance(got.iloc[0]['_poss_key'],tuple)
    assert isinstance(got.iloc[0]['freeze_frame'],list)


def test_set_piece_rows_survive_snapshot():
    from tests.test_set_piece_story import events
    from intelligence.set_piece_patterns import analyze_set_pieces, KIND_CORNER
    src,summary,_=analyze_set_pieces(events(),'A')
    loaded=restore(archive({'events':events(),'focal_team':'A',
                            'set_piece_sequences':src,'set_piece_summary':summary}))
    s=loaded['set_piece_sequences']
    assert len(s)==7
    assert len(s[(s['kind']==KIND_CORNER)&(s['side']=='A favor')])==2


def test_legacy_snapshot_restores_observed_possession_keys():
    """The already uploaded Guadalajara snapshot predates the codec repair."""
    import gzip, io, json
    d,t=_events()
    result={'events':d.assign(pass_outcome=[None,None]),'focal_team':'Guadalajara','organized_attack_data':(d,t)}
    old_blob=archive(result)
    uncompressed=json.loads(gzip.decompress(old_blob))
    # Simulate the original v0.4.31 JSON payload: no DataFrame attrs.
    attack=uncompressed['analysis']['organized_attack_data']['items']
    for frame in attack:
        frame.pop('attrs',None)
    raw=gzip.compress(json.dumps(uncompressed).encode('utf-8'))
    restored=restore(raw)
    dd,tt=restored['organized_attack_data']
    assert isinstance(dd.iloc[0]['_poss_key'],tuple)
    assert isinstance(tt.iloc[0]['key'],tuple)
    assert dd.attrs['outcome_available'] is True
    assert figure_sequence_board(dd,tt.iloc[0]['key']).data
