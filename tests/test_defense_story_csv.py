import pandas as pd
import pytest
from ingestion.flexible_csv import read_flexible,adapt,suggest_mapping
from tests.test_defensive_insights import fixture,insights
from intelligence.defensive_open_play import normalize_events
from visualization.defensive_storytelling import route_patterns,lane_comparison
from intelligence.defensive_insights import zone_exposure

def test_csv_delimiter_encoding_and_mapping():
    df,enc=read_flexible('equipo;evento\nMálaga;Pase\n'.encode('cp1252'))
    mapped,r=adapt(df,suggest_mapping(df),{'Pase':'Pass'})
    assert mapped.team.iloc[0]=='Málaga' and not r['defense_ready'] and not r['unknown_events']

def test_native_data_new_team_no_source_mutation():
    df=fixture().replace({'A':'Club Nuevo','B':'Rival'});original=df.copy(deep=True)
    out,r=adapt(df,suggest_mapping(df))
    assert r['defense_ready'] and r['teams']==['Club Nuevo','Rival']
    pd.testing.assert_frame_equal(df,original)

def test_coordinate_rotation_and_invalid_location():
    df=fixture();df['direction']=-1
    out,r=adapt(df,suggest_mapping(df),orientation='fixed',direction='direction')
    assert out.location_x.iloc[0]==80 and out.location_y.iloc[0]==40
    df.loc[0,'location_x']=150
    out,r=adapt(df,suggest_mapping(df))
    assert r['invalid_coordinates']==1 and pd.isna(out.location_x.iloc[0])

def test_clock_and_duplicate_order():
    df=fixture();df.loc[0,'second']=99
    out,r=adapt(df,suggest_mapping(df))
    assert r['excluded']==1 and len(out)==5
    df=fixture();df.loc[1,'index']=df.loc[0,'index']
    assert not adapt(df,suggest_mapping(df))[1]['defense_ready']

def test_missing_outcome_and_unknown_events():
    df=fixture().drop(columns='outcome_name')
    assert not adapt(df,suggest_mapping(df))[1]['defense_ready']
    df=fixture();df.loc[0,'event_type']='Mystery'
    assert not adapt(df,suggest_mapping(df))[1]['defense_ready']

def test_pattern_and_denominators():
    df=fixture();d=insights(df);p=route_patterns(d,normalize_events(df),'A')
    assert len(p)==1 and p.iloc[0]['end'].endswith('carril central')
    z=zone_exposure(d);fig=lane_comparison(z)
    assert sum(fig.data[0].x)+sum(fig.data[1].x)==z.posesiones.sum()

def test_duplicate_mapping_rejected():
    with pytest.raises(ValueError):adapt(fixture(),{'team':'team','possession_team':'team'})

def test_csv_workbench_end_to_end():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    root=str(Path(__file__).resolve().parents[1])
    code=f'''import sys
sys.path.insert(0,{root!r})
import streamlit as st
from tests.test_defensive_insights import fixture
class Upload:
    def getvalue(self): return fixture().to_csv(index=False).encode()
st.file_uploader=lambda *a,**kw:[Upload()]
from visualization.csv_workbench import render_csv_workbench
render_csv_workbench()
'''
    app=AppTest.from_string(code).run(timeout=30)
    assert not app.exception
    semantics=next(x for x in app.checkbox if 'Confirmo' in x.label)
    semantics.check().run(timeout=30)
    assert not app.exception
    assert any('Muestra CSV activa' in x.value for x in app.success)
    app.radio[0].set_value('Estadísticas agregadas').run(timeout=30)
    assert not app.exception

def test_exact_repeated_rows_collapse_but_conflicts_block():
    df=fixture();df=pd.concat([df,df.iloc[[1]]],ignore_index=True)
    out,r=adapt(df,suggest_mapping(df))
    assert r['defense_ready'] and r['exact_duplicates_removed']==1 and len(out)==6
