"""Portable, non-executable EFOS analysis snapshots (JSON + gzip).

Unlike pickle, this format cannot run Python code when read. Original StatsBomb
source files remain in private Storage and are never included in the archive.
"""
from __future__ import annotations

import datetime as dt
import gzip
import io
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

FORMAT = 'efos-safe-json-v1'
MAX_ARCHIVE_BYTES = 48 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MARKER = '__efos_archive_type__'


def _tree(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        # pandas JSON preserves nested values in object columns, without unsafe pickle.
        raw = json.loads(value.to_json(orient='split', date_format='iso', date_unit='ms',
                                      double_precision=15, default_handler=str))
        # Preserve only documented, portable diagnostic attributes needed by
        # attack filters; other .attrs may contain incompatible library objects.
        kept_attrs = {k: v for k, v in value.attrs.items()
                      if k in {'source_columns', 'outcome_available', 'team',
                               'open_play', 'restart_known'}}
        return {MARKER: 'frame', 'frame': raw, 'dtypes': {str(c): str(t) for c, t in value.dtypes.items()},
                'index_name': value.index.name, 'attrs': _tree(kept_attrs)}
    if isinstance(value, pd.Series):
        return {MARKER: 'series', 'name': value.name, 'items': _tree(value.to_list())}
    if isinstance(value, tuple):
        return {MARKER: 'tuple', 'items': [_tree(x) for x in value]}
    if isinstance(value, dict):
        return {str(k): _tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_tree(x) for x in value]
    if isinstance(value, (np.ndarray,)):
        return [_tree(x) for x in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return _tree(float(value))
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        return {MARKER: 'date', 'value': value.isoformat()}
    if isinstance(value, (Path,)):
        # A local PDF path cannot work in a different Streamlit instance.
        return None
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (bool, int, str)):
        return value
    if hasattr(value, 'item'):
        return _tree(value.item())
    raise TypeError(f'Tipo de resultado EFOS no portable: {type(value).__name__}')


def _restore(value: Any) -> Any:
    if isinstance(value, list):
        return [_restore(x) for x in value]
    if not isinstance(value, dict):
        return value
    marker = value.get(MARKER)
    if marker == 'frame':
        raw = value['frame']
        frame = pd.DataFrame(raw['data'], columns=raw['columns'])
        frame.index = pd.Index(raw['index'], name=value.get('index_name'))
        # Pandas JSON encodes tuples in object columns as lists. EFOS uses
        # hashable (match_id, period, possession, segment) tuples to connect
        # events with observed possession summaries. Restore just these known
        # key fields; leave other arrays (e.g. freeze_frame) untouched.
        for key_column in ('_poss_key', 'key'):
            if key_column in frame:
                frame[key_column] = frame[key_column].map(
                    lambda item: tuple(item) if isinstance(item, list) else item)
        for col, typ in value.get('dtypes', {}).items():
            if col not in frame:
                continue
            try:
                if typ.startswith('datetime64'):
                    frame[col] = pd.to_datetime(frame[col], errors='coerce')
                elif typ.startswith(('int', 'Int', 'uint', 'UInt', 'float', 'Float', 'boolean')):
                    frame[col] = frame[col].astype(typ)
                elif typ == 'bool' and not frame[col].isna().any():
                    frame[col] = frame[col].astype('bool')
            except (ValueError, TypeError):
                # Retain observed values rather than fabricate replacements.
                pass
        if value.get('attrs'):
            frame.attrs.update(_restore(value['attrs']))
        return frame
    if marker == 'series':
        return pd.Series(_restore(value['items']), name=value.get('name'))
    if marker == 'tuple':
        return tuple(_restore(x) for x in value['items'])
    if marker == 'date':
        return pd.Timestamp(value['value'])
    return {key: _restore(v) for key, v in value.items()}


def archive(result: dict) -> bytes:
    clean = {k: v for k, v in result.items() if k not in (
        'football_pdf_path', 'coach_story_pdf_path', '_explorer')}
    payload = {'format': FORMAT, 'analysis': _tree(clean)}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    data = gzip.compress(encoded, compresslevel=6, mtime=0)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError('El análisis comprimido supera 48 MiB. Debe dividirse en varios artefactos.')
    return data


def restore(data: bytes) -> dict:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError('El artefacto excede el tamaño admitido.')
    # Guard against decompression bombs or accidentally oversized JSON payloads.
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode='rb') as stream:
        decoded = stream.read(MAX_UNCOMPRESSED_BYTES + 1)
    if len(decoded) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError('El análisis descomprimido supera el límite de memoria.')
    payload = json.loads(decoded)
    if payload.get('format') != FORMAT:
        raise ValueError('Formato de análisis EFOS desconocido o incompatible.')
    analysis = _restore(payload['analysis'])
    if not isinstance(analysis, dict) or 'focal_team' not in analysis or 'events' not in analysis:
        raise ValueError('Resultado EFOS incompleto.')
    # Backward compatibility: snapshots made with the initial v0.4.31 codec
    # dropped DataFrame.attrs. Rebuild only facts inferable from saved,
    # *observed* event fields. This does NOT invent GPS or tactical indicators.
    attack = analysis.get('organized_attack_data')
    raw_events = analysis['events']
    if (isinstance(attack, (tuple, list)) and len(attack) == 2
            and isinstance(attack[0], pd.DataFrame)
            and isinstance(raw_events, pd.DataFrame)):
        a = attack[0]
        if 'source_columns' not in a.attrs:
            a.attrs['source_columns'] = sorted(str(c) for c in raw_events.columns)
        if 'outcome_available' not in a.attrs:
            a.attrs['outcome_available'] = bool(
                {'pass_outcome', 'outcome_name'} & set(raw_events.columns))
        if 'team' not in a.attrs:
            a.attrs['team'] = analysis['focal_team']
        if 'restart_known' not in a.attrs:
            a.attrs['restart_known'] = bool(
                'play_pattern_name' in raw_events and raw_events['play_pattern_name'].notna().any())
    return analysis


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
