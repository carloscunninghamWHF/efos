from pathlib import Path
import hashlib
import json
import os
import pytest
from unittest.mock import patch
from ui import supabase_bridge as S


def test_config_no_secret_and_https():
    assert S.config({}) is None
    assert S.config({'EFOS_SUPABASE_URL':'https://example.supabase.co', 'EFOS_SUPABASE_ANON_KEY':'public'}) == {'url':'https://example.supabase.co','anon_key':'public'}
    with pytest.raises(S.CloudError):
        S.config({'EFOS_SUPABASE_URL':'http://bad.example.com','EFOS_SUPABASE_ANON_KEY':'key'})


def test_safe_paths():
    assert S._valid_storage_path('league/2026/file.csv.gz') == 'league/2026/file.csv.gz'
    for path in ['../x.csv.gz','/a.csv.gz','x/../../a.csv.gz','https://bad.csv.gz','x.csv','x\\a.csv.gz','x.csv.gz?key=1']:
        with pytest.raises(S.CloudError):S._valid_storage_path(path)


def test_refresh_timing():
    cfg={'url':'https://example.supabase.co','anon_key':'public'}
    s={'access_token':'ok','expires_at':10**12}
    assert S.refresh(cfg,s) is s


def test_catalog_api_is_scoped():
    cfg={'url':'https://example.supabase.co','anon_key':'public'}
    with patch.object(S,'_request',return_value=[{'team_name':'América'}]) as request:
        result=S.catalog(cfg,'user_access_token')
        assert result[0]['team_name']=='América'
        assert request.call_args[0][2]=='user_access_token'
        assert 'efos_catalog_match_teams' in request.call_args[0][1]


def test_source_sha256_verified(tmp_path):
    cfg={'url':'https://example.supabase.co','anon_key':'public'}
    data=b'\x1f\x8bcompressed placeholder'
    source={'bucket':'efos-private','status':'cataloged','file_sha256':hashlib.sha256(data).hexdigest(),
            'storage_path':'mx/file.csv.gz','source_bytes':len(data)}
    with patch.object(S,'_request',return_value=data) as req:
        path=S.cache_source(cfg,'session',source,tmp_path)
        assert path.read_bytes()==data
        assert req.call_count==1
        assert S.cache_source(cfg,'session',source,tmp_path)==path
        assert req.call_count==1
    with patch.object(S,'_request',return_value=b'wrong'):
        (tmp_path/(source['file_sha256']+'.csv.gz')).unlink()
        with pytest.raises(S.CloudError,match='Tamaño diferente'):
            S.cache_source(cfg,'session',source,tmp_path)
