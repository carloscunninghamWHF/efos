"""EFOS — Transiciones con StatsBomb 360: diagramas de Voronoi en el instante real.

Con 360 cada evento trae la posición de los jugadores visibles en ese instante. Este módulo analiza:

  * Transición ofensiva  → TODAS las recuperaciones (Ball Recovery / Interception ganada, juego abierto),
    con la fotografía del instante de la recuperación.
  * Transición defensiva → TODAS las pérdidas (pase fallado, Dispossessed, Miscontrol, en juego abierto),
    con la fotografía del instante de la pérdida y una segunda fotografía 2–6 s después (compactación).

Se calcula lo mismo para el equipo analizado y para sus rivales en esos partidos, de modo que cada
lectura se compara con «los rivales en la misma situación».

Convenciones
  * Las fotografías 360 vienen orientadas hacia el ataque del equipo que ejecuta el evento y su campo
    «teammate» es relativo a ese jugador (verificado: el actor coincide con la ubicación del evento).
  * Todo se calcula en el sistema del EQUIPO QUE ATACA tras el cambio de posesión (ataca hacia x = 120).
  * Solo se usan las celdas del campo que la cámara ve (visible_area): fuera de ella no se asigna dueño.
  * Unidades StatsBomb (yardas) internamente; resultados en metros y m².

Los 10 análisis (O = ofensiva, D = defensiva):
  O1 Espacios disponibles tras recuperación   O2 Líneas de progresión         O3 Espacios vulnerables del rival
  O4 Apoyos al jugador que recupera           O5 Ventajas espaciales           D1 Eficacia de la presión tras pérdida
  D2 Protección de espacios centrales         D3 Espacios libres para el rival D4 Coberturas defensivas
  D5 Compactación defensiva tras pérdida
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.path import Path as MPath
from scipy.spatial import cKDTree

YD = 0.9144
YD2 = YD * YD
LENGTH, WIDTH = 120.0, 80.0
STEP = 2.0                                   # malla de 2 × 2 yardas para los mapas agregados
_gx, _gy = np.meshgrid(np.arange(STEP / 2, LENGTH, STEP), np.arange(STEP / 2, WIDTH, STEP))
GX, GY = _gx, _gy                            # forma (40, 60)
GRID = np.column_stack([_gx.ravel(), _gy.ravel()])
CELL_M2 = STEP * STEP * YD2

AHEAD_RADIUS = 35.0 / YD                     # zona analizada: por delante del balón y a < 35 m de él
FREE_RADIUS = 25.0 / YD                      # espacio libre: solo a < 25 m del balón (la cámara 360 no ve a los
                                             # defensores lejanos y el borde de la imagen parecería «libre»)
FREE_DIST = 8.0 / YD                         # espacio «vulnerable/libre»: defensor más cercano a ≥ 8 m
FREE_ATTACKER = 5.0 / YD                     # atacante libre: defensor más cercano a ≥ 5 m
SUPPORT_RADIUS = 20.0 / YD
PASS_LANE = 2.0 / YD
PRESS_RADII = (5.0 / YD, 10.0 / YD)
COVER_RADIUS = 15.0 / YD
NEAR_BALL = 25.0 / YD
BLOCK_RADIUS = 35.0 / YD                     # jugadores que cuentan para el bloque (cerca del balón)
MIN_ATT, MIN_DEF = 2, 3
CORRIDORS = [("Banda izquierda", 0, 18), ("Interior izquierdo", 18, 30), ("Carril central", 30, 50),
             ("Interior derecho", 50, 62), ("Banda derecha", 62, 80)]
CENTRAL = (30.0, 50.0)
RECOVERY_TYPES = {"Ball Recovery", "Interception"}
LOSS_PASS = {"Incomplete", "Out", "Pass Offside", "Unknown"}
SET_PIECE_TYPES = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off", "Penalty"}

POINT_TITLES = {
    "O1": "Espacios disponibles tras recuperación", "O2": "Líneas de progresión",
    "O3": "Espacios vulnerables del rival", "O4": "Apoyos al jugador que recupera",
    "O5": "Ventajas espaciales en contraataques",
    "D1": "Eficacia de la presión tras pérdida", "D2": "Protección de espacios centrales",
    "D3": "Espacios libres para el rival", "D4": "Coberturas defensivas", "D5": "Compactación defensiva tras pérdida",
}


# ============================================================== carga 360
def find_360_dir(paths) -> Path | None:
    """Busca la carpeta 360 junto a los CSV de eventos (statsbomb_360, stastbomb_360, three-sixty, 360)."""
    names = ("statsbomb_360", "stastbomb_360", "three-sixty", "three_sixty", "360", "frames_360")
    seen = set()
    for p in paths or []:
        p = Path(p)
        for base in (p.parent, p.parent.parent):
            if base in seen:
                continue
            seen.add(base)
            for n in names:
                d = base / n
                if d.is_dir() and any(d.glob("*.json")):
                    return d
    return None


def load_frames(source, match_ids=None) -> dict:
    """Carga 360 desde una carpeta (un JSON por partido), un archivo o una lista. {event_id: frame}."""
    if source is None:
        return {}
    files = []
    for s in (source if isinstance(source, (list, tuple, set)) else [source]):
        s = Path(s)
        files += sorted(s.glob("*.json")) if s.is_dir() else ([s] if s.exists() else [])
    keep = {str(m) for m in match_ids} if match_ids is not None else None
    out = {}
    for f in files:
        if keep is not None and f.stem not in keep and f.stem.isdigit():
            continue
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for fr in raw if isinstance(raw, list) else []:
            eid = fr.get("event_uuid") or fr.get("event_id")
            if eid:
                out[str(eid)] = {"event_id": str(eid), "visible_area": fr.get("visible_area"),
                                 "freeze_frame": fr.get("freeze_frame") or [], "match_id": f.stem}
    return out


# ============================================================== una fotografía
def _players(frame: dict):
    ff = frame.get("freeze_frame") or []
    xy = np.array([p["location"][:2] for p in ff], float) if ff else np.empty((0, 2))
    mate = np.array([bool(p.get("teammate")) for p in ff], bool)
    actor = np.array([bool(p.get("actor")) for p in ff], bool)
    keeper = np.array([bool(p.get("keeper")) for p in ff], bool)
    return xy, mate, actor, keeper


def _visible_mask(frame: dict, flip: bool) -> np.ndarray:
    va = frame.get("visible_area")
    if not va or len(va) < 6:
        return np.ones(len(GRID), bool)
    poly = np.array(va, float).reshape(-1, 2)
    if flip:
        poly = np.column_stack([LENGTH - poly[:, 0], WIDTH - poly[:, 1]])
    return MPath(poly).contains_points(GRID)


def snapshot(frame: dict, ball, actor_team_attacks: bool) -> dict | None:
    """Fotografía en el sistema del equipo que ataca (x → 120).

    actor_team_attacks=True  → recuperación: el equipo del actor pasa a atacar.
    actor_team_attacks=False → pérdida: el equipo del actor pasa a defender; se gira 180° el campo.
    """
    xy, mate, actor, keeper = _players(frame)
    if not len(xy):
        return None
    flip = not actor_team_attacks
    bx, by = float(ball[0]), float(ball[1])
    if flip:
        xy = np.column_stack([LENGTH - xy[:, 0], WIDTH - xy[:, 1]]); bx, by = LENGTH - bx, WIDTH - by
    att_mask = mate if actor_team_attacks else ~mate
    att, dfn = xy[att_mask], xy[~att_mask]
    return {"att": att, "dfn": dfn, "ball": np.array([bx, by]), "vis": _visible_mask(frame, flip),
            "att_actor": actor[att_mask], "def_keeper": keeper[~att_mask], "dfn_actor": actor[~att_mask]}


def _seg_dist(points, a, b):
    ab = b - a; t = np.clip(((points - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(points - (a + np.outer(t, ab)), axis=1)


def _hull(xy):
    if len(xy) < 3:
        return 0.0, np.empty((0, 2))
    from scipy.spatial import ConvexHull
    try:
        h = ConvexHull(xy); return float(h.volume), xy[h.vertices]
    except Exception:
        return 0.0, np.empty((0, 2))


def analyze_snapshot(s: dict) -> dict:
    """Métricas de las 10 lecturas para una fotografía + capas para los mapas agregados."""
    att, dfn, ball, vis = s["att"], s["dfn"], s["ball"], s["vis"]
    bx, by = ball
    pts = np.vstack([att, dfn])
    owner = cKDTree(pts).query(GRID)[1]
    own_att = owner < len(att)
    d_def = cKDTree(dfn).query(GRID)[0] if len(dfn) else np.full(len(GRID), np.inf)
    gx, gy = GRID[:, 0], GRID[:, 1]
    ahead = vis & (gx >= bx) & (np.hypot(gx - bx, gy - by) <= AHEAD_RADIUS)
    n_ahead = max(int(ahead.sum()), 1)
    m = {"n_att": len(att), "n_def": len(dfn)}

    # O1 / (vista inversa) espacio por delante del balón
    m["esp_atac_pct"] = 100 * float((ahead & own_att).sum()) / n_ahead
    m["esp_atac_m2"] = float((ahead & own_att).sum() * CELL_M2)
    # O2 carriles
    lanes = {}
    for name, y0, y1 in CORRIDORS:
        z = ahead & (gy >= y0) & (gy < y1)
        lanes[name] = 100 * float((z & own_att).sum()) / int(z.sum()) if z.sum() >= 5 else np.nan
    m["carriles"] = lanes
    valid = {k: v for k, v in lanes.items() if not np.isnan(v)}
    m["carril_abierto"] = max(valid, key=valid.get) if valid else None
    # O3 / D3 espacio lejos de cualquier defensor (≥ 8 m)
    near_zone = ahead & (np.hypot(gx - bx, gy - by) <= FREE_RADIUS)
    free = near_zone & (d_def >= FREE_DIST)
    m["libre_pct"] = 100 * float(free.sum()) / max(int(near_zone.sum()), 1)
    m["libre_m2"] = float(free.sum() * CELL_M2)
    dd_att = cKDTree(dfn).query(att)[0] if len(dfn) and len(att) else np.full(len(att), np.inf)
    in_ahead = (att[:, 0] >= bx) & (np.hypot(att[:, 0] - bx, att[:, 1] - by) <= AHEAD_RADIUS) if len(att) else np.array([], bool)
    in_near = (att[:, 0] >= bx) & (np.hypot(att[:, 0] - bx, att[:, 1] - by) <= FREE_RADIUS) if len(att) else np.array([], bool)
    m["atac_en_libre"] = int((in_near & (dd_att >= FREE_DIST)).sum())
    # O4 apoyos al que tiene el balón (actor si está; si no, el atacante más cercano al balón)
    if len(att):
        ci = int(np.flatnonzero(s["att_actor"])[0]) if s["att_actor"].any() else int(np.argmin(np.linalg.norm(att - ball, axis=1)))
        mates = np.delete(att, ci, axis=0)
    else:
        ci, mates = -1, np.empty((0, 2))
    dist = np.linalg.norm(mates - ball, axis=1) if len(mates) else np.array([])
    near = mates[dist < SUPPORT_RADIUS] if len(mates) else mates
    lane_free = np.array([not (len(dfn) and (_seg_dist(dfn, ball, q) < PASS_LANE).any()) for q in near], bool)
    m["apoyos_20m"] = int(len(near))
    m["lineas_libres"] = int(lane_free.sum())
    rel = near - ball if len(near) else np.empty((0, 2))
    m["apoyos_delante"] = int((rel[:, 0] > 2).sum()) if len(rel) else 0
    m["apoyos_detras"] = int((rel[:, 0] < -2).sum()) if len(rel) else 0
    # O5 ventajas: atacantes libres por delante y balance numérico cerca del balón
    free_att = in_ahead & (att[:, 0] > bx + 1) & (dd_att >= FREE_ATTACKER) if len(att) else np.array([], bool)
    m["atac_libres"] = int(free_att.sum())
    cnt = lambda P: int(((P[:, 0] >= bx - 5) & (np.linalg.norm(P - ball, axis=1) < NEAR_BALL)).sum()) if len(P) else 0
    m["balance"] = cnt(att) - cnt(dfn)
    # D1 presión sobre el balón (sin contar al jugador que acaba de perderlo: está siempre junto al balón)
    loser = s["dfn_actor"] if len(dfn) else np.array([], bool)
    db = np.linalg.norm(dfn - ball, axis=1) if len(dfn) else np.array([])
    db_p = np.where(loser, np.inf, db) if len(dfn) else db
    m["def_5m"] = int((db_p < PRESS_RADII[0]).sum())
    m["def_10m"] = int((db_p < PRESS_RADII[1]).sum())
    r10 = vis & (np.linalg.norm(GRID - ball, axis=1) < PRESS_RADII[1])
    m["control_r10_def_pct"] = 100 * float((r10 & ~own_att).sum()) / max(int(r10.sum()), 1)
    m["celda_poseedor_m2"] = float((vis & (owner == ci)).sum() * CELL_M2) if ci >= 0 else np.nan
    # D2 carril central entre balón y portería defendida
    cz = ahead & (gy >= CENTRAL[0]) & (gy < CENTRAL[1])
    m["central_def_pct"] = 100 * float((cz & ~own_att).sum()) / int(cz.sum()) if cz.sum() >= 5 else np.nan
    # D4 coberturas al que presiona (defensores más cerca de su portería que él, a < 15 m)
    if len(dfn):
        field_idx = np.flatnonzero(~s["def_keeper"] & ~loser)
        field_idx = field_idx if len(field_idx) else np.arange(len(dfn))
        pi = field_idx[np.argmin(db[field_idx])]
        presser = dfn[pi]; others = np.delete(dfn, pi, axis=0)
        okeep = np.delete(s["def_keeper"] | loser, pi)
        cov_mask = (~okeep) & (others[:, 0] > presser[0]) & (np.linalg.norm(others - presser, axis=1) < COVER_RADIUS) if len(others) else np.array([], bool)
        m["coberturas"] = int(cov_mask.sum())
        m["dist_presion_m"] = float(db[pi] * YD)
        cover_rel = (others[cov_mask] - presser) if len(others) else np.empty((0, 2))
    else:
        presser, cover_rel = None, np.empty((0, 2))
        m["coberturas"], m["dist_presion_m"] = 0, np.nan
    # D5 bloque defensivo cerca del balón (sin portero)
    blk = dfn[(~s["def_keeper"]) & ~loser & (np.linalg.norm(dfn - ball, axis=1) < BLOCK_RADIUS)] if len(dfn) else dfn
    area, hull = _hull(blk)
    m["bloque_m2"] = area * YD2
    m["bloque_ancho_m"] = float(np.ptp(blk[:, 1]) * YD) if len(blk) >= 2 else np.nan
    m["bloque_prof_m"] = float(np.ptp(blk[:, 0]) * YD) if len(blk) >= 2 else np.nan
    m["bloque_n"] = int(len(blk))
    m["fiable"] = len(att) >= MIN_ATT and len(dfn) >= MIN_DEF

    layers = {"own_att": own_att, "ahead": ahead, "free": free, "vis": vis, "central": cz,
              "support_rel": rel, "support_free": lane_free,
              "free_att_rel": (att[free_att] - ball) if len(att) else np.empty((0, 2)),
              "def_rel": (dfn[~s["def_keeper"] & ~loser] - ball) if len(dfn) else np.empty((0, 2)), "near": near_zone,
              "cover_rel": cover_rel, "blk_rel": (blk - ball) if len(blk) else np.empty((0, 2)), "hull": hull}
    return m, layers


# ============================================================== momentos de transición
def _prep(ev: pd.DataFrame) -> pd.DataFrame:
    e = ev.copy()
    for c in ("timestamp_seconds", "location_x", "location_y", "end_location_x", "end_location_y", "statsbomb_xg",
              "minute", "second", "period", "possession"):
        e[c] = pd.to_numeric(e[c], errors="coerce") if c in e else np.nan
    for c in ("pass_outcome", "outcome_name", "play_pattern_name", "type_name", "shot_outcome", "player"):
        if c not in e:
            e[c] = np.nan
    e["event_id"] = e["event_id"].astype(str)
    m = e["minute"].copy(); sh = e["period"].eq(2)
    if sh.any() and m[sh].median() < 45:
        m = m.where(~sh, m + 45)
    e["minuto_juego"] = m + e["second"].fillna(0) / 60
    return e


def recoveries(e: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    r = e[mask & e["event_type"].isin(RECOVERY_TYPES)]
    return r[~r["outcome_name"].isin(["Lost In Play", "Lost Out"])]


def losses(e: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    me = e[mask]
    failed = me["event_type"].eq("Pass") & me["pass_outcome"].isin(LOSS_PASS) & ~me["type_name"].isin(SET_PIECE_TYPES)
    return me[me["event_type"].isin(["Dispossessed", "Miscontrol"]) | failed]


def _first_progression(by_poss: dict, rec: pd.Series, window: float = 10.0):
    """Primer pase completado o conducción que avanza ≥ 10 yd tras la recuperación (misma posesión)."""
    g = by_poss.get((rec["match_id"], rec["period"], rec["possession"]))
    if g is None:
        return None
    g = g[g["team"].eq(rec["team"]) & (g["timestamp_seconds"] - rec["timestamp_seconds"]).between(0, window)]
    if g.empty:
        return None
    r = g.iloc[0]
    return (r["location_x"], r["location_y"], r["end_location_x"], r["end_location_y"], r["event_type"])


def build_moments(ev: pd.DataFrame, team: str, frames: dict, shot_window: float = 15.0) -> dict:
    """Calcula métricas y capas para cada recuperación y pérdida con fotografía 360 (equipo y rivales)."""
    e = _prep(ev)
    e = e[e["match_id"].isin(e.loc[e["team"].eq(team), "match_id"].unique())]
    keep = ["event_id", "match_id", "team", "player", "event_type", "type_name", "outcome_name", "pass_outcome", "period",
            "possession", "timestamp_seconds", "minuto_juego", "location_x", "location_y", "end_location_x", "end_location_y",
            "statsbomb_xg", "shot_outcome"]
    e = e[keep].sort_values(["match_id", "period", "timestamp_seconds"], kind="stable").reset_index(drop=True)
    for c in ("team", "player", "event_type", "type_name", "outcome_name", "pass_outcome", "shot_outcome", "event_id"):
        e[c] = e[c].astype(object)
    e["_has360"] = e["event_id"].isin(set(frames)) & e["location_x"].notna()
    cand = e[e["_has360"]]
    # para D5: por (partido, parte) tiempos, equipo y fila de los eventos con 360
    ts = {k: (g["timestamp_seconds"].to_numpy(), g["team"].to_numpy(object), g.index.to_numpy())
          for k, g in cand.groupby(["match_id", "period"])}
    prog_ev = e[e["event_type"].isin(["Pass", "Carries", "Carry"]) & e["pass_outcome"].isna()
                & ((e["end_location_x"] - e["location_x"]) >= 10)]
    by_poss = {k: g for k, g in prog_ev.groupby(["match_id", "period", "possession"])}
    shots = e[e["event_type"].eq("Shot")]
    # remates por (partido, parte): tiempos, equipo, posesión, xG, gol
    sh_mp = {k: (g["timestamp_seconds"].to_numpy(float), g["team"].to_numpy(object), g["possession"].to_numpy(float),
                 g["statsbomb_xg"].fillna(0).to_numpy(float), g["shot_outcome"].eq("Goal").to_numpy())
             for k, g in shots.groupby(["match_id", "period"])}

    def shots_after(match, period, t, team_, same_team, possession=None):
        a = sh_mp.get((match, period))
        if a is None:
            return 0, 0.0, False
        tt, tm, po, xg, gl = a
        k = (tt >= t) & (tt <= t + shot_window) & ((tm == team_) if same_team else (tm != team_))
        if possession is not None:
            k &= po == possession
        return int(k.sum()), float(xg[k].sum()), bool(gl[k].any())
    rows, lay = [], {}

    for owner in ("equipo", "rival"):
        mask = e["team"].eq(team) if owner == "equipo" else ~e["team"].eq(team)
        # ---- transición ofensiva: recuperaciones (el actor pasa a atacar)
        for r in recoveries(e, mask & e["_has360"]).to_dict("records"):
            fr = frames.get(r["event_id"])
            if fr is None or pd.isna(r["location_x"]):
                continue
            s = snapshot(fr, (r["location_x"], r["location_y"]), actor_team_attacks=True)
            if s is None:
                continue
            m, L = analyze_snapshot(s)
            # ¿acaba en remate en ≤ 15 s (misma posesión)?
            n_sh, xg_sh, goal_sh = shots_after(r["match_id"], r["period"], r["timestamp_seconds"], r["team"], True, r["possession"])
            prog = _first_progression(by_poss, r)
            key = f"O|{r['event_id']}"
            lay[key] = {**L, "snap": s, "prog": prog}
            rows.append({"clave": key, "fase": "Ofensiva", "quien": owner, "match_id": r["match_id"], "equipo_evento": r["team"],
                         "jugador": r["player"], "minuto": r["minuto_juego"], "x": r["location_x"], "y": r["location_y"],
                         "acaba_en_tiro": n_sh > 0, "xg_siguiente": xg_sh, "gol_siguiente": goal_sh,
                         "carril_progresion": _lane_of(prog[3]) if prog else None, **_flat(m)})
        # ---- transición defensiva: pérdidas (el actor pasa a defender)
        for l in losses(e, mask & e["_has360"]).to_dict("records"):
            fr = frames.get(l["event_id"])
            if fr is None or pd.isna(l["location_x"]):
                continue
            bx = l["end_location_x"] if l["event_type"] == "Pass" and not pd.isna(l["end_location_x"]) else l["location_x"]
            by = l["end_location_y"] if l["event_type"] == "Pass" and not pd.isna(l["end_location_y"]) else l["location_y"]
            s = snapshot(fr, (bx, by), actor_team_attacks=False)
            if s is None:
                continue
            m, L = analyze_snapshot(s)
            # segunda fotografía 2–6 s después: primer evento del rival con 360 (D5)
            g = ts.get((l["match_id"], l["period"]))
            after = None
            if g is not None:
                tt, tm, ix = g
                i0, i1 = np.searchsorted(tt, l["timestamp_seconds"] + 2), np.searchsorted(tt, l["timestamp_seconds"] + 6, side="right")
                hit = [j for j in range(i0, i1) if tm[j] != l["team"]]
                if hit:
                    n = e.loc[ix[hit[-1]]].to_dict()      # la fotografía más tardía dentro de la ventana 2–6 s
                    s1 = snapshot(frames[n["event_id"]], (n["location_x"], n["location_y"]), actor_team_attacks=True)
                    if s1 is not None and len(s1["dfn"]):
                        m1, L1 = analyze_snapshot(s1)
                        after = {"seg": float(n["timestamp_seconds"] - l["timestamp_seconds"]), "m": m1,
                                 "blk_rel": L1["blk_rel"], "hull": L1["hull"], "ball": s1["ball"]}
            n_sh, xg_sh, goal_sh = shots_after(l["match_id"], l["period"], l["timestamp_seconds"], l["team"], False)
            key = f"D|{l['event_id']}"
            lay[key] = {**L, "snap": s, "after": after}
            rows.append({"clave": key, "fase": "Defensiva", "quien": owner, "match_id": l["match_id"], "equipo_evento": l["team"],
                         "jugador": l["player"], "minuto": l["minuto_juego"], "x": l["location_x"], "y": l["location_y"],
                         "acaba_en_tiro": n_sh > 0, "xg_siguiente": xg_sh, "gol_siguiente": goal_sh,
                         "carril_progresion": None, **_flat(m),
                         "seg_despues": after["seg"] if after else np.nan,
                         **{f"{k}_despues": (after["m"][k] if after else np.nan)
                            for k in ("bloque_m2", "bloque_ancho_m", "bloque_prof_m", "def_10m", "bloque_n")}})
    mom = pd.DataFrame(rows)
    return {"momentos": mom, "capas": lay, "fuente": "360", "n_frames": len(frames)}


def _flat(m: dict) -> dict:
    out = {k: v for k, v in m.items() if not isinstance(v, dict)}
    for k, v in m.get("carriles", {}).items():
        out[f"carril::{k}"] = v
    return out


def _lane_of(y) -> str | None:
    if y is None or pd.isna(y):
        return None
    return next(n for n, y0, y1 in CORRIDORS if y0 <= y < y1 or (y1 == 80 and y >= y0))


# ============================================================== agregados para los mapas
def select(mom: pd.DataFrame, fase: str, quien: str = "equipo", matches=None, player=None, only_reliable=True) -> pd.DataFrame:
    d = mom[mom["fase"].eq(fase) & mom["quien"].eq(quien)]
    if only_reliable:
        d = d[d["fiable"]]
    if matches:
        d = d[d["match_id"].isin(matches)]
    if player:
        d = d[d["jugador"].eq(player)]
    return d


def grid_rate(keys, capas: dict, num: str, den: str, invert: bool = False, min_n: int = 15):
    """Por celda: veces que se cumple `num` (o su contrario) dentro de `den` / veces que se cumple `den`.

    Ej.: num="own_att", den="ahead" → probabilidad de que el equipo que ataca controle esa celda cuando está
    por delante del balón y es visible. Devuelve (tasa, n) con forma de malla; NaN donde n < min_n.
    """
    N = np.zeros(len(GRID)); D = np.zeros(len(GRID))
    for k in keys:
        L = capas[k]; dmask = L[den]; v = L[num]
        N += (~v if invert else v) & dmask; D += dmask
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(D >= min_n, N / D, np.nan)
    return r.reshape(GX.shape), D.reshape(GX.shape)


def stack_rel(keys, capas: dict, layer: str) -> np.ndarray:
    arr = [capas[k][layer] for k in keys if len(capas[k][layer])]
    return np.vstack(arr) * YD if arr else np.empty((0, 2))


def lane_table(d: pd.DataFrame) -> pd.DataFrame:
    cols = [f"carril::{c[0]}" for c in CORRIDORS]
    used = d["carril_progresion"].value_counts() if "carril_progresion" in d else pd.Series(dtype=int)
    return pd.DataFrame({"Carril": [c[0] for c in CORRIDORS],
                         "Control medio por delante del balón (%)": [round(float(d[c].mean()), 0) if c in d and d[c].notna().any() else np.nan for c in cols],
                         "Veces carril más abierto": [int((d["carril_abierto"] == c[0]).sum()) for c in CORRIDORS],
                         "Progresiones reales por ese carril": [int(used.get(c[0], 0)) for c in CORRIDORS]})


# ============================================================== lecturas (texto + comparación)
def _fmt(v, f="{:.0f}"):
    return "—" if v is None or pd.isna(v) else f.format(v)


def readings(mom: pd.DataFrame, team: str, matches=None, player=None) -> dict:
    """Una lectura por análisis: frase, valor del equipo, valor de los rivales en la misma situación y n."""
    if mom is None or mom.empty:
        return {}
    oT, oR = select(mom, "Ofensiva", "equipo", matches, player), select(mom, "Ofensiva", "rival", matches)
    dT, dR = select(mom, "Defensiva", "equipo", matches, player), select(mom, "Defensiva", "rival", matches)
    med = lambda d, k: float(d[k].median()) if len(d) and k in d and d[k].notna().any() else np.nan
    mean = lambda d, k: float(d[k].mean()) if len(d) and k in d and d[k].notna().any() else np.nan
    pct = lambda d, cond: 100 * float(cond.mean()) if len(d) else np.nan
    who = player or team
    R = {}

    a, b = med(oT, "esp_atac_pct"), med(oR, "esp_atac_pct")
    R["O1"] = dict(valor=f"{_fmt(a)} %", rival=f"{_fmt(b)} %", n=len(oT), texto=(
        f"En el instante en que {who} recupera, controla el {_fmt(a)} % del espacio visible por delante del balón (a menos de 35 m), "
        f"unos {_fmt(med(oT, 'esp_atac_m2'))} m². Sus rivales, cuando recuperan, controlan el {_fmt(b)} %. "
        f"El mapa muestra en qué zonas ese espacio suele quedar a favor tras recuperar."))
    if len(oT):
        lt = lane_table(oT).set_index("Carril")
        best = lt["Control medio por delante del balón (%)"].idxmax()
        used = lt["Progresiones reales por ese carril"]
        real = used.idxmax() if used.sum() else None
        R["O2"] = dict(valor=best, rival=f"{_fmt(med(oR, 'carril::' + best))} %", n=len(oT), texto=(
            f"El corredor más abierto tras recuperar es «{best.lower()}» ({_fmt(lt.loc[best, 'Control medio por delante del balón (%)'])} % "
            f"bajo control propio). " + (f"La primera progresión real (pase o conducción de 10+ yardas) va más veces por «{real.lower()}» "
            f"({int(used.max())} de {int(used.sum())})." if real else "No hay progresiones registradas en la selección.")))
    a, b = med(oT, "libre_pct"), med(oR, "libre_pct")
    ia, ib = mean(oT, "atac_en_libre"), mean(oR, "atac_en_libre")
    R["O3"] = dict(valor=f"{_fmt(a)} %", rival=f"{_fmt(b)} %", n=len(oT), texto=(
        f"El {_fmt(a)} % del espacio por delante del balón (a menos de 25 m) queda a más de 8 m de cualquier defensor rival (rivales: {_fmt(b)} %). "
        f"{who} tiene de media {_fmt(ia, '{:.1f}')} atacantes dentro de esas zonas (rivales {_fmt(ib, '{:.1f}')})."))
    a, b = mean(oT, "apoyos_20m"), mean(oR, "apoyos_20m")
    la, lb = mean(oT, "lineas_libres"), mean(oR, "lineas_libres")
    R["O4"] = dict(valor=f"{_fmt(a, '{:.1f}')} apoyos", rival=f"{_fmt(b, '{:.1f}')}", n=len(oT), texto=(
        f"Quien recupera tiene {_fmt(a, '{:.1f}')} compañeros a menos de 20 m y {_fmt(la, '{:.1f}')} líneas de pase sin un rival en medio "
        f"(rivales: {_fmt(b, '{:.1f}')} y {_fmt(lb, '{:.1f}')}). De esos apoyos, {_fmt(mean(oT, 'apoyos_delante'), '{:.1f}')} están por delante "
        f"del balón y {_fmt(mean(oT, 'apoyos_detras'), '{:.1f}')} por detrás."))
    a, b = mean(oT, "atac_libres"), mean(oR, "atac_libres")
    sup = pct(oT, oT["balance"] >= 1) if len(oT) else np.nan
    R["O5"] = dict(valor=f"{_fmt(a, '{:.1f}')} libres", rival=f"{_fmt(b, '{:.1f}')}", n=len(oT), texto=(
        f"Al recuperar, {who} tiene {_fmt(a, '{:.1f}')} atacantes libres (sin defensor a 5 m) por delante del balón (rivales {_fmt(b, '{:.1f}')}) "
        f"y está en superioridad numérica cerca del balón en el {_fmt(sup)} % de las recuperaciones. "
        f"El {_fmt(pct(oT, oT['acaba_en_tiro']) if len(oT) else np.nan)} % de sus recuperaciones termina en remate en menos de 15 s."))

    a, b = mean(dT, "def_10m"), mean(dR, "def_10m")
    ca, cb = med(dT, "celda_poseedor_m2"), med(dR, "celda_poseedor_m2")
    R["D1"] = dict(valor=f"{_fmt(ca)} m²", rival=f"{_fmt(cb)} m²", n=len(dT), texto=(
        f"En el instante de la pérdida, {team} tiene {_fmt(a, '{:.1f}')} jugadores a menos de 10 m del balón y {_fmt(mean(dT, 'def_5m'), '{:.1f}')} a menos de 5 m "
        f"(sin contar al que lo pierde); "
        f"el rival que recibe dispone de {_fmt(ca)} m² propios (cuando pierden sus rivales: {_fmt(b, '{:.1f}')} jugadores y {_fmt(cb)} m²). "
        f"Menos metros para el poseedor = presión tras pérdida más eficaz."))
    a, b = med(dT, "central_def_pct"), med(dR, "central_def_pct")
    R["D2"] = dict(valor=f"{_fmt(a)} %", rival=f"{_fmt(b)} %", n=len(dT), texto=(
        f"Tras perder, {team} controla el {_fmt(a)} % del carril central entre el balón y su portería (rivales {_fmt(b)} %). "
        f"El mapa muestra qué tramos del centro protege y cuáles quedan para el rival."))
    a, b = med(dT, "libre_pct"), med(dR, "libre_pct")
    R["D3"] = dict(valor=f"{_fmt(a)} %", rival=f"{_fmt(b)} %", n=len(dT), texto=(
        f"Tras la pérdida, el {_fmt(a)} % del espacio entre el balón y la portería de {team} (a menos de 25 m del balón) queda a más de 8 m de sus jugadores "
        f"(cuando pierden sus rivales: {_fmt(b)} %). Son las zonas por las que el rival puede salir con ventaja."))
    a, b = mean(dT, "coberturas"), mean(dR, "coberturas")
    zero = pct(dT, dT["coberturas"].eq(0)) if len(dT) else np.nan
    R["D4"] = dict(valor=f"{_fmt(a, '{:.1f}')}", rival=f"{_fmt(b, '{:.1f}')}", n=len(dT), texto=(
        f"El jugador de {team} más cercano al balón tiene {_fmt(a, '{:.1f}')} compañeros cubriéndole a su espalda (a < 15 m) "
        f"(rivales {_fmt(b, '{:.1f}')}). En el {_fmt(zero)} % de las pérdidas sale a presionar sin ninguna cobertura."))
    pair = dT.dropna(subset=["bloque_m2_despues"]) if len(dT) else dT
    pair = pair[(pair["bloque_n"] >= 4) & (pair["bloque_n_despues"] >= 4)] if len(pair) else pair
    pr = dR.dropna(subset=["bloque_m2_despues"]) if len(dR) else dR
    pr = pr[(pr["bloque_n"] >= 4) & (pr["bloque_n_despues"] >= 4)] if len(pr) else pr
    if len(pair):
        a0, a1 = pair["bloque_m2"].median(), pair["bloque_m2_despues"].median()
        w0, w1 = pair["bloque_ancho_m"].median(), pair["bloque_ancho_m_despues"].median()
        chg = 100 * (a1 - a0) / max(a0, 1)
        rch = 100 * (pr["bloque_m2_despues"].median() - pr["bloque_m2"].median()) / max(pr["bloque_m2"].median(), 1) if len(pr) else np.nan
        R["D5"] = dict(valor=f"{chg:+.0f} %", rival=f"{_fmt(rch, '{:+.0f}')} %", n=len(pair), texto=(
            f"Entre el instante de la pérdida y unos {_fmt(pair['seg_despues'].median())} s después, el bloque de {team} cerca del balón pasa de "
            f"{_fmt(a0)} m² a {_fmt(a1)} m² ({'se compacta' if a1 < a0 else 'se abre'} un {abs(chg):.0f} %) y de {_fmt(w0)} m a {_fmt(w1)} m de ancho. "
            f"Cuando pierden sus rivales, su bloque cambia un {_fmt(rch, '{:+.0f}')} %."))
    else:
        R["D5"] = dict(valor="—", rival="—", n=0, texto="No hay suficientes pérdidas con una segunda fotografía 2–6 s después en la selección.")
    for k in R:
        R[k]["titulo"] = POINT_TITLES[k]
    return R
