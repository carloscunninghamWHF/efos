"""Safe persistence helpers for Streamlit-uploaded EFOS input files."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


def safe_filename(name: str) -> str:
    """Return a conservative filename while preserving a .csv extension."""
    base = Path(str(name or "events.csv")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(base).stem).strip("._") or "events"
    return f"{stem[:100]}.csv"


def persist_csv_bytes(data: bytes, original_name: str, root: str | Path, username: str) -> tuple[Path, str]:
    """Persist an uploaded CSV under a deterministic content hash.

    Returns (path, sha256). Existing identical uploads are reused.
    """
    if not data:
        raise ValueError("El archivo está vacío.")
    digest = hashlib.sha256(data).hexdigest()
    user = re.sub(r"[^A-Za-z0-9_-]+", "_", str(username)).strip("_") or "user"
    target_dir = Path(root) / "uploads" / user
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{digest[:12]}_{safe_filename(original_name)}"
    if not target.exists():
        target.write_bytes(data)
    return target, digest
