"""Regression: no silent fallback to auth/users.txt when Supabase config is absent."""
from pathlib import Path
import pytest
from ui.cloud_auth_config import require_cloud_config
from ui.supabase_bridge import CloudError


def test_reads_secrets_from_project_root_even_with_other_cwd(tmp_path, monkeypatch):
    secrets = tmp_path/'.streamlit'/'secrets.toml'
    secrets.parent.mkdir()
    secrets.write_text('EFOS_SUPABASE_URL = "https://testing.supabase.co"\nEFOS_SUPABASE_ANON_KEY = "sb_publishable_test"\n')
    other = tmp_path/'other'
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.delenv('EFOS_SUPABASE_URL',raising=False)
    monkeypatch.delenv('EFOS_SUPABASE_ANON_KEY',raising=False)
    monkeypatch.delenv('EFOS_SUPABASE_PUBLISHABLE_KEY',raising=False)
    assert require_cloud_config(tmp_path, {})['url']=='https://testing.supabase.co'


def test_missing_config_fails_closed(tmp_path, monkeypatch):
    for v in ['EFOS_SUPABASE_URL','EFOS_SUPABASE_ANON_KEY','EFOS_SUPABASE_PUBLISHABLE_KEY']:
        monkeypatch.delenv(v,raising=False)
    with pytest.raises(CloudError,match='No se utilizará auth/users.txt'):
        require_cloud_config(tmp_path,{})


def test_missing_config_runtime_secrets(tmp_path, monkeypatch):
    for v in ['EFOS_SUPABASE_URL','EFOS_SUPABASE_ANON_KEY','EFOS_SUPABASE_PUBLISHABLE_KEY']:
        monkeypatch.delenv(v,raising=False)
    cfg=require_cloud_config(tmp_path,{'EFOS_SUPABASE_URL':'https://testing.supabase.co','EFOS_SUPABASE_ANON_KEY':'sb_publishable_test'})
    assert cfg['anon_key']=='sb_publishable_test'


def test_local_service_key_rejected(tmp_path, monkeypatch):
    for v in ['EFOS_SUPABASE_URL','EFOS_SUPABASE_ANON_KEY','EFOS_SUPABASE_PUBLISHABLE_KEY']:
        monkeypatch.delenv(v,raising=False)
    secrets=tmp_path/'.streamlit'/'secrets.toml'
    secrets.parent.mkdir()
    secrets.write_text('EFOS_SUPABASE_URL = "https://testing.supabase.co"\nEFOS_SUPABASE_ANON_KEY = "sb_secret_fake"\n')
    with pytest.raises(CloudError,match='clave secreta'):
        require_cloud_config(tmp_path,{})


def test_dashboard_does_not_reference_legacy_auth():
    text=(Path(__file__).resolve().parents[1]/'visualization'/'efos_dashboard.py').read_text()
    assert 'authenticate(username,password)' not in text
    assert 'return require_cloud_config(BASE_DIR, st.secrets)' in text
