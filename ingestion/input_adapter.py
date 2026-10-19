"""Generic CSV adapter for EFOS.

Supports two event-table families without team-specific logic:
1) EFOS normalized CSV (team, event_type, match_id, ...)
2) StatsBomb wide CSV export (team_name, event_type_name, id, period, ...)

The adapter returns the canonical EFOS event DataFrame plus metadata describing
how the source was interpreted. Unsupported schemas fail explicitly rather than
being silently coerced.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from ingestion.statsbomb_wide_csv import load_statsbomb_wide

NORMALIZED_REQUIRED = {"team", "event_type"}
STATSBOMB_WIDE_REQUIRED = {"team_name", "event_type_name", "id", "match_id", "period"}


def inspect_csv_schema(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el CSV: {path}")
    cols = list(pd.read_csv(path, nrows=0).columns)
    colset = set(cols)
    if STATSBOMB_WIDE_REQUIRED.issubset(colset):
        fmt = "STATSBOMB_WIDE"
    elif NORMALIZED_REQUIRED.issubset(colset):
        fmt = "EFOS_NORMALIZED"
    else:
        fmt = "UNSUPPORTED"
    return {
        "path": str(path),
        "format": fmt,
        "columns": cols,
        "n_columns": len(cols),
        "missing_normalized_required": sorted(NORMALIZED_REQUIRED - colset),
        "missing_statsbomb_wide_required": sorted(STATSBOMB_WIDE_REQUIRED - colset),
    }


def _standardize_flat(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Bring common flat-CSV aliases into EFOS canonical columns without dropping extras."""
    aliases={
        "team_name":"team", "type":"event_type", "event":"event_type",
        "x":"location_x", "y":"location_y", "loc_x":"location_x", "loc_y":"location_y",
        "end_x":"end_location_x", "end_y":"end_location_y",
        "id":"event_id", "idx":"index", "player_name":"player",
    }
    rename={k:v for k,v in aliases.items() if k in df.columns and v not in df.columns}
    df=df.rename(columns=rename).copy()
    if "match_id" not in df.columns: df["match_id"]=path.stem
    df["match_id"]=df["match_id"].astype(str)
    if "index" not in df.columns: df["index"]=range(1,len(df)+1)
    if "timestamp_seconds" not in df.columns and {"minute","second"}.issubset(df.columns):
        df["timestamp_seconds"]=pd.to_numeric(df["minute"],errors="coerce")*60+pd.to_numeric(df["second"],errors="coerce")
    if "outcome_name" not in df.columns:
        df["outcome_name"]=pd.NA
        if "pass_outcome" in df.columns:
            mask=df["event_type"].astype(str).eq("Pass"); df.loc[mask,"outcome_name"]=df.loc[mask,"pass_outcome"]
        if "shot_outcome" in df.columns:
            mask=df["event_type"].astype(str).eq("Shot"); df.loc[mask,"outcome_name"]=df.loc[mask,"shot_outcome"]
        if "duel_outcome" in df.columns:
            mask=df["event_type"].astype(str).eq("Duel"); df.loc[mask,"outcome_name"]=df.loc[mask,"duel_outcome"]
    if "under_pressure" not in df.columns: df["under_pressure"]=False
    return df


def load_event_csv(path: str | Path) -> tuple[pd.DataFrame, dict]:
    path = Path(path)
    meta = inspect_csv_schema(path)
    if meta["format"] == "STATSBOMB_WIDE":
        df = load_statsbomb_wide([path])
    elif meta["format"] == "EFOS_NORMALIZED":
        df = _standardize_flat(pd.read_csv(path, low_memory=False),path)
    else:
        raise ValueError(
            "CSV no compatible con EFOS. Se requiere un CSV normalizado con "
            "['team','event_type'] o un export ancho de StatsBomb con "
            "['team_name','event_type_name','id','match_id','period']. "
            f"Columnas encontradas: {meta['columns'][:25]}"
        )
    meta.update({
        "n_source_rows": int(df.attrs.get("n_source_rows", len(df))),
        "source_duplicates_removed": int(df.attrs.get("source_duplicates_removed", 0)),
        "duplicates_removed": int(df.attrs.get("source_duplicates_removed", 0)),
        "n_events_loaded": int(len(df)),
        "n_matches_loaded": int(df["match_id"].nunique()) if "match_id" in df else 0,
        "teams_found": sorted(df["team"].dropna().astype(str).unique().tolist()) if "team" in df else [],
    })
    return df, meta


def load_event_csvs(paths) -> tuple[pd.DataFrame, dict]:
    """Load and merge one or more compatible event CSV files.

    Every file is normalized independently through :func:`load_event_csv`, then
    concatenated into the canonical EFOS event schema. Duplicate events are
    removed conservatively when a stable identifier is available.
    """
    paths = [Path(p) for p in paths]
    if not paths:
        raise ValueError("Debes cargar al menos un archivo CSV.")

    frames = []
    source_meta = []
    for path in paths:
        df, meta = load_event_csv(path)
        df = df.copy()
        df["source_file"] = path.name
        frames.append(df)
        source_meta.append(meta)

    merged = pd.concat(frames, ignore_index=True, sort=False)
    rows_before = int(len(merged))

    # Deduplicate by match + provider event ID; never merge distinct matches
    # solely because a provider has reused an identifier.
    if "event_id" in merged.columns and merged["event_id"].notna().any():
        keys=["match_id", "event_id"] if "match_id" in merged.columns else ["event_id"]
        with_id = merged[merged["event_id"].notna()].drop_duplicates(subset=keys, keep="first")
        without_id = merged[merged["event_id"].isna()]
        merged = pd.concat([with_id, without_id], ignore_index=True, sort=False)
    elif {"match_id", "index", "team", "event_type"}.issubset(merged.columns):
        merged = merged.drop_duplicates(subset=["match_id", "index", "team", "event_type"], keep="first")

    formats = sorted({m["format"] for m in source_meta})
    meta = {
        "path": [str(p) for p in paths],
        "format": formats[0] if len(formats) == 1 else "MULTI_FORMAT",
        "source_formats": formats,
        "source_files": [p.name for p in paths],
        "n_files_loaded": len(paths),
        "n_events_before_dedup": rows_before,
        "n_events_loaded": int(len(merged)),
        "duplicates_removed": int(sum(m.get("source_duplicates_removed", 0) for m in source_meta)) + rows_before - int(len(merged)),
        "n_source_rows": int(sum(m.get("n_source_rows", m["n_events_loaded"]) for m in source_meta)),
        "n_matches_loaded": int(merged["match_id"].nunique()) if "match_id" in merged else 0,
        "teams_found": sorted(merged["team"].dropna().astype(str).unique().tolist()) if "team" in merged else [],
    }
    return merged.reset_index(drop=True), meta
