"""EFOS Corner Sequence Engine v0.1: P0 execution -> P1 event proxy -> P2 result.
Descriptive evidence, not XGBoost/SHAP, causality, video or confirmed ball contact.
StatsBomb coordinates are 120x80 units; 360 frames are partial snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CornerConfig:
    shot_window_seconds: float = 10.0
    p1_window_seconds: float = 6.0
    short_delivery_max_units: float = 15.0
    box_min_x: float = 102.0
    box_min_y: float = 18.0
    box_max_y: float = 62.0
    near_post_cut_y: float = 36.0
    far_post_cut_y: float = 44.0
    high_threat_shot_xg: float = 0.10
    min_zone_examples: int = 5


INTERVENTION_EVENTS = frozenset({
    "Ball Receipt*", "Pass", "Shot", "Carry", "Carries", "Dribble",
    "Duel", "Clearance", "Interception", "Ball Recovery", "Miscontrol",
    "Dispossessed", "Goal Keeper", "Block"
})
OUTPUT_COLUMNS = [
    "corner_id", "match_id", "period", "possession", "side", "attacking_team",
    "minute", "t0_seconds", "ejecutor", "recipient_declared", "delivery_type",
    "target_zone", "start_x", "start_y", "end_x", "end_y", "pass_height",
    "p0_pass_completed_or_unspecified", "first_registered_team",
    "first_registered_player", "first_registered_event", "first_event_delay_s",
    "p1_evidence", "p1_team_matches_attacker", "shot_count", "shot_generated",
    "first_shooter", "first_shot_delay_s", "corner_xg", "xg_coverage",
    "max_shot_xg", "high_threat", "goal", "score_state", "obv_p0",
    "has_360_snapshot", "attackers_visible_in_box", "defenders_visible_in_box",
    "data_source", "limitation"
]


def _number(value):
    value = pd.to_numeric(value, errors="coerce")
    return float(value) if pd.notna(value) and math.isfinite(float(value)) else math.nan


def _target_zone(start_x, start_y, end_x, end_y, cfg):
    v = (start_x, start_y, end_x, end_y)
    if not all(math.isfinite(x) for x in v):
        return "Sin trayectoria"
    if math.hypot(end_x - start_x, end_y - start_y) <= cfg.short_delivery_max_units:
        return "Corto"
    if end_x < cfg.box_min_x or not cfg.box_min_y <= end_y <= cfg.box_max_y:
        return "Fuera del área"
    rel_y = end_y if start_y <= 40 else 80 - end_y
    if rel_y < cfg.near_post_cut_y:
        return "Primer palo (proxy)"
    if rel_y <= cfg.far_post_cut_y:
        return "Zona central (proxy)"
    return "Segundo palo (proxy)"


def _visible_box_counts(event_id, frames360, cfg):
    frame = (frames360 or {}).get(str(event_id)) if event_id is not None else None
    if not isinstance(frame, dict) or not isinstance(frame.get("freeze_frame"), list):
        return False, math.nan, math.nan
    attack = defend = 0
    for player in frame["freeze_frame"]:
        if not isinstance(player, dict):
            continue
        pos = player.get("location")
        if not isinstance(pos, list) or len(pos) < 2:
            continue
        x, y = _number(pos[0]), _number(pos[1])
        if math.isfinite(x) and math.isfinite(y) and x >= cfg.box_min_x and cfg.box_min_y <= y <= cfg.box_max_y:
            if player.get("teammate") is True:
                attack += 1
            elif player.get("teammate") is False:
                defend += 1
    return True, attack, defend


def build_corner_sequences(events: pd.DataFrame, focal_team: str,
                           frames360: dict | None = None,
                           config: CornerConfig | None = None) -> pd.DataFrame:
    """One row per identified corner; subsequent shots share match, period and possession.
    A later corner within the same possession truncates the previous corner's window.
    """
    cfg = config or CornerConfig()
    required = {"match_id", "period", "possession", "team", "event_type", "type_name", "timestamp_seconds"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"Corner Engine necesita columnas: {sorted(missing)}")
    e = events.copy().reset_index(drop=True)
    if e.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    e["_source_order"] = np.arange(len(e))
    e["_time"] = pd.to_numeric(e["timestamp_seconds"], errors="coerce")
    e["_idx"] = pd.to_numeric(e["index"], errors="coerce") if "index" in e else e["_source_order"]
    e["_idx"] = e["_idx"].fillna(e["_source_order"])
    e["_match"] = e["match_id"].astype(str)
    e["_period"] = pd.to_numeric(e["period"], errors="coerce").fillna(-1)
    e["_poss"] = pd.to_numeric(e["possession"], errors="coerce").fillna(-1)
    e = e.sort_values(["_match", "_period", "_time", "_idx", "_source_order"], kind="stable")
    e["_seq"] = e.groupby(["_match", "_period", "_poss"], sort=False).cumcount()
    groups = {k: g for k, g in e.groupby(["_match", "_period", "_poss"], sort=False)}
    match_teams = {m: set(g["team"].dropna()) for m, g in e.groupby("_match", sort=False)}
    mask = (e["event_type"].eq("Pass") & e["type_name"].eq("Corner") &
            e["_time"].notna() & e["_period"].ne(-1) & e["_poss"].ne(-1))
    rows = []
    for _, anchor in e[mask].iterrows():
        if focal_team not in match_teams.get(anchor["_match"], set()):
            continue
        g = groups[(anchor["_match"], anchor["_period"], anchor["_poss"])]
        t0 = float(anchor["_time"])
        after = g[(g["_seq"] > anchor["_seq"]) & (g["_time"] >= t0)]
        next_corners = after[after["event_type"].eq("Pass") & after["type_name"].eq("Corner")]
        if len(next_corners):
            after = after[after["_seq"] < next_corners.iloc[0]["_seq"]]
        after = after[after["_time"] <= t0 + cfg.shot_window_seconds]
        attacker = str(anchor["team"])
        first_candidates = after[(after["_time"] <= t0 + cfg.p1_window_seconds) &
                                 after["event_type"].isin(INTERVENTION_EVENTS)]
        p1 = first_candidates.iloc[0] if len(first_candidates) else None
        shots = after[after["event_type"].eq("Shot") & after["team"].eq(attacker)]
        nshots = len(shots)
        shot_xg = (pd.to_numeric(shots["statsbomb_xg"], errors="coerce")
                   if "statsbomb_xg" in shots else pd.Series(dtype="float64"))
        if nshots == 0:
            corner_xg, coverage, high_threat, max_xg = 0.0, "NO_SHOT", False, math.nan
        elif len(shot_xg) == nshots and shot_xg.notna().all():
            corner_xg, coverage, max_xg = float(shot_xg.sum()), "COMPLETE", float(shot_xg.max())
            high_threat = bool(max_xg >= cfg.high_threat_shot_xg)
        else:
            corner_xg, coverage, high_threat, max_xg = math.nan, "MISSING_SHOT_XG", None, math.nan
        first_shot = shots.iloc[0] if nshots else None
        if nshots and "shot_outcome" in shots:
            goal = bool(shots["shot_outcome"].eq("Goal").any())
        elif nshots and "outcome_name" in shots:
            goal = bool(shots["outcome_name"].eq("Goal").any())
        else:
            goal = False
        coords = [_number(anchor.get(c)) for c in
                  ("location_x", "location_y", "end_location_x", "end_location_y")]
        zone = _target_zone(*coords, cfg)
        event_id = anchor.get("event_id", None)
        if event_id is None or pd.isna(event_id):
            event_id = f"{anchor['_match']}_{int(anchor['_source_order'])}"
        has_360, attack_visible, defend_visible = _visible_box_counts(anchor.get("event_id"), frames360, cfg)
        rows.append({
            "corner_id": str(event_id), "match_id": anchor["match_id"],
            "period": anchor["period"], "possession": anchor["possession"],
            "side": "A favor" if attacker == focal_team else "En contra",
            "attacking_team": attacker, "minute": _number(anchor.get("minute")),
            "t0_seconds": t0, "ejecutor": anchor.get("player"),
            "recipient_declared": anchor.get("pass_recipient_name"),
            "delivery_type": "Corto" if zone == "Corto" else "Envío",
            "target_zone": zone, "start_x": coords[0], "start_y": coords[1],
            "end_x": coords[2], "end_y": coords[3],
            "pass_height": anchor.get("pass_height_name"),
            "p0_pass_completed_or_unspecified": pd.isna(anchor.get("pass_outcome")),
            "first_registered_team": p1["team"] if p1 is not None else None,
            "first_registered_player": p1.get("player") if p1 is not None else None,
            "first_registered_event": p1["event_type"] if p1 is not None else None,
            "first_event_delay_s": float(p1["_time"] - t0) if p1 is not None else math.nan,
            "p1_evidence": "EVENT_SEQUENCE_PROXY" if p1 is not None else "NOT_OBSERVED",
            "p1_team_matches_attacker": bool(p1["team"] == attacker) if p1 is not None else None,
            "shot_count": nshots, "shot_generated": bool(nshots),
            "first_shooter": first_shot.get("player") if first_shot is not None else None,
            "first_shot_delay_s": float(first_shot["_time"] - t0) if first_shot is not None else math.nan,
            "corner_xg": corner_xg, "xg_coverage": coverage, "max_shot_xg": max_xg,
            "high_threat": high_threat, "goal": goal,
            "score_state": anchor.get("score_state"),
            "obv_p0": _number(anchor.get("obv_total_net")),
            "has_360_snapshot": has_360, "attackers_visible_in_box": attack_visible,
            "defenders_visible_in_box": defend_visible,
            "data_source": "STATSBOMB_EVENTS+360_SNAPSHOT" if has_360 else "STATSBOMB_EVENTS",
            "limitation": ("P1 es primera intervención registrada, no contacto físico confirmado; "
                           "xG suma valor de remates sin ser probabilidad de gol del córner.")
        })
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def summarize_corners(corners: pd.DataFrame, cfg: CornerConfig | None = None) -> dict:
    cfg = cfg or CornerConfig()
    summary = {
        "method": "EFOS_CORNER_SEQUENCE_v0.1", "units": "StatsBomb 120x80",
        "shot_window_s": cfg.shot_window_seconds,
        "first_intervention_window_s": cfg.p1_window_seconds,
        "high_threat_xg_threshold_exploratory": cfg.high_threat_shot_xg,
        "sides": {},
        "limitations": [
            "P1 es un proxy de eventos, no primer contacto físico confirmado.",
            "360 es una instantánea parcial, no tracking ni marcaje demostrado.",
            "Los umbrales de zona y high-threat son heurísticos.",
            "Segundas jugadas fuera de la ventana temporal no se atribuyen.",
            "La suma del xG por córner no es una probabilidad de gol del córner."
        ]
    }
    for side in ("A favor", "En contra"):
        d = corners[corners["side"].eq(side)] if len(corners) else corners
        n = len(d)
        if not n:
            summary["sides"][side] = {"n_corners": 0, "n_matches": 0, "data_status": "INSUFFICIENT"}
            continue
        covered = d[d["xg_coverage"].isin(["COMPLETE", "NO_SHOT"])]
        zones = d["target_zone"].value_counts()
        zone = str(zones.index[0]) if len(zones) and int(zones.iloc[0]) >= cfg.min_zone_examples else None
        p1 = d[d["p1_evidence"].eq("EVENT_SEQUENCE_PROXY")]
        summary["sides"][side] = {
            "n_corners": n, "n_matches": int(d["match_id"].nunique()),
            "shot_rate_pct": round(100 * float(d["shot_generated"].mean()), 2),
            "goals": int(d["goal"].sum()),
            "xg_total_covered": round(float(covered["corner_xg"].sum()), 4),
            "xg_per_corner_covered": round(float(covered["corner_xg"].mean()), 4) if len(covered) else None,
            "xg_coverage_pct": round(100 * len(covered) / n, 2),
            "high_threat_rate_pct_covered": round(100 * float(covered["high_threat"].mean()), 2) if len(covered) else None,
            "p1_registered_pct": round(100 * len(p1) / n, 2),
            "p1_attacker_action_pct_observed": (
                round(100 * float(p1["p1_team_matches_attacker"].mean()), 2) if len(p1) else None),
            "most_common_target_zone": zone,
            "target_zone_distribution": {str(k): int(v) for k, v in zones.items()},
            "sample_label": "EXPLORATORY_SMALL_SAMPLE" if n < 30 else "DESCRIPTIVE_INTERNAL",
            "n_360_snapshots": int(d["has_360_snapshot"].sum())
        }
    return summary


def build_corner_evidence(summary: dict, focal_team: str) -> list[dict]:
    claims = []
    for side, data in summary["sides"].items():
        n = data.get("n_corners", 0)
        if n == 0:
            continue
        zone = data.get("most_common_target_zone") or "sin zona suficientemente repetida"
        value = data.get("xg_per_corner_covered")
        xg_text = f"{value:.3f} xG por córner cubierto" if value is not None else "xG no disponible"
        claims.append({
            "id": "corner_sequence_for" if side == "A favor" else "corner_sequence_against",
            "section": "set_piece_identity",
            "claim": (f"{focal_team}: {side.lower()}, {n} córners; "
                      f"{data['shot_rate_pct']:.1f}% acabaron en remate dentro de 10 s; "
                      f"{xg_text}. Zona más frecuente: {zone}."),
            "evidence": data, "n": n, "source": "CORNER_EVENT_SEQUENCE",
            "confidence": "LOW" if n < 30 else "MEDIUM",
            "limitation": ("Descriptivo y dependiente de cobertura; P1 proxy de intervención registrada. "
                           "No identifica causalidad, contacto confirmado ni intención del entrenador.")
        })
    return claims


def analyze_corners(events: pd.DataFrame, focal_team: str,
                    frames360: dict | None = None,
                    config: CornerConfig | None = None):
    cfg = config or CornerConfig()
    detail = build_corner_sequences(events, focal_team, frames360, cfg)
    summary = summarize_corners(detail, cfg)
    claims = build_corner_evidence(summary, focal_team)
    return detail, summary, claims
