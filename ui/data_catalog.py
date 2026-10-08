"""Repositorio local de datasets EFOS.

Convierte archivos CSV almacenados en ``data/raw/statsbomb`` en un catálogo
navegable Liga -> Temporada -> Equipo -> Periodo. La interfaz deja de pedir
uploads manuales: consume directamente los archivos disponibles en el repo.

Convención recomendada de nombres:
    Liga_MX_2025_2026_Club_America_p1.csv
    Liga_MX_2025_2026_Club_America_p2.csv

El equipo focal NO se toma del nombre del archivo: se infiere de la cobertura
por match_id (el equipo presente en más partidos). Esto evita depender de
acentos o nombres de archivo imperfectos.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

PERIOD_LABELS = {"p1": "Apertura (P1)", "p2": "Clausura (P2)"}
ALL_PERIODS = "Temporada completa"


def _humanize_league(raw: str) -> str:
    s = re.sub(r"[_-]+", " ", raw).strip()
    s = re.sub(r"\s+", " ", s)
    return s.replace("Liga Mx", "Liga MX").replace("Liga mx", "Liga MX")


def _parse_filename(path: Path) -> tuple[str, str, str]:
    stem = path.stem
    period = "p1" if re.search(r"(?:^|[_-])p1$", stem, re.I) else "p2" if re.search(r"(?:^|[_-])p2$", stem, re.I) else "full"
    stem0 = re.sub(r"(?:[_-])p[12]$", "", stem, flags=re.I)
    m = re.search(r"(20\d{2})[_-](20\d{2})", stem0)
    if m:
        season = f"{m.group(1)}-{m.group(2)}"
        league_raw = stem0[:m.start()].strip("_- ") or "Repositorio"
    else:
        season = "Sin temporada"
        league_raw = "Repositorio"
    return _humanize_league(league_raw), season, period


def _infer_team(path: Path) -> tuple[str, int]:
    """Infere el equipo focal leyendo solo team/match_id del CSV."""
    header = pd.read_csv(path, nrows=0).columns.tolist()
    team_col = "team_name" if "team_name" in header else "team" if "team" in header else None
    match_col = "match_id" if "match_id" in header else None
    if not team_col or not match_col:
        return "Equipo no identificado", 0
    d = pd.read_csv(path, usecols=[team_col, match_col], low_memory=False)
    d = d.dropna(subset=[team_col, match_col])
    if d.empty:
        return "Equipo no identificado", 0
    cov = d.groupby(team_col)[match_col].nunique().sort_values(ascending=False)
    return str(cov.index[0]), int(cov.iloc[0])


def load_team_metadata(path: Path | str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _metadata_for(meta: dict, league: str, season: str, team: str) -> dict:
    # Estructura preferida: equipos -> "Liga MX|2025-2026|América" -> {...}
    key = f"{league}|{season}|{team}"
    return dict((meta.get("equipos") or {}).get(key, {}) or {})


def scan_catalog(data_root: Path | str, metadata_path: Path | str | None = None) -> pd.DataFrame:
    root = Path(data_root)
    meta = load_team_metadata(metadata_path)
    rows = []
    for p in sorted(root.rglob("*.csv")) if root.exists() else []:
        league, season, period = _parse_filename(p)
        try:
            team, matches = _infer_team(p)
        except Exception:
            team, matches = "Equipo no identificado", 0
        md = _metadata_for(meta, league, season, team)
        rows.append({
            "league": league,
            "season": season,
            "team": team,
            "period": period,
            "period_label": PERIOD_LABELS.get(period, "Archivo completo"),
            "path": str(p),
            "matches": matches,
            "coach": md.get("coach"),
            "coach_source": md.get("coach_source"),
            "competition_note": md.get("competition_note"),
        })
    return pd.DataFrame(rows)


def period_options(catalog: pd.DataFrame, league: str, season: str, team: str) -> list[str]:
    d = catalog[(catalog["league"] == league) & (catalog["season"] == season) & (catalog["team"] == team)]
    labels = [PERIOD_LABELS[p] for p in ("p1", "p2") if (d["period"] == p).any()]
    if len(labels) >= 2:
        return [ALL_PERIODS] + labels
    if labels:
        return labels
    return ["Archivo completo"] if len(d) else []


def paths_for_selection(catalog: pd.DataFrame, league: str, season: str, team: str, period_label: str) -> list[Path]:
    d = catalog[(catalog["league"] == league) & (catalog["season"] == season) & (catalog["team"] == team)]
    if period_label == ALL_PERIODS:
        d = d[d["period"].isin(["p1", "p2", "full"])]
    elif period_label == "Archivo completo":
        d = d[d["period"] == "full"]
    else:
        inv = {v: k for k, v in PERIOD_LABELS.items()}
        d = d[d["period"] == inv.get(period_label, period_label)]
    return [Path(x) for x in d["path"].tolist()]


def context_for_selection(catalog: pd.DataFrame, league: str, season: str, team: str, period_label: str) -> dict:
    d = catalog[(catalog["league"] == league) & (catalog["season"] == season) & (catalog["team"] == team)]
    coach = next((x for x in d.get("coach", pd.Series(dtype=object)).dropna().astype(str) if x.strip()), None)
    coach_source = next((x for x in d.get("coach_source", pd.Series(dtype=object)).dropna().astype(str) if x.strip()), None)
    return {
        "league": league,
        "season": season,
        "team": team,
        "period": period_label,
        "coach": coach,
        "coach_source": coach_source,
        "files": [Path(x).name for x in paths_for_selection(catalog, league, season, team, period_label)],
    }
