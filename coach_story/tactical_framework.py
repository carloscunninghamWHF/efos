"""Video-derived tactical framework for EFOS Coach Story.

This module translates a set of tactical concepts into auditable StatsBomb event
proxies.  It deliberately distinguishes direct observations (EVENT) from tactical
proxies (EVENT_PROXY).  It never treats event locations as full tracking data.

Concept families incorporated from the user's video synthesis:
- defensive height / counterpress / offside-line outcomes / passer pressure
- pressure attraction ("fishing"), third-man progression and half-space occupation
- cross-to-danger-zone ("Aliup" proxy) and centre-back/full-back interval attacks
- xG / OBV value layer
- a weekly planning hypothesis template (not a physical-load prescription)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from config_loader import get_thresholds


PASS_FAILURES = {
    "Incomplete", "Out", "Unknown", "Pass Offside", "Injury Clearance",
}
PASS_SUCCESSES = {"Complete", "Success", "Won", "Success In Play", "Success Out"}
DEFENSIVE_ACTION_TYPES = {
    "Pressure", "Ball Recovery", "Interception", "Clearance", "Foul Committed",
}


def _num(s: pd.Series | Any, index=None, default=np.nan) -> pd.Series:
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce")
    return pd.Series(default, index=index, dtype=float)


def _bool(s: pd.Series | Any, index=None) -> pd.Series:
    if not isinstance(s, pd.Series):
        return pd.Series(False, index=index, dtype=bool)
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False)
    text = s.astype(str).str.strip().str.lower()
    return text.isin({"true", "1", "yes", "y", "t"})


def _safe_count(mask: pd.Series) -> int:
    return int(mask.fillna(False).sum())


def _rate(num: float, den: float) -> float | None:
    return float(num / den) if den else None


def _round(v: Any, n: int = 3):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return round(float(v), n)


def _pass_success(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(False, index=df.index, dtype=bool)
    outcome = df.get("outcome_name", pd.Series(pd.NA, index=df.index)).astype("string")
    # StatsBomb event data convention: a successful pass is commonly null outcome.
    return outcome.isna() | outcome.isin(PASS_SUCCESSES)


def _deduplicate_events(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    raw = df.copy()
    before = len(raw)
    if "event_id" in raw.columns and raw["event_id"].notna().any():
        with_id = raw[raw["event_id"].notna()].drop_duplicates("event_id", keep="first")
        without_id = raw[raw["event_id"].isna()]
        out = pd.concat([with_id, without_id], ignore_index=True, sort=False)
        key = "event_id"
    elif "id" in raw.columns and raw["id"].notna().any():
        with_id = raw[raw["id"].notna()].drop_duplicates("id", keep="first")
        without_id = raw[raw["id"].isna()]
        out = pd.concat([with_id, without_id], ignore_index=True, sort=False)
        key = "id"
    elif {"match_id", "index"}.issubset(raw.columns):
        out = raw.drop_duplicates(["match_id", "index"], keep="first").copy()
        key = "match_id+index"
    else:
        out = raw.drop_duplicates().copy()
        key = "full_row"
    return out, {
        "rows_before": int(before),
        "rows_after": int(len(out)),
        "duplicates_removed": int(before - len(out)),
        "dedupe_key": key,
    }


def _match_rate(mask: pd.Series, df: pd.DataFrame, matches: int) -> float:
    return float(mask.fillna(False).sum() / max(matches, 1))


def _coverage(series: pd.Series) -> float:
    return float(series.notna().mean()) if len(series) else 0.0


def _future_progression_release(team_events: pd.DataFrame, candidate_index: pd.Index, cfg: dict) -> pd.Series:
    """Whether a pressure-attraction pass is followed by forward release.

    Uses the next N same-team on-ball events in the same possession and an optional
    time horizon. This is a sequence proxy, not proof that pressure was intentionally
    attracted.
    """
    if team_events.empty or not len(candidate_index):
        return pd.Series(False, index=candidate_index, dtype=bool)

    horizon_events = int(cfg.get("pressure_release_next_events", 3))
    horizon_seconds = float(cfg.get("pressure_release_seconds", 8.0))
    min_gain = float(cfg.get("pressure_release_min_x_gain", 10.0))
    final_third_x = float(cfg.get("final_third_x", 80.0))

    work = team_events.copy()
    work["_x"] = _num(work.get("location_x"), work.index)
    ex = _num(work.get("end_location_x"), work.index)
    work["_event_reach_x"] = pd.concat([work["_x"], ex], axis=1).max(axis=1, skipna=True)
    work["_t"] = _num(work.get("timestamp_seconds"), work.index)
    work["_order"] = _num(work.get("index"), work.index)
    sort_cols = [c for c in ["match_id", "possession", "_order", "_t"] if c in work.columns]
    work = work.sort_values(sort_cols, kind="stable")

    future_best = pd.Series(np.nan, index=work.index, dtype=float)
    for k in range(1, horizon_events + 1):
        same_match = work["match_id"].eq(work["match_id"].shift(-k)) if "match_id" in work else pd.Series(True, index=work.index)
        same_poss = work["possession"].eq(work["possession"].shift(-k)) if "possession" in work else pd.Series(True, index=work.index)
        valid = same_match & same_poss
        if "timestamp_seconds" in work:
            dt = work["_t"].shift(-k) - work["_t"]
            valid &= dt.ge(0) & dt.le(horizon_seconds)
        candidate_reach = work["_event_reach_x"].shift(-k).where(valid)
        future_best = pd.concat([future_best, candidate_reach], axis=1).max(axis=1, skipna=True)

    start = ex.reindex(work.index).fillna(work["_x"])
    released = future_best.ge(start + min_gain) | future_best.ge(final_third_x)
    return released.reindex(candidate_index).fillna(False)


def _third_man_proxy(passes: pd.DataFrame, cfg: dict) -> pd.Series:
    """Detect A->B->C progressive pass chains as a third-man *proxy*.

    Requires pass recipient names and event player names. It cannot infer off-ball
    intention, decoy movement or whether C was literally the tactical third man.
    """
    if passes.empty or not {"player", "pass_recipient_name"}.issubset(passes.columns):
        return pd.Series(False, index=passes.index, dtype=bool)
    p = passes.copy()
    p["_success"] = _pass_success(p)
    p["_t"] = _num(p.get("timestamp_seconds"), p.index)
    p["_order"] = _num(p.get("index"), p.index)
    p["_start_x"] = _num(p.get("location_x"), p.index)
    p["_end_x"] = _num(p.get("end_location_x"), p.index)
    sort_cols = [c for c in ["match_id", "possession", "_order", "_t"] if c in p.columns]
    p = p.sort_values(sort_cols, kind="stable")

    nxt = p.shift(-1)
    same_match = p["match_id"].eq(nxt["match_id"]) if "match_id" in p else True
    same_poss = p["possession"].eq(nxt["possession"]) if "possession" in p else True
    link = p["pass_recipient_name"].astype(str).eq(nxt["player"].astype(str))
    distinct = (
        p["player"].astype(str).ne(p["pass_recipient_name"].astype(str))
        & nxt["pass_recipient_name"].astype(str).ne(p["pass_recipient_name"].astype(str))
        & nxt["pass_recipient_name"].astype(str).ne(p["player"].astype(str))
    )
    max_seconds = float(cfg.get("third_man_max_seconds", 4.0))
    time_ok = (nxt["_t"] - p["_t"]).between(0, max_seconds) if "timestamp_seconds" in p else True
    min_gain = float(cfg.get("third_man_min_x_gain", 15.0))
    min_second_gain = float(cfg.get("third_man_second_pass_min_x_gain", 8.0))
    progressive = nxt["_end_x"].ge(p["_start_x"] + min_gain)
    second_progressive = (nxt["_end_x"] - nxt["_start_x"]).ge(min_second_gain)
    pressure_involved = _bool(p.get("under_pressure"), p.index) | _bool(nxt.get("under_pressure"), nxt.index)
    hit = p["_success"] & nxt["_success"].eq(True) & same_match & same_poss & link & distinct & time_ok & progressive & second_progressive & pressure_involved
    return hit.reindex(passes.index).fillna(False)


def _height_band(mean_x: float | None, cfg: dict) -> str:
    if mean_x is None:
        return "N/A"
    high = float(cfg.get("defensive_height_high_x", 70.0))
    mid = float(cfg.get("defensive_height_mid_x", 50.0))
    if mean_x >= high:
        return "Intervención defensiva alta"
    if mean_x >= mid:
        return "Intervención defensiva media-alta"
    return "Intervención defensiva media/baja"


def _metric(value=None, *, count=None, rate=None, per_match=None, unit=None, source="EVENT", confidence="HIGH", limitation=None, denominator=None, coverage=None) -> dict:
    return {
        "value": _round(value),
        "count": int(count) if count is not None else None,
        "rate": _round(rate),
        "per_match": _round(per_match),
        "unit": unit,
        "source": source,
        "confidence": confidence,
        "limitation": limitation,
        "denominator": int(denominator) if denominator is not None else None,
        "coverage": _round(coverage),
    }


def extract_tactical_framework(events: pd.DataFrame, focal_team: str) -> dict:
    """Extract a coach-facing tactical framework from canonical EFOS events."""
    df, dq = _deduplicate_events(events)
    if "team" not in df.columns or "event_type" not in df.columns:
        raise ValueError("Tactical framework requires canonical EFOS columns 'team' and 'event_type'.")

    cfg = get_thresholds().get("tactical_framework", {})
    team = df[df["team"].eq(focal_team)].copy()
    opp = df[df["team"].notna() & df["team"].ne(focal_team)].copy()
    matches = max(int(team["match_id"].nunique()) if "match_id" in team else 1, 1)

    # ------------------------------------------------------------------
    # I. Defensive dimension
    # ------------------------------------------------------------------
    def_actions = team[team["event_type"].isin(DEFENSIVE_ACTION_TYPES)].copy()
    def_x = _num(def_actions.get("location_x"), def_actions.index)
    mean_def_x = float(def_x.mean()) if def_x.notna().any() else None

    cp_mask = _bool(team.get("counterpress"), team.index)
    cp_count = _safe_count(cp_mask)
    cp_eligible = team["event_type"].isin({"Pressure", "Dribbled Past", "50/50", "Duel", "Block", "Interception", "Foul Committed"})
    cp_rate = _rate(cp_count, _safe_count(cp_eligible))

    opp_outcome = opp.get("outcome_name", pd.Series(pd.NA, index=opp.index)).astype("string")
    opp_offside = opp_outcome.eq("Pass Offside") | opp["event_type"].astype(str).eq("Offside")
    opp_passes = opp[opp["event_type"].eq("Pass")].copy()
    opp_pass_pressure = _bool(opp_passes.get("under_pressure"), opp_passes.index)

    pressures = team[team["event_type"].eq("Pressure")].copy()
    pressure_x = _num(pressures.get("location_x"), pressures.index)
    high_press_x = float(cfg.get("high_press_x", 80.0))
    high_press = pressure_x.ge(high_press_x)

    defensive = {
        "defensive_action_height": {
            **_metric(mean_def_x, unit="StatsBomb x (0–120)", source="EVENT", confidence="HIGH",
                      limitation="Altura media de las acciones defensivas; no equivale a la altura geométrica de la línea defensiva sin tracking/360 completo.",
                      denominator=len(def_actions), coverage=_coverage(def_x)),
            "band": _height_band(mean_def_x, cfg),
            "actions": int(len(def_actions)),
        },
        "counterpress": _metric(count=cp_count, rate=cp_rate, per_match=cp_count/matches, source="EVENT", confidence="HIGH",
                                 denominator=_safe_count(cp_eligible),
                                 limitation="StatsBomb marca counterpress en acciones defensivas dentro de 5s de una pérdida en juego abierto; mide acciones, no la calidad del counterpress."),
        "opponent_offside_outcomes": _metric(count=_safe_count(opp_offside), per_match=_safe_count(opp_offside)/matches,
                                              rate=_rate(_safe_count(opp_offside), len(opp_passes)), source="EVENT_PROXY", confidence="MEDIUM",
                                              denominator=len(opp_passes),
                                              limitation="Cuenta pases del rival terminados en offside. Es compatible con una línea/trampa de fuera de juego, pero no prueba que el equipo la haya provocado deliberadamente."),
        "opponent_passes_under_pressure": _metric(count=_safe_count(opp_pass_pressure), rate=_rate(_safe_count(opp_pass_pressure), len(opp_passes)),
                                                    per_match=_safe_count(opp_pass_pressure)/matches, source="EVENT", confidence="HIGH",
                                                    denominator=len(opp_passes),
                                                    limitation="Acciones de pase rivales etiquetadas under_pressure; no identifica por sí sola el mecanismo colectivo de presión."),
        "high_press_share": _metric(count=_safe_count(high_press), rate=_rate(_safe_count(high_press), len(pressures)), per_match=_safe_count(high_press)/matches,
                                     source="EVENT", confidence="HIGH", denominator=len(pressures),
                                     limitation=f"Share de Pressure events con x≥{high_press_x:.0f}; describe localización de presión, no altura de bloque en cada frame."),
    }

    # ------------------------------------------------------------------
    # II. Construction and progression
    # ------------------------------------------------------------------
    passes = team[team["event_type"].eq("Pass")].copy()
    success = _pass_success(passes)
    px = _num(passes.get("location_x"), passes.index)
    pex = _num(passes.get("end_location_x"), passes.index)
    pey = _num(passes.get("end_location_y"), passes.index)
    under = _bool(passes.get("under_pressure"), passes.index)

    build_max_x = float(cfg.get("pressure_attraction_max_x", 80.0))
    attraction = success & under & px.lt(build_max_x)
    team_onball = team[team["event_type"].isin(["Pass", "Carries", "Carry", "Dribble", "Shot", "Ball Receipt*"])].copy()
    released = _future_progression_release(team_onball, passes.index[attraction], cfg)

    hs_x_min = float(cfg.get("halfspace_x_min", 70.0)); hs_x_max = float(cfg.get("halfspace_x_max", 95.0))
    y1a=float(cfg.get("halfspace_y1_min",18.0)); y1b=float(cfg.get("halfspace_y1_max",30.0))
    y2a=float(cfg.get("halfspace_y2_min",50.0)); y2b=float(cfg.get("halfspace_y2_max",62.0))
    halfspace_y = pey.between(y1a,y1b) | pey.between(y2a,y2b)
    halfspace = success & pex.between(hs_x_min,hs_x_max) & halfspace_y

    direct = _num(team.get("possession_directness"), team.index)
    third_man = _third_man_proxy(passes, cfg)

    build = {
        "possession_directness": _metric(float(direct.mean()) if direct.notna().any() else None,
                                          unit="StatsBomb possession_directness", source="EVENT", confidence="HIGH" if direct.notna().mean()>.5 else "MEDIUM",
                                          denominator=int(direct.notna().sum()), coverage=_coverage(direct),
                                          limitation="Media de la variable disponible en el proveedor; debe interpretarse con la definición de StatsBomb del dataset cargado."),
        "pressure_attraction_passes": _metric(count=_safe_count(attraction), per_match=_safe_count(attraction)/matches,
                                                rate=_rate(_safe_count(attraction), _safe_count(success & px.lt(build_max_x))), source="EVENT_PROXY", confidence="MEDIUM",
                                                denominator=_safe_count(success & px.lt(build_max_x)),
                                                limitation="Proxy 'fishing': pase completado bajo presión antes de x=80. No demuestra intención deliberada de atraer rivales."),
        "pressure_release_success": _metric(count=_safe_count(released), rate=_rate(_safe_count(released), len(released)), per_match=_safe_count(released)/matches,
                                             source="SEQUENCE_PROXY", confidence="MEDIUM", denominator=len(released),
                                             limitation="Tras un pase de atracción, busca progresión en los siguientes eventos de la misma posesión; asociación secuencial, no causalidad."),
        "halfspace_entries": _metric(count=_safe_count(halfspace), rate=_rate(_safe_count(halfspace), _safe_count(success)), per_match=_safe_count(halfspace)/matches,
                                     source="EVENT_PROXY", confidence="MEDIUM", denominator=_safe_count(success),
                                     limitation="Pases completados a dos zonas predefinidas de half-space; la geometría es una hipótesis configurable del modelo."),
        "third_man_progression_proxy": _metric(count=_safe_count(third_man), rate=_rate(_safe_count(third_man), _safe_count(success)), per_match=_safe_count(third_man)/matches,
                                                source="SEQUENCE_PROXY", confidence="MEDIUM" if {"player","pass_recipient_name"}.issubset(passes.columns) else "LOW",
                                                denominator=_safe_count(success),
                                                limitation="Detecta cadenas A→B→C progresivas con tres jugadores distintos. No observa movimientos sin balón ni confirma el principio táctico de tercer hombre."),
    }

    # ------------------------------------------------------------------
    # III. Offensive micro-concepts
    # ------------------------------------------------------------------
    cross = _bool(passes.get("pass_cross"), passes.index)
    danger_x = float(cfg.get("cross_target_x_min", 102.0))
    danger_y_min = float(cfg.get("cross_target_y_min",18.0)); danger_y_max=float(cfg.get("cross_target_y_max",62.0))
    aliup_proxy = cross & pex.ge(danger_x) & pey.between(danger_y_min,danger_y_max)
    aliup_complete = aliup_proxy & success

    interval_start_x=float(cfg.get("interval_start_x",60.0)); interval_end_x=float(cfg.get("interval_end_x",88.0))
    interval = success & px.ge(interval_start_x) & pex.ge(interval_end_x) & halfspace_y

    offensive = {
        "cross_to_danger_zone_proxy": _metric(count=_safe_count(aliup_proxy), rate=_rate(_safe_count(aliup_complete), _safe_count(aliup_proxy)), per_match=_safe_count(aliup_proxy)/matches,
                                               source="EVENT_PROXY", confidence="LOW", denominator=_safe_count(aliup_proxy),
                                               limitation="Proxy del concepto 'Aliup': identifica geometría de centro hacia zona peligrosa, pero no rosca, pierna cambiada, segundo palo real ni intención del receptor."),
        "interval_entries": _metric(count=_safe_count(interval), rate=_rate(_safe_count(interval), _safe_count(success)), per_match=_safe_count(interval)/matches,
                                    source="EVENT_PROXY", confidence="MEDIUM", denominator=_safe_count(success),
                                    limitation="Pases completados hacia el intervalo central-lateral aproximado por half-spaces; no observa desmarques sin balón."),
    }

    # ------------------------------------------------------------------
    # IV. Value / purpose layer
    # ------------------------------------------------------------------
    shots = team[team["event_type"].eq("Shot")]
    xg = _num(shots.get("statsbomb_xg"), shots.index)
    obv = _num(team.get("obv_total_net"), team.index)
    value = {
        "xg": {
            "total": _round(xg.sum(min_count=1) if xg.notna().any() else None, 2),
            "per_match": _round(xg.sum(min_count=1)/matches if xg.notna().any() else None, 3),
            "per_shot": _round(xg.mean() if xg.notna().any() else None, 3),
            "shots": int(len(shots)),
            "coverage": _round(_coverage(xg)),
            "source": "EVENT_MODEL",
            "confidence": "HIGH" if xg.notna().any() else "LOW",
            "limitation": "xG evalúa la probabilidad del remate, no la calidad de toda la posesión previa.",
        },
        "obv": {
            "total_net": _round(obv.sum(min_count=1) if obv.notna().any() else None, 3),
            "per_match": _round(obv.sum(min_count=1)/matches if obv.notna().any() else None, 3),
            "per_100_team_events": _round(100*obv.sum(min_count=1)/len(team) if obv.notna().any() and len(team) else None, 3),
            "coverage": _round(_coverage(obv)),
            "source": "EVENT_MODEL",
            "confidence": "HIGH" if obv.notna().any() else "LOW",
            "limitation": "OBV mide cambio de valor esperado asociado a acciones elegibles; no equivale por sí solo a intención táctica.",
        },
    }

    # ------------------------------------------------------------------
    # V. Weekly planning hypotheses (coach-facing, non-prescriptive)
    # ------------------------------------------------------------------
    release_rate = build["pressure_release_success"]["rate"]
    third_per_match = build["third_man_progression_proxy"]["per_match"] or 0.0
    interval_per_match = offensive["interval_entries"]["per_match"] or 0.0
    cp_share = defensive["counterpress"]["rate"] or 0.0
    high_press_share = defensive["high_press_share"]["rate"] or 0.0
    offside_pm = defensive["opponent_offside_outcomes"]["per_match"] or 0.0

    release_cut = float(cfg.get("planning_pressure_release_rate", .55))
    third_cut = float(cfg.get("planning_third_man_per_match", 1.5))
    interval_cut = float(cfg.get("planning_interval_per_match", 3.0))

    if release_rate is not None and release_rate < release_cut:
        monday = ("Corrección / salida bajo presión", "Revisar secuencias de atracción de presión y salida posterior; priorizar apoyos y tercer hombre.", "pressure_release_success")
    elif third_per_match < third_cut:
        monday = ("Corrección / tercer hombre", "Explorar más conexiones A→B→C progresivas en tareas de construcción.", "third_man_progression_proxy")
    else:
        monday = ("Consolidación", "Revisar en video las secuencias de salida bajo presión que ya generan progresión y consolidar sus gatillos.", "pressure_release_success")

    if cp_share >= float(cfg.get("planning_counterpress_share_high", .18)) or high_press_share >= float(cfg.get("planning_high_press_share_high", .35)):
        tuesday = ("Principios defensivos", "Coordinar distancias de presión, cobertura y reorganización del bloque tras pérdida.", "counterpress/high_press")
    else:
        tuesday = ("Principios defensivos", "Trabajar compactación, coberturas y gatillos de salto sin asumir un modelo de presión alta.", "counterpress/high_press")

    thursday_focus = "Ataque de intervalos central-lateral y ocupación de half-spaces" if interval_per_match < interval_cut else "Consolidar ataques de intervalo y variantes de centro a zona peligrosa"

    planning = [
        {"day":"Lunes","theme":monday[0],"focus":monday[1],"evidence":monday[2],"requires_opponent_data":False},
        {"day":"Martes","theme":tuesday[0],"focus":tuesday[1],"evidence":tuesday[2],"requires_opponent_data":False},
        {"day":"Miércoles","theme":"Plan contra rival","focus":"Definir altura y gatillos de presión frente a la salida específica del próximo rival.","evidence":f"offside_proxy={offside_pm:.2f}/partido; high_press_share={high_press_share:.2f}","requires_opponent_data":True},
        {"day":"Jueves","theme":"Plan ofensivo contra rival","focus":thursday_focus + "; ajustar al comportamiento defensivo del rival.","evidence":"interval_entries / halfspace_entries / cross_to_danger_zone_proxy","requires_opponent_data":True},
        {"day":"Viernes","theme":"Balón parado y escenarios","focus":"Revisar balón parado y escenarios de partido usando xG/OBV como evidencia de valor, sin prescribir carga física desde EFOS.","evidence":"xG / OBV / play patterns","requires_opponent_data":False},
    ]

    return {
        "version": "TACTICAL_FRAMEWORK_v1",
        "team": focal_team,
        "matches": matches,
        "data_quality": dq,
        "defensive_profile": defensive,
        "construction_progression": build,
        "offensive_microconcepts": offensive,
        "value_purpose": value,
        "weekly_planning_hypotheses": planning,
        "terminology": {
            "fishing": "Proxy de atracción de presión: pase completado bajo presión antes del último tercio, con evaluación adicional de liberación/progresión posterior.",
            "third_man": "Proxy secuencial A→B→C con tres jugadores distintos y ganancia territorial; no observa el movimiento sin balón.",
            "aliup": "Etiqueta conceptual de video; EFOS sólo observa un proxy geométrico de centro hacia zona peligrosa.",
            "offside_trap": "EFOS observa outcomes de offside del rival; atribuirlos a una trampa deliberada requiere validación de video/360.",
        },
        "methodological_guardrail": "Cada concepto se reporta como observación o proxy según la información realmente disponible. Un proxy no prueba por sí solo intención del entrenador.",
    }
