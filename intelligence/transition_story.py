"""EFOS · Transiciones observadas desde eventos StatsBomb, sin trayectorias sintéticas.

Una transición OFENSIVA requiere una posesión del equipo posterior a una del rival,
con una Ball Recovery/Interception propia observable en esa nueva posesión.
Una pérdida DEFENSIVA requiere una acción de pérdida candidata Y un cambio de
propietario hacia el rival en los 15 s siguientes dentro del mismo periodo.

Cada denominador se limita a casos verificables. La ausencia de evento no
se interpreta como ausencia de comportamiento táctico (event data != tracking).
No modifica ESI/CTS ni ningún motor canónico existente.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RECOVERY = {"Ball Recovery", "Interception"}
LOSS = {"Dispossessed", "Miscontrol"}
FAILED_PASSES = {"Incomplete", "Out", "Pass Offside", "Unknown"}
RESTARTS = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
NEEDED = {"match_id", "period", "possession", "possession_team", "team",
          "event_type", "timestamp_seconds", "event_id"}


def _values(df: pd.DataFrame, col: str, default=np.nan) -> pd.Series:
    return df[col] if col in df.columns else pd.Series(default, index=df.index)


def _is_loss(g: pd.DataFrame) -> pd.Series:
    ev = g["event_type"]
    bad_pass = (ev.eq("Pass") & _values(g, "pass_outcome").isin(FAILED_PASSES)
                & ~_values(g, "type_name").isin(RESTARTS))
    return ev.isin(LOSS) | bad_pass


def _snip(g: pd.DataFrame, limit: int = 5) -> str:
    """Only observed events, never invented intermediate positions."""
    terms = [str(x) for x in g.event_type.dropna() if str(x) not in {"Ball Receipt*", "Pressure"}]
    return " → ".join(terms[:limit]) + (" → …" if len(terms) > limit else "")


def _xg(s: pd.DataFrame) -> tuple[float, int]:
    if s.empty:
        return 0.0, 0
    vals = pd.to_numeric(_values(s, "statsbomb_xg"), errors="coerce")
    return float(vals.sum()), int(vals.notna().sum())


def analyze_transitions(events: pd.DataFrame, team: str, match_ids=None) -> dict:
    """Compute evidence examples and summaries; counts are event-based, scoped by match/period.

    No calculations from interpolated frames. No inferred moves or space control.
    """
    empty = {"offensive": pd.DataFrame(), "defensive": pd.DataFrame(),
             "status": "unavailable", "reason": "Faltan eventos y campos obligatorios."}
    if not isinstance(events, pd.DataFrame) or not NEEDED.issubset(events.columns):
        return empty
    e = events.copy()
    if match_ids is not None:
        mids = {str(m) for m in match_ids}
        e = e[e.match_id.astype(str).isin(mids)].copy()
    if e.empty:
        return {**empty, "reason": "No hay eventos para la muestra seleccionada."}
    e["_secs"] = pd.to_numeric(e.timestamp_seconds, errors="coerce")
    e["_order"] = pd.to_numeric(_values(e, "index"), errors="coerce")
    e["_order"] = e["_order"].fillna(pd.Series(np.arange(len(e)), index=e.index))
    e = e.dropna(subset=["_secs", "period", "possession", "possession_team"])
    if e.empty:
        return {**empty, "reason": "Faltan tiempos o propietario de posesión verificable."}
    # Order by canonical in-match event index, keeping stable order for ties.
    e = e.sort_values(["match_id", "period", "_order", "_secs"], kind="stable")
    attacks: list[dict] = []
    defenses: list[dict] = []
    for (mid, period), game in e.groupby(["match_id", "period"], sort=False):
        blocks = []
        for pos, block in game.groupby("possession", sort=False):
            owners = block.possession_team.dropna().astype(str)
            if owners.empty:
                continue
            blocks.append((pos, str(owners.iloc[0]), block))
        for idx in range(1, len(blocks)):
            pos, owner, block = blocks[idx]
            _, previous_owner, previous_block = blocks[idx - 1]
            # New owned possession with an explicitly registered regain event.
            if owner == team and previous_owner != team:
                rec = block[block.team.eq(team) & block.event_type.isin(RECOVERY)]
                rec = rec[~_values(rec, "outcome_name").isin(["Lost In Play", "Lost Out"])]
                if not rec.empty:
                    start = rec.iloc[0]
                    t0 = float(start._secs)
                    actions = block[(block._secs >= t0) & (block._secs <= t0 + 15)
                                    & block.team.eq(team) & ~block.event_id.eq(start.event_id)]
                    shots = actions[actions.event_type.eq("Shot")]
                    xg, available = _xg(shots)
                    first_balls = actions[actions.event_type.isin(["Pass", "Carry", "Carries", "Dribble", "Shot"])]
                    first = first_balls.iloc[0] if not first_balls.empty else None
                    attacks.append({
                        "match_id": str(mid), "period": period, "possession": pos,
                        "event_id": str(start.event_id), "minute": start.get("minute", np.nan),
                        "timestamp_seconds": t0, "player": start.get("player", np.nan),
                        "anchor_type": start.event_type, "location_x": start.get("location_x", np.nan),
                        "location_y": start.get("location_y", np.nan),
                        "actions": int(len(actions)),
                        "first_ball_action": str(first.event_type) if first is not None else None,
                        "first_ball_player": first.get("player") if first is not None else None,
                        "first_action_after_s": (float(first._secs) - t0) if first is not None else np.nan,
                        "passes": int(actions.event_type.eq("Pass").sum()),
                        "carries": int(actions.event_type.isin(["Carry", "Carries"]).sum()),
                        "shots": int(len(shots)), "xg": xg, "shots_with_xg": available,
                        "sequence": _snip(actions),
                        "event_ids": actions.event_id.astype(str).tolist(),
                    })
            # A candidate turnover counts only when the next possession belongs to the rival.
            if previous_owner == team and owner != team:
                cand = previous_block[previous_block.team.eq(team) & _is_loss(previous_block)]
                if cand.empty:
                    continue
                lost = cand.iloc[-1]
                t0 = float(lost._secs)
                t_opp = float(block._secs.min())
                if t_opp < t0 or t_opp - t0 > 15:
                    continue  # unclear possession change, never call it a confirmed loss
                # Only measure pressure after the opponent's possession actually starts.
                opp5 = block[(block._secs >= t_opp) & (block._secs <= t0 + 5)]
                p = opp5[opp5.team.eq(team) & opp5.event_type.eq("Pressure")]
                # Opponent's possession, not a later unrelated attacking sequence.
                opp15 = block[(block._secs >= t_opp) & (block._secs <= t0 + 15)
                              & block.team.ne(team)]
                shots = opp15[opp15.event_type.eq("Shot")]
                xg, available = _xg(shots)
                # Explicit recovery confirmed in next team-owned block within five seconds.
                recovered = False
                if idx + 1 < len(blocks) and blocks[idx + 1][1] == team:
                    regain = blocks[idx + 1][2]
                    regained_events = regain[regain.team.eq(team) & regain.event_type.isin(RECOVERY)
                                             & (regain._secs > t0) & (regain._secs <= t0 + 5)]
                    regained_events = regained_events[~_values(regained_events, "outcome_name").isin(["Lost In Play", "Lost Out"])]
                    recovered = bool(len(regained_events))
                defenses.append({
                    "match_id": str(mid), "period": period, "possession": previous_block.possession.iloc[0],
                    "event_id": str(lost.event_id), "minute": lost.get("minute", np.nan),
                    "timestamp_seconds": t0, "player": lost.get("player", np.nan),
                    "anchor_type": lost.event_type, "location_x": lost.get("location_x", np.nan),
                    "location_y": lost.get("location_y", np.nan),
                    "pressures_5s": int(len(p)), "recovered_5s": recovered,
                    "first_pressure_after_s": (float(p._secs.min()) - t0) if not p.empty else np.nan,
                    "rival_shots_15s": int(len(shots)), "rival_xg_15s": xg,
                    "rival_shots_with_xg": available, "sequence": _snip(opp15),
                    "event_ids": opp15.event_id.astype(str).tolist(),
                })
    return {"offensive": pd.DataFrame(attacks), "defensive": pd.DataFrame(defenses),
            "status": "ok", "reason": None}


def describe_transitions(out: dict, direction: str) -> dict:
    """Numerators, denominators, coverage, and conservative Spanish story."""
    kind = "offensive" if direction == "offensive" else "defensive"
    data = out.get(kind)
    if not isinstance(data, pd.DataFrame) or data.empty:
        return {"n": 0, "matches": 0, "story": (
            "No hay suficientes cambios de posesión verificables y eventos etiquetados "
            "para describir esta transición. No se completa la información por inferencia."),
            "rate": None, "xg": None, "coverage": (0, 0)}
    n = len(data)
    matches = int(data.match_id.nunique())
    qualified = matches >= 5 and n >= 30
    if kind == "offensive":
        n_shot = int(data.shots.gt(0).sum())
        xg = float(data.xg.sum())
        cov = (int(data.shots_with_xg.sum()), int(data.shots.sum()))
        first = data.first_ball_action.dropna().astype(str).value_counts()
        common_first = (first.index[0], int(first.iloc[0]), int(first.sum())) if len(first) else None
        return {"n": n, "matches": matches, "shot_possessions": n_shot,
                "common_first": common_first,
                "rate": n_shot / n, "xg": xg if cov[1] and cov[0] == cov[1] else None,
                "coverage": cov, "total_shots": int(data.shots.sum()),
                "story": (f"De {n} recuperaciones o intercepciones registradas que iniciaron posesiones "
                          f"en {matches} partidos, {n_shot} produjeron al menos un remate "
                          "en los siguientes 15 s de la misma posesión. "
                          + ("Muestra descriptiva; no demuestra que cada recuperación generara ventaja espacial. "
                             if qualified else "Muestra exploratoria: no demuestra un patrón estable del entrenador. ")
                          + "La secuencia y su desenlace pueden consultarse en los eventos originales.")}
    p = int(data.pressures_5s.gt(0).sum())
    conceded = int(data.rival_shots_15s.gt(0).sum())
    regains = int(data.recovered_5s.sum())
    cov = (int(data.rival_shots_with_xg.sum()), int(data.rival_shots_15s.sum()))
    return {"n": n, "matches": matches, "pressure_cases": p, "regains": regains,
            "rival_shot_cases": conceded, "rate": p / n,
            "xg": float(data.rival_xg_15s.sum()) if cov[1] and cov[0] == cov[1] else None,
            "coverage": cov,
            "story": (f"En {n} pérdidas candidatas seguidas de una posesión rival confirmada "
                      f"en {matches} partidos, se registró al menos una acción de presión "
                      f"dentro de los siguientes 5 s en {p} casos; "
                      f"el rival remató dentro de 15 s en {conceded}. "
                      + ("Es una asociación descriptiva, no un marcaje ni una presión coordinada demostrados."
                         if qualified else "Muestra exploratoria: no se infiere una respuesta defensiva habitual."))}


def find_360_anchors(events: pd.DataFrame, team: str, direction: str,
                     frame_ids: set[str], anchor_ids: set[str] | None = None) -> pd.DataFrame:
    """Observed transition anchors with at least one subsequent 360 image (0–15 s).

    Never requires the anchor event itself to have a 360 snapshot: the provider
    may photograph a later pass or shot but not the recovery/loss. No positions
    or intermediate events are synthesized by this selector.
    """
    required = {"event_id", "match_id", "period", "timestamp_seconds", "team", "event_type"}
    if not isinstance(events, pd.DataFrame) or not required.issubset(events.columns) or not frame_ids:
        return pd.DataFrame(columns=sorted(required))
    e = events.copy()
    e["_time360"] = pd.to_numeric(e.timestamp_seconds, errors="coerce")
    e = e.dropna(subset=["_time360", "period", "match_id"])
    if direction == 'Tras recuperación':
        selected = e.team.eq(team) & e.event_type.isin(RECOVERY)
    else:
        selected = e.team.eq(team) & _is_loss(e)
    if anchor_ids is not None:
        selected &= e.event_id.astype(str).isin({str(x) for x in anchor_ids})
    anchors = e.loc[selected].copy()
    if anchors.empty:
        return anchors
    images = e.loc[e.event_id.astype(str).isin(frame_ids)]
    # Iterate only the small match/period index, not over every source event.
    valid = set()
    for (mid, per), grp in anchors.groupby(["match_id", "period"], sort=False):
        times = images.loc[images.match_id.eq(mid) & images.period.eq(per), "_time360"]
        if times.empty:
            continue
        photo_times = np.sort(times.to_numpy(dtype=float))
        t0 = grp["_time360"].to_numpy(dtype=float)
        idx = np.searchsorted(photo_times, t0, side="left")
        ok = idx < len(photo_times)
        ok[ok] = photo_times[idx[ok]] <= t0[ok] + 15
        valid.update(grp.loc[ok, "event_id"].astype(str))
    return anchors.loc[anchors.event_id.astype(str).isin(valid)].sort_values(
        ["match_id", "period", "_time360"], kind="stable"
    ).head(300).drop(columns=["_time360"])
