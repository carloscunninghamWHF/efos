"""Team selection utilities for team-agnostic EFOS execution."""
from __future__ import annotations
import re
import unicodedata
import pandas as pd


def team_coverage(events: pd.DataFrame) -> pd.DataFrame:
    if "team" not in events.columns or "match_id" not in events.columns:
        raise ValueError("EFOS necesita columnas 'team' y 'match_id' para determinar el alcance por equipo.")
    total_matches = max(int(events["match_id"].nunique()), 1)
    rows = []
    for team, g in events.dropna(subset=["team"]).groupby("team"):
        nm = int(g["match_id"].nunique())
        rows.append({
            "team": str(team),
            "matches": nm,
            "match_coverage": nm / total_matches,
            "events": int(len(g)),
            "event_share": len(g) / max(len(events), 1),
        })
    return pd.DataFrame(rows).sort_values(["matches", "events", "team"], ascending=[False, False, True]).reset_index(drop=True)


def resolve_focal_team(events: pd.DataFrame, requested: str | None = None) -> tuple[str, dict]:
    cov = team_coverage(events)
    teams = cov["team"].tolist()
    if requested and str(requested).strip().lower() not in {"auto", "none"}:
        if requested not in teams:
            raise ValueError(f"El equipo '{requested}' no aparece en los datos. Equipos disponibles: {teams}")
        row = cov[cov.team.eq(requested)].iloc[0]
        return requested, {"mode": "explicit", "team": requested, "coverage": float(row.match_coverage), "matches": int(row.matches)}

    full = cov[cov.match_coverage.eq(1.0)]
    if len(full) == 1:
        row = full.iloc[0]
        return str(row.team), {"mode": "auto_full_coverage", "team": str(row.team), "coverage": 1.0, "matches": int(row.matches)}

    # For multi-match team-centric exports, the focal team normally has clearly
    # higher match coverage than every opponent even if one match is incomplete.
    if len(cov) >= 2 and int(cov.iloc[0].matches) >= 2:
        top, second = cov.iloc[0], cov.iloc[1]
        if float(top.match_coverage) >= 0.80 and int(top.matches) > int(second.matches):
            return str(top.team), {"mode": "auto_dominant_coverage", "team": str(top.team), "coverage": float(top.match_coverage), "matches": int(top.matches)}

    raise ValueError(
        "No se puede inferir de forma segura un único equipo focal. "
        f"Cobertura detectada: {cov[['team','matches','match_coverage']].to_dict('records')}. "
        "Use --team 'Nombre exacto' o --all-teams."
    )


def slugify_team(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text or "team"
