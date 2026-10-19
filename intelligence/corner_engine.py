"""EFOS — Corner Sequence Engine v0.1 (P0 -> P1 proxy -> P2).

Análisis descriptivo y auditable, SIN modelos predictivos ni SHAP.
Unidad de análisis: un saque de esquina de StatsBomb (Pass con type_name='Corner').

P0 = ejecución observada, trayectoria y zona de envío.
P1 = primera *intervención registrada* en los eventos posteriores (NO es el
     primer contacto físico confirmado, ni garantiza quién ganó el duelo).
P2 = remates y xG generados en la misma posesión en una ventana temporal.

La geometría utiliza unidades StatsBomb (campo 120x80); NO son metros.
Los freeze-frames 360 son instantáneas parciales, nunca tracking continuo.
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
    high_threat_shot_xg: float = 0.10  # umbral heurístico para seleccionar vídeo, NO benchmark
    min_zone_examples: int = 5


# Un evento de disputa/intervención registrado no garantiza un contacto físico real.
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


def _target_zone(start_x, start_y, end_x, end_y, cfg: CornerConfig) -> tuple[str, str]:
    vals = [start_x, start_y, end_x, end_y]
    if not all(math.isfinite(x) for x in vals):
        return "Sin trayectoria", "UNKNOWN"
    distance = math.hypot(end_x-start_x, end_y-start_y)
    if distance <= cfg.short_delivery_max_units:
        return "Corto", "SHORT_DELIVERY_PROXY"
    if end_x < cfg.box_min_x or not cfg.box_min_y <= end_y <= cfg.box_max_y:
        return "Fuera del área", "EVENT_GEOMETRY_PROXY"
    # Invertimos el eje lateral cuando se cobra desde y~80 para definir
    # primer/segundo palo desde el lado del ejecutor. Corte HEURÍSTICO.
    relative_y = end_y if start_y <= 40 else 80-end_y
    if relative_y < cfg.near_post_cut_y:
        return "Primer palo (proxy)", "EVENT_GEOMETRY_PROXY"
    if relative_y <= cfg.far_post_cut_y:
        return "Zona central (proxy)", "EVENT_GEOMETRY_PROXY"
    return "Segundo palo (proxy)", "EVENT_GEOMETRY_PROXY"


def _visible_box_counts(event_id, frames360, cfg: CornerConfig):
    frame = (frames360 or {}).get(str(event_id)) if event_id is not None else None
    if not isinstance(frame, dict) or not isinstance(frame.get("freeze_frame"), list):
        return False, math.nan, math.nan
    atacantes = defensores = 0
    for player in frame["freeze_frame"]:
        if not isinstance(player, dict):
            continue
        pos = player.get("location")
        if not isinstance(pos, list) or len(pos) < 2:
            continue
        x, y = _number(pos[0]), _number(pos[1])
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        if x >= cfg.box_min_x and cfg.box_min_y <= y <= cfg.box_max_y:
            if player.get("teammate") is True:
                atacantes += 1
            elif player.get("teammate") is False:
                defensores += 1
    return True, atacantes, defensores


def build_corner_sequences(events: pd.DataFrame, focal_team: str,
                           frames360: dict | None = None,
                           config: CornerConfig | None = None) -> pd.DataFrame:
    """Retorna una fila por córner a favor o en contra del equipo focal.

    Requiere identificación de partido, periodo, posesión y tiempos válidos.
    No une eventos de distintos partidos/periodos/posesiones.
    """
    cfg = config or CornerConfig()
    needed = {"match_id", "period", "possession", "team", "event_type", "type_name", "timestamp_seconds"}
    missing = needed.difference(events.columns)
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
    groups = {key: group for key, group in e.groupby(["_match", "_period", "_poss"], sort=False)}
    participating_teams = {m: set(g["team"].dropna()) for m, g in e.groupby("_match", sort=False)}
    corner_mask = (e["event_type"].eq("Pass") & e["type_name"].eq("Corner") & e["_time"].notna()
                   & e["_period"].ne(-1) & e["_poss"].ne(-1))
    corners = e[corner_mask]
    rows = []
    for _, anchor in corners.iterrows():
        key = (anchor["_match"], anchor["_period"], anchor["_poss"])
        g = groups[key]
        t0 = float(anchor["_time"])
        # Dos ejecuciones dentro de una misma posesión NO comparten remates:
        # cada ventana se trunca antes del siguiente córner.
        later = g[(g["_seq"] > anchor["_seq"]) & (g["_time"] >= t0)]
        next_corner = later[(later["event_type"].eq("Pass")) & later["type_name"].eq("Corner")]
        if len(next_corner):
            later = later[later["_seq"] < next_corner.iloc[0]["_seq"]]
        later = later[later["_time"] <= t0+cfg.shot_window_seconds]
        attacker = str(anchor["team"])
        side = "A favor" if attacker == focal_team else "En contra"
        # Evita incluir córners de terceros o de partidos no disputados por el focal.
        if focal_team not in participating_teams[anchor["_match"]]:
            continue

        first_events = later[(later["_time"] <= t0+cfg.p1_window_seconds) &
                             later["event_type"].isin(INTERVENTION_EVENTS)]
        p1 = first_events.iloc[0] if len(first_events) else None
        shots = later[later["event_type"].eq("Shot") & later["team"].eq(attacker)]
        nshots = len(shots)
        xg = (pd.to_numeric(shots["statsbomb_xg"], errors="coerce")
              if "statsbomb_xg" in shots else pd.Series(dtype="float64"))
        if nshots == 0:
            corner_xg, xg_coverage, high_threat, max_xg = 0.0, "NO_SHOT", False, math.nan
        elif len(xg) == nshots and xg.notna().all():
            corner_xg, xg_coverage = float(xg.sum()), "COMPLETE"
            max_xg = float(xg.max())
            high_threat = bool(max_xg >= cfg.high_threat_shot_xg)
        else:
            corner_xg, xg_coverage, high_threat, max_xg = math.nan, "MISSING_SHOT_XG", None, math.nan
        first_shot = shots.iloc[0] if nshots else None
        if nshots and "shot_outcome" in shots:
            goal = bool(shots["shot_outcome"].eq("Goal").any())
        elif nshots and "outcome_name" in shots:
            goal = bool(shots["outcome_name"].eq("Goal").any())
        else:
            goal = False
        zone, _ = _target_zone(*[_number(anchor.get(c)) for c in
                                ("location_x", "location_y", "end_location_x", "end_location_y")], cfg)
        eid = anchor.get("event_id", None)
        if eid is None or pd.isna(eid):
            eid = f"{anchor['_match']}_{int(anchor['_source_order'])}"
        has360, a360, d360 = _visible_box_counts(anchor.get("event_id"), frames360, cfg)
        rows.append({
            "corner_id": str(eid), "match_id": anchor["match_id"],
            "period": anchor["period"], "possession": anchor["possession"],
            "side": side, "attacking_team": attacker,
            "minute": _number(anchor.get("minute")), "t0_seconds": t0,
            "ejecutor": anchor.get("player"),
            "recipient_declared": anchor.get("pass_recipient_name"),
            "delivery_type": "Corto" if zone == "Corto" else "Envío",
            "target_zone": zone,
            "start_x": _number(anchor.get("location_x")),
            "start_y": _number(anchor.get("location_y")),
            "end_x": _number(anchor.get("end_location_x")),
            "end_y": _number(anchor.get("end_location_y")),
            "pass_height": anchor.get("pass_height_name"),
            "p0_pass_completed_or_unspecified": pd.isna(anchor.get("pass_outcome")),
            "first_registered_team": p1["team"] if p1 is not None else None,
            "first_registered_player": p1.get("player") if p1 is not None else None,
            "first_registered_event": p1["event_type"] if p1 is not None else None,
            "first_event_delay_s": float(p1["_time"]-t0) if p1 is not None else math.nan,
            "p1_evidence": "EVENT_SEQUENCE_PROXY" if p1 is not None else "NOT_OBSERVED",
            "p1_team_matches_attacker": bool(p1["team"]==attacker) if p1 is not None else None,
            "shot_count": nshots, "shot_generated": bool(nshots),
            "first_shooter": first_shot.get("player") if first_shot is not None else None,
            "first_shot_delay_s": float(first_shot["_time"]-t0) if first_shot is not None else math.nan,
            "corner_xg": corner_xg, "xg_coverage": xg_coverage,
            "max_shot_xg": max_xg, "high_threat": high_threat, "goal": goal,
            "score_state": anchor.get("score_state"),
            "obv_p0": _number(anchor.get("obv_total_net")),
            "has_360_snapshot": has360, "attackers_visible_in_box": a360,
            "defenders_visible_in_box": d360,
            "data_source": "STATSBOMB_EVENTS+360_SNAPSHOT" if has360 else "STATSBOMB_EVENTS",
            "limitation": "P1 aproxima primera intervención registrada, NO primer contacto confirmado;"
                          " xG es suma descriptiva, no probabilidad calibrada de gol del córner."
        })
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def summarize_corners(corners: pd.DataFrame, cfg: CornerConfig | None = None) -> dict:
    """Firma táctica de córners sin pesos arbitrarios ni inferencia causal."""
    cfg = cfg or CornerConfig()
    summary = {"method": "EFOS_CORNER_SEQUENCE_v0.1", "units": "StatsBomb 120x80",
               "shot_window_s": cfg.shot_window_seconds, "first_intervention_window_s": cfg.p1_window_seconds,
               "high_threat_xg_threshold_exploratory": cfg.high_threat_shot_xg,
               "sides": {}, "limitations": [
                   "P1 no confirma primer contacto físico ni ganador del duelo aéreo.",
                   "El 360 es un snapshot de jugadores visibles, no tracking o marcaje validado.",
                   "Zona y high-threat son umbrales metodológicos, no verdades universales.",
                   "Cada remate se atribuye por misma posesión y ventana de 10 s; pueden existir segundas jugadas más tardías.",
                   "La suma de xG por córner no es probabilidad de marcar al menos un gol.",
               ]}
    for side in ("A favor", "En contra"):
        d = corners[corners["side"].eq(side)] if len(corners) else corners
        n = len(d)
        if not n:
            summary["sides"][side] = {"n_corners": 0, "n_matches": 0, "data_status": "INSUFFICIENT"}
            continue
        valid_xg = d[d["xg_coverage"].isin(["COMPLETE", "NO_SHOT"])]
        zones = d["target_zone"].value_counts()
        zone = str(zones.index[0]) if len(zones) and int(zones.iloc[0]) >= cfg.min_zone_examples else None
        with_intervention = d[d["p1_evidence"].eq("EVENT_SEQUENCE_PROXY")]
        z = {
            "n_corners": n, "n_matches": int(d["match_id"].nunique()),
            "shot_rate_pct": round(100*float(d["shot_generated"].mean()), 2),
            "goals": int(d["goal"].sum()),
            "xg_total_covered": round(float(valid_xg["corner_xg"].sum()), 4),
            "xg_per_corner_covered": round(float(valid_xg["corner_xg"].mean()), 4) if len(valid_xg) else None,
            "xg_coverage_pct": round(100*len(valid_xg)/n, 2),
            "high_threat_rate_pct_covered": round(100*float(valid_xg["high_threat"].mean()), 2) if len(valid_xg) else None,
            "p1_registered_pct": round(100*len(with_intervention)/n, 2),
            "p1_attacker_action_pct_observed": round(100*float(with_intervention["p1_team_matches_attacker"].mean()), 2) if len(with_intervention) else None,
            "most_common_target_zone": zone,
            "target_zone_distribution": {str(k): int(v) for k,v in zones.items()},
            "sample_label": "EXPLORATORY_SMALL_SAMPLE" if n < 30 else "DESCRIPTIVE_INTERNAL",
            "n_360_snapshots": int(d["has_360_snapshot"].sum()),
        }
        summary["sides"][side] = z
    return summary


def build_corner_evidence(summary: dict, focal_team: str) -> list[dict]:
    """Claims compatibles con interpretation/evidence.py; sin atribuir intención al DT."""
    claims=[]
    for side, z in summary["sides"].items():
        n=z.get("n_corners",0)
        if not n:
            continue
        zone=z.get("most_common_target_zone") or "ninguna zona suficientemente repetida"
        xg=z.get("xg_per_corner_covered")
        value=f"{xg:.3f} xG/córner con cobertura válida" if xg is not None else "xG no disponible"
        claim=(f"{focal_team}: {side.lower()}, {n} córners; "
               f"{z['shot_rate_pct']:.1f}% terminaron en remate del equipo ejecutor dentro de 10 s; "
               f"{value}. Zona objetivo más frecuente: {zone}.")
        claims.append({"id": "corner_sequence_for" if side=="A favor" else "corner_sequence_against",
                       "section": "set_piece_identity", "claim": claim,
                       "evidence": z, "n": n, "source": "CORNER_EVENT_SEQUENCE",
                       "confidence": "LOW" if n<30 else "MEDIUM",
                       "limitation": "Evidencia descriptiva condicionada por la muestra. P1 es intervención registrada proxy,"
                                     " no primer contacto confirmado; sin inferencia causal ni atribución de intención del DT."})
    return claims


def analyze_corners(events: pd.DataFrame, focal_team: str,
                    frames360: dict | None = None,
                    config: CornerConfig | None = None):
    """Return (detail DataFrame, summary dict, evidence claims list)."""
    cfg = config or CornerConfig()
    detail = build_corner_sequences(events, focal_team, frames360, cfg)
    summary = summarize_corners(detail, cfg)
    evidence = build_corner_evidence(summary, focal_team)
    return detail, summary, evidence
