"""EFOS Supabase Auth + RLS-aware metadata and private CSV.GZ access.

No administrator/service_role secret is used by this client. RLS protects the
catalog; Storage SELECT policy protects the original source files. The app must
only run analysis on sources returned by the authenticated catalog.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import os
import re
import time
import certifi
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

BUCKET = 'efos-private'
MAX_SOURCE_BYTES = 300 * 1024 * 1024
DATASET_UUID = re.compile(r'^[a-f0-9-]{36}$', re.I)


class CloudError(Exception):
    """Friendly, non-secret cloud error."""


def config(secrets: Any = None) -> dict[str, str] | None:
    """Return config only if both public parameters exist. Never load a service key."""
    def get(name: str) -> str:
        value = os.environ.get(name, '')
        if not value and secrets is not None:
            try:
                value = secrets.get(name, '')
            except (KeyError, AttributeError):
                pass
        return str(value).strip()
    url = get('EFOS_SUPABASE_URL').rstrip('/')
    key = get('EFOS_SUPABASE_ANON_KEY') or get('EFOS_SUPABASE_PUBLISHABLE_KEY')
    if not url and not key:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.path not in ('', '/'):
        raise CloudError('EFOS_SUPABASE_URL debe ser una URL HTTPS de Supabase sin ruta adicional.')
    if not key:
        raise CloudError('Falta EFOS_SUPABASE_ANON_KEY (clave pública).')
    if key.startswith('sb_secret_'):
        raise CloudError('No puedes utilizar una clave secreta en Streamlit; usa una publishable.')
    # Legacy JWTs carry a role. Never accept a privileged service_role token.
    if key.count('.') == 2:
        try:
            import base64
            payload = key.split('.')[1]
            decoded = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
            if decoded.get('role') == 'service_role':
                raise CloudError('No puedes utilizar una service_role en Streamlit.')
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            if isinstance(exc, CloudError):
                raise
    return {'url': url, 'anon_key': key}


def _request(cfg: dict, path: str, token: str | None = None,
             *, method: str = 'GET', payload: dict | None = None,
             binary: bool = False, max_bytes: int = MAX_SOURCE_BYTES,
             extra_headers: dict[str, str] | None = None,
             content_bytes: bytes | None = None) -> Any:
    if not path.startswith('/') or path.startswith('//'):
        raise ValueError('Ruta de API inválida.')
    headers = {'apikey': cfg['anon_key'], 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if payload is not None and content_bytes is not None:
        raise ValueError('Elige payload JSON o contenido binario.')
    headers.update(extra_headers or {})
    data = content_bytes if content_bytes is not None else (json.dumps(payload).encode('utf-8') if payload is not None else None)
    request = Request(cfg['url'] + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=180 if binary else 45,
                     context=ssl.create_default_context(cafile=certifi.where())) as response:
            if binary:
                length = int(response.headers.get('Content-Length') or 0)
                if length > max_bytes:
                    raise CloudError('El archivo supera el límite de descarga de EFOS.')
                content = response.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise CloudError('El archivo supera el límite de descarga de EFOS.')
                return content
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        # Never include response body: can contain provider diagnostics.
        status = exc.code
        if status in (400, 401):
            raise CloudError('Credenciales incorrectas o sesión de Supabase vencida.') from None
        if status == 403:
            raise CloudError('Sin permiso. Verifica membresía, RLS y política privada de Storage.') from None
        if status == 404:
            raise CloudError('No se encontró el recurso. Revisa el esquema o la ruta del archivo.') from None
        raise CloudError(f'Supabase respondió con HTTP {status}.') from None
    except (URLError, TimeoutError, OSError) as exc:
        raise CloudError('No se pudo contactar Supabase. Revisa la red y configuración.') from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CloudError('Respuesta inesperada del servicio Supabase.') from None


def sign_in(cfg: dict, email: str, password: str) -> dict:
    response = _request(cfg, '/auth/v1/token?grant_type=password', method='POST',
                        payload={'email': email, 'password': password})
    if not isinstance(response, dict) or not response.get('access_token') or not response.get('user', {}).get('id'):
        raise CloudError('Supabase Auth no devolvió una sesión válida.')
    return {**response, 'expires_at': time.time() + int(response.get('expires_in') or 3600)}


def refresh(cfg: dict, session: dict) -> dict:
    if session.get('expires_at', 0) > time.time() + 90:
        return session
    refresh_token = session.get('refresh_token')
    if not refresh_token:
        raise CloudError('Sesión caducada. Vuelve a iniciar sesión.')
    response = _request(cfg, '/auth/v1/token?grant_type=refresh_token', method='POST',
                        payload={'refresh_token': refresh_token})
    if not response.get('access_token'):
        raise CloudError('La sesión terminó. Inicia sesión de nuevo.')
    return {**response, 'expires_at': time.time() + int(response.get('expires_in') or 3600)}


def _rest(cfg: dict, token: str, table: str, fields: str, filters: dict[str, str] | None = None) -> list[dict]:
    results = []
    offset = 0
    while True:
        query = {'select': fields, 'limit': '1000', 'offset': str(offset)}
        query.update(filters or {})
        response = _request(cfg, f'/rest/v1/{table}?{urlencode(query)}', token)
        if not isinstance(response, list):
            raise CloudError('El catálogo devolvió un formato inesperado.')
        results.extend(response)
        if len(response) < 1000:
            return results
        offset += len(response)
        if offset > 50000:
            raise CloudError('El catálogo excede el límite de consulta.')


def catalog(cfg: dict, token: str) -> list[dict]:
    return _rest(cfg, token, 'efos_catalog_match_teams',
                 'organization_id,dataset_id,competition,season,period,team_name,provider_match_id,match_date,home_team,away_team,has_360,team_event_count')


def authorized_sources(cfg: dict, token: str, dataset_id: str) -> list[dict]:
    if not DATASET_UUID.fullmatch(str(dataset_id)):
        raise CloudError('Identificador de dataset inválido.')
    return _rest(cfg, token, 'efos_source_files',
                 'dataset_id,bucket,storage_path,file_sha256,source_bytes,status,competition,season,period',
                 {'dataset_id': f'eq.{dataset_id}'})


def _valid_storage_path(value: str) -> str:
    path = str(value or '')
    if not path or path.startswith(('/', '\\')) or '\\' in path or any(x in ('..', '.', '') for x in path.split('/')):
        raise CloudError('Ruta privada de almacenamiento inválida.')
    if '\x00' in path or '?' in path or '#' in path or not path.lower().endswith('.csv.gz'):
        raise CloudError('El archivo original debe ser un CSV.GZ válido.')
    return path


def cache_source(cfg: dict, token: str, source: dict, directory: Path) -> Path:
    """Download only authorized object metadata, verify bytes + SHA256, then cache."""
    if source.get('bucket') != BUCKET or source.get('status') not in ('cataloged', 'ready'):
        raise CloudError('Archivo no catalogado en el bucket privado EFOS.')
    path = _valid_storage_path(source.get('storage_path'))
    expected = str(source.get('file_sha256') or '').lower()
    if not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise CloudError('Falta el hash SHA256 original del archivo.')
    expected_size = source.get('source_bytes')
    if expected_size is not None and int(expected_size) > MAX_SOURCE_BYTES:
        raise CloudError('Archivo demasiado grande para descarga directa.')
    directory = Path(directory)
    target = directory / (expected + '.csv.gz')
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            return target
        target.unlink()
    data = _request(cfg, '/storage/v1/object/authenticated/' + quote(BUCKET, safe='') + '/' + quote(path, safe='/'),
                    token, binary=True)
    if expected_size is not None and len(data) != int(expected_size):
        raise CloudError('Tamaño diferente al registrado en el catalogador.')
    if hashlib.sha256(data).hexdigest() != expected:
        raise CloudError('El hash no coincide con el archivo registrado en Supabase.')
    directory.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.tmp')
    try:
        temporary.write_bytes(data)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def ready_run(cfg: dict, token: str, dataset_id: str, team: str, matches: list[str],
              version: str, parameters_hash: str) -> dict | None:
    """Return the exact ready analysis, never a stale or different-match result."""
    from ui.analysis_identity import scope_key
    rows = _rest(cfg, token, 'efos_analysis_runs',
                 'id,dataset_id,scope_key,focal_team,engine_version,parameters_sha256,status',
                 {'dataset_id': f'eq.{dataset_id}', 'scope_key': f'eq.{scope_key(matches)}',
                  'focal_team': f'eq.{team}', 'engine_version': f'eq.{version}',
                  'parameters_sha256': f'eq.{parameters_hash}', 'status': 'eq.ready'})
    return rows[0] if rows else None


def archived_analysis(cfg: dict, token: str, run_id: str) -> dict:
    """Read a member-authorized, content-verified result from private Storage."""
    from ui.analysis_archive import restore, sha256_bytes
    if not DATASET_UUID.fullmatch(str(run_id)):
        raise CloudError('Identificador de análisis inválido.')
    rows = _rest(cfg, token, 'efos_analysis_artifacts',
                 'analysis_run_id,storage_path,sha256,metadata,artifact_kind',
                 {'analysis_run_id': f'eq.{run_id}', 'module': 'eq.shared'})
    candidates = [r for r in rows if r.get('artifact_kind') == 'json'
                  and r.get('metadata', {}).get('format') == 'efos-safe-json-v1'
                  and str(r.get('storage_path', '')).startswith('analysis/')
                  and f'/{run_id}/' in str(r.get('storage_path', ''))]
    if len(candidates) != 1:
        raise CloudError('El resultado persistente no está completo o su formato no coincide.')
    row = candidates[0]
    digest = str(row.get('sha256') or '')
    if not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise CloudError('El resultado no tiene huella SHA-256 verificable.')
    path = _valid_artifact_path(row['storage_path'])
    raw = _request(cfg, '/storage/v1/object/authenticated/' + quote(BUCKET) + '/' + quote(path, safe='/'),
                   token, binary=True, max_bytes=48 * 1024 * 1024)
    if sha256_bytes(raw) != digest:
        raise CloudError('La integridad del análisis almacenado no coincide con el catálogo.')
    try:
        return restore(raw)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        raise CloudError('El análisis guardado está incompleto o tiene un formato incompatible.') from None


def _valid_artifact_path(path: str) -> str:
    s = str(path or '')
    if not s.startswith('analysis/') or '\\' in s or s.endswith('/') or \
       any(x in ('', '.', '..') for x in s.split('/')) or not s.endswith('.json.gz'):
        raise CloudError('Ruta de análisis no válida.')
    return s
