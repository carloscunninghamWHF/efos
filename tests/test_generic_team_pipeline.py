import pandas as pd
import pytest
from intelligence.team_scope import resolve_focal_team, team_coverage, slugify_team
from ingestion.input_adapter import load_event_csv, inspect_csv_schema


def team_centric_sample():
    rows=[]
    idx=0
    for m,opp in [('m1','Opp1'),('m2','Opp2'),('m3','Opp3')]:
        for team in ['Club X',opp]:
            for j in range(3):
                idx += 1
                rows.append({'match_id':m,'event_id':str(idx),'index':idx,'team':team,'event_type':'Pass','minute':j,'second':0,'timestamp_seconds':j*60.0,'location_x':20.0,'location_y':40.0,'end_location_x':30.0,'end_location_y':40.0,'under_pressure':False})
    return pd.DataFrame(rows)


def test_auto_detect_team_from_match_coverage():
    df=team_centric_sample()
    team,meta=resolve_focal_team(df,'auto')
    assert team=='Club X'
    assert meta['mode']=='auto_full_coverage'
    assert team_coverage(df).iloc[0].matches==3


def test_explicit_team_works_for_any_name():
    df=team_centric_sample().replace({'Club X':'Equipo Ñandú'})
    team,meta=resolve_focal_team(df,'Equipo Ñandú')
    assert team=='Equipo Ñandú' and meta['mode']=='explicit'
    assert slugify_team(team)=='equipo_nandu'


def test_ambiguous_single_match_requires_selection():
    df=team_centric_sample(); df=df[df.match_id.eq('m1')]
    with pytest.raises(ValueError):
        resolve_focal_team(df,'auto')


def test_input_adapter_normalized(tmp_path):
    p=tmp_path/'events.csv'; team_centric_sample().to_csv(p,index=False)
    assert inspect_csv_schema(p)['format']=='EFOS_NORMALIZED'
    df,meta=load_event_csv(p)
    assert meta['format']=='EFOS_NORMALIZED' and len(df)>0


def test_team_name_does_not_change_formulas(tmp_path):
    from run_sprint4 import run
    src=pd.read_csv('data/raw/csv_demo/events.csv')
    p1=tmp_path/'a.csv'; src.to_csv(p1,index=False)
    renamed=src.replace({'Team A':'Club Renamed A','Team B':'Club Renamed B'})
    p2=tmp_path/'b.csv'; renamed.to_csv(p2,index=False)
    r1=run(p1,'Team A')
    r2=run(p2,'Club Renamed A')
    assert r1['ESI']==pytest.approx(r2['ESI'])
    assert r1['esi_dimensions']==pytest.approx(r2['esi_dimensions'])
    assert r1['hps_meta']['n_actions']==r2['hps_meta']['n_actions']
    assert r1['trap_metrics']==pytest.approx(r2['trap_metrics'])
