"""Persistence must keep scientific evidence and DataFrames intact, not a summary only."""
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch

from ui.analysis_archive import archive, restore, sha256_bytes
from ui.analysis_identity import scope_key, signature
from ui import supabase_bridge as SB


def test_archive_roundtrip_exact_dataframe_and_nested_tuple():
    df=pd.DataFrame({'match_id':['001','002'], 'x':[1.0, np.nan],
                     'pressure':[True, False], 'freeze_frame':[[{'x':1.1}], []]})
    result={'focal_team':'América','events':df,'organized_attack_data':(df.copy(),pd.DataFrame()),
            'football_report':{'per_match':df.copy(), 'textos':{'identidad':'Datos medidos'}}}
    data=archive(result)
    assert data==archive(result)
    loaded=restore(data)
    pd.testing.assert_frame_equal(loaded['events'],df,check_dtype=False)
    assert loaded['events']['match_id'].to_list()==['001','002']
    assert isinstance(loaded['organized_attack_data'],tuple)
    assert loaded['football_report']['textos']['identidad']=='Datos medidos'
    assert sha256_bytes(data)==sha256_bytes(archive(result))


def test_restore_rejects_unknown_payload():
    import gzip,json,pytest
    data=gzip.compress(json.dumps({'format':'untrusted-pickle','analysis':{}}).encode())
    with pytest.raises(ValueError, match='desconocido'):
        restore(data)


def test_scope_prevents_cross_match_cache_mix():
    assert scope_key(['002','001'])==scope_key(['001','002'])
    assert scope_key(['001'])!=scope_key(['002'])
    ver,key=signature()
    assert ver.startswith('EFOS') and len(key)==64


def test_load_ready_artifact_checks_sha():
    result={'focal_team':'Equipo','events':pd.DataFrame({'x':[1]})}
    blob=archive(result)
    uid='11111111-1111-1111-1111-111111111111'
    rows=[{'analysis_run_id':uid, 'artifact_kind':'json',
           'metadata':{'format':'efos-safe-json-v1'},
           'sha256':sha256_bytes(blob),
           'storage_path':f'analysis/dataset/{uid}/analysis.json.gz'}]
    cfg={'url':'https://x.supabase.co','anon_key':'public'}
    with patch.object(SB,'_rest',return_value=rows),patch.object(SB,'_request',return_value=blob):
        got=SB.archived_analysis(cfg,'token',uid)
        assert got['events'].x.iloc[0]==1
    import pytest
    with patch.object(SB,'_rest',return_value=rows),patch.object(SB,'_request',return_value=b'bad'):
        with pytest.raises(SB.CloudError,match='integridad'):
            SB.archived_analysis(cfg,'token',uid)
