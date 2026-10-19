"""Lightweight, auditable recognition/preview of CSV files uploaded to EFOS.

This module does not guess tactical semantics for unknown providers. It reads
only header and match/team/ID columns, leaving the original files untouched.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ingestion.input_adapter import inspect_csv_schema

SUPPORTED = {"STATSBOMB_WIDE", "EFOS_NORMALIZED"}


def inspect_uploaded_paths(paths) -> dict:
    """Recognize EFOS/StatsBomb tables and report actual team/match coverage."""
    paths = [Path(path) for path in paths]
    if not paths:
        raise ValueError("No hay archivos CSV para inspeccionar.")
    info = [inspect_csv_schema(path) for path in paths]
    unsupported = [Path(item["path"]).name for item in info if item["format"] not in SUPPORTED]
    if unsupported:
        return {"recognized": False, "unsupported": unsupported, "formats": [item["format"] for item in info]}

    samples = []
    event_keys = []
    all_events_identifiable = True
    original_rows = 0
    for path, meta in zip(paths, info):
        cols = set(meta["columns"])
        name = "team_name" if "team_name" in cols else "team"
        keys = [name] + (["match_id"] if "match_id" in cols else [])
        id_field = "id" if meta["format"] == "STATSBOMB_WIDE" else "event_id" if "event_id" in cols else None
        if id_field:
            keys.append(id_field)
        data = pd.read_csv(path, usecols=keys, low_memory=False)
        original_rows += len(data)
        data = data.rename(columns={name: "team"})
        if "match_id" not in data:
            data["match_id"] = path.stem
        data["match_id"] = data["match_id"].astype(str)
        if id_field:
            # Preserve provenance across multiple overlapping files.
            event_keys.append(data[["match_id", id_field]].dropna().rename(columns={id_field: "event_id"}))
            data = data.drop_duplicates(["match_id", id_field])
        else:
            all_events_identifiable = False
        data = data[["team", "match_id"]].dropna().drop_duplicates()
        samples.append(data)

    combined = pd.concat(samples, ignore_index=True).drop_duplicates()
    if combined.empty:
        return {"recognized": False, "unsupported": ["Sin equipos o partidos identificables"], "formats": [x["format"] for x in info]}
    coverage = combined.groupby("team", observed=True)["match_id"].nunique().sort_values(ascending=False)
    teams = [str(team) for team in coverage.index]
    matches = sorted(combined["match_id"].unique().tolist())
    by_match = combined.groupby("match_id", observed=True)["team"].agg(list).to_dict()
    return {
        "recognized": True,
        "unsupported": [],
        "formats": sorted(set(x["format"] for x in info)),
        "rows": int(original_rows),
        "unique_events": (len(pd.concat(event_keys, ignore_index=True).drop_duplicates())
                          if all_events_identifiable and event_keys else None),
        "matches": matches,
        "teams": teams,
        "team_matches": {str(k): int(v) for k, v in coverage.items()},
        "match_teams": {str(k): [str(x) for x in v] for k, v in by_match.items()},
        "n_files": len(paths),
    }


def match_labels(summary: dict, team: str) -> dict[str, str]:
    """Observed opponents, never guessed dates or fabricated match numbers."""
    labels = {}
    for i, mid in enumerate(summary.get("matches", []), 1):
        opponents = [t for t in summary.get("match_teams", {}).get(mid, []) if t != team]
        opponent = opponents[0] if len(opponents) == 1 else "rival no identificado"
        labels[mid] = f"Partido {i:02d} · vs {opponent}"
    return labels
