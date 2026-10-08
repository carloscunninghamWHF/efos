import pandas as pd
from ingestion.input_adapter import load_event_csvs


def _write(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def test_load_event_csvs_merges_normalized_files(tmp_path):
    p1=tmp_path/'m1.csv'; p2=tmp_path/'m2.csv'
    _write(p1,[{'event_id':'e1','match_id':'m1','team':'Team A','event_type':'Pass','minute':1,'second':0},
               {'event_id':'e2','match_id':'m1','team':'Team B','event_type':'Pressure','minute':1,'second':1}])
    _write(p2,[{'event_id':'e3','match_id':'m2','team':'Team A','event_type':'Pass','minute':2,'second':0},
               {'event_id':'e4','match_id':'m2','team':'Team C','event_type':'Pressure','minute':2,'second':1}])
    df,meta=load_event_csvs([p1,p2])
    assert len(df)==4
    assert meta['n_files_loaded']==2
    assert meta['n_matches_loaded']==2
    assert set(meta['source_files'])=={'m1.csv','m2.csv'}
    assert 'source_file' in df.columns


def test_load_event_csvs_deduplicates_event_ids(tmp_path):
    p1=tmp_path/'a.csv'; p2=tmp_path/'b.csv'
    row={'event_id':'same','match_id':'m1','team':'Team A','event_type':'Pass','minute':1,'second':0}
    _write(p1,[row]); _write(p2,[row])
    df,meta=load_event_csvs([p1,p2])
    assert len(df)==1
    assert meta['duplicates_removed']==1


def test_multi_file_runner_matches_single_file_runner(tmp_path):
    import pytest
    from run_sprint4 import run
    src=pd.read_csv('data/raw/csv_demo/events.csv')
    whole=tmp_path/'whole.csv'; a=tmp_path/'a.csv'; b=tmp_path/'b.csv'
    src.to_csv(whole,index=False)
    cut=max(1,len(src)//2)
    src.iloc[:cut].to_csv(a,index=False); src.iloc[cut:].to_csv(b,index=False)
    r1=run(whole,'Team A')
    r2=run([a,b],'Team A')
    assert r2['input_metadata']['n_files_loaded']==2
    assert r1['ESI']==pytest.approx(r2['ESI'])
    assert r1['esi_dimensions']==pytest.approx(r2['esi_dimensions'])
