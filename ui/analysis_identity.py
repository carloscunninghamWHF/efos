"""Single source of truth for EFOS analysis identity and invalidation."""
from __future__ import annotations
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIRS = ('coach_story', 'behavior', 'context', 'esi', 'ingestion',
               'intelligence', 'interpretation', 'metrics', 'normalization',
               'objects', 'players', 'states', 'transitions', 'defense',
               'offense', 'set_pieces')


@lru_cache(maxsize=1)
def signature() -> tuple[str, str]:
    """Hash the engine implementation and configuration, not only a UI version label.

    Updating analysis Python or YAML forces a new run. The caller must restart
    Streamlit after deploying a new revision, which is normal for deployments.
    """
    files = [ROOT / 'run_sprint4.py', ROOT / 'run_sprint2.py', ROOT / 'VERSION.txt']
    for directory in ENGINE_DIRS:
        folder = ROOT / directory
        if folder.exists():
            files.extend(folder.rglob('*.py'))
    files.extend((ROOT / 'config').rglob('*.yaml'))
    sha = hashlib.sha256()
    for path in sorted(set(files)):
        if path.is_file():
            sha.update(path.relative_to(ROOT).as_posix().encode())
            sha.update(hashlib.sha256(path.read_bytes()).digest())
    ver = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').split('—')[0].strip() if (ROOT / 'VERSION.txt').exists() else 'EFOS'
    return ver[:80], sha.hexdigest()


def scope_key(match_ids) -> str:
    ids = sorted({str(x) for x in match_ids})
    if not ids:
        raise ValueError('La muestra debe incluir partidos.')
    raw = json.dumps(ids, separators=(',', ':'), ensure_ascii=False)
    return 'matches:' + hashlib.sha256(raw.encode('utf-8')).hexdigest()
