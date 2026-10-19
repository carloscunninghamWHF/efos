import pandas as pd
from intelligence import organized_attack as A
from visualization import efos_smart_attack_graphs as G

def sample():
    rows=[]
    for i,(a,b,x,ex,sec) in enumerate([('A','B',20,40,0),('B','C',40,60,3),('C','D',60,85,6)]):
        rows.append(dict(event_id=f'e{i}',match_id='m',period=1,possession=1,index=i,minute=10,second=sec,
            team='Test',possession_team='Test',event_type='Pass',player=a,pass_recipient_name=b,
            location_x=x,location_y=25,end_location_x=ex,end_location_y=25,
            outcome_name=None,under_pressure=True,play_pattern_name='Regular Play'))
    return pd.DataFrame(rows)

def test_abc_and_player_scope():
    d=A.prepare_attack(sample(),'Test');t=A.possession_table(d)
    assert len(G._find_abc(d))==2
    filtered,ft=A.filter_sample(d,t,player='D')
    assert len(filtered)==3 and len(ft)==1

def test_no_join_across_opponent_touch():
    e=sample();other=e.iloc[0].copy();other['index']=.5;other['event_id']='opp';other['team']='Opponent'
    d=A.prepare_attack(pd.concat([e,pd.DataFrame([other])]),'Test')
    assert len(G._find_abc(d))==1

def test_no_join_across_period_or_time():
    e=sample();e.loc[1:,'second']=[20,40]
    assert not G._find_abc(A.prepare_attack(e,'Test'))
    e=sample();e.loc[1:,'period']=2
    assert len(G._find_abc(A.prepare_attack(e,'Test')))==1

def test_missing_ids_not_dropped_and_no_obv_invented():
    e=sample();e['event_id']=None
    d=A.prepare_attack(e,'Test');t=A.possession_table(d)
    assert len(d)==3 and t.obv.isna().all()
    fig=G.figure_primary_network_atlas(d)
    assert '0.00 OBV' not in fig.to_json()

def test_missing_outcome_does_not_complete():
    d=A.prepare_attack(sample().drop(columns='outcome_name'),'Test')
    assert not d['_pass_done'].any()

def test_restart_excludes_whole_possession():
    e=sample();e.loc[0,'type_name']='Corner'
    assert A.prepare_attack(e,'Test').empty

def test_unknown_phase_not_called_organized():
    t=A.possession_table(A.prepare_attack(sample(),'Test'))
    assert t.iloc[0].phase=='Juego abierto sin clasificación'

def test_sparse_and_empty_figures():
    d=A.prepare_attack(sample(),'Test')
    for fn in [G.figure_identity_atlas,G.figure_primary_network_atlas,G.figure_pass_network,G.figure_mechanism_board,G.figure_tactical_sequence,G.figure_pressure_exits,G.figure_halfspace_receptions,G.figure_final_routes]:
        assert fn(d).to_json()
        assert fn(d.iloc[:0]).to_json()

def test_csv_mapping_preserves_attack_fields():
    from ingestion.flexible_csv import adapt,suggest_mapping
    e=sample();e['obv_total_net']=[.1,.2,.3];e['pass_switch']=False
    mapped,report=adapt(e,suggest_mapping(e))
    assert 'pass_recipient_name' in mapped and 'obv_total_net' in mapped
    assert mapped.obv_total_net.sum()==.1+.2+.3
    assert report['defense_ready']
