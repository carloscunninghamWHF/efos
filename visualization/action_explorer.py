"""EFOS — Explorador de acciones sobre el campo (mplsoccer).

Lógica pura (sin Streamlit) para:
  * catálogos de acciones por fase: ataque organizado, defensa organizada y transiciones;
  * filtros colectivo / individual y por partido(s);
  * un campo por acción (flechas, trayectorias o puntos) y mapas de calor;
  * valor acumulado: OBV (valor de las acciones) y xG (probabilidad de gol) por minuto o por partido;
  * balón parado: tipo de ejecución, ejecutor, rematador y trayectoria;
  * alineaciones por dibujo táctico.

Coordenadas StatsBomb 120×80; el equipo analizado ataca siempre hacia la derecha.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

try:
    from mplsoccer import Pitch, VerticalPitch
except Exception:  # pragma: no cover - mplsoccer está en requirements
    Pitch = VerticalPitch = None

NAVY, BLUE, GOLD, RED, GREEN, GREY = "#0F172A", "#2563EB", "#C89B3C", "#B91C1C", "#15803D", "#94A3B8"
BG, LINE = "#F8FAFC", "#CBD5E1"
SET_PIECE_PASS_TYPES = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
LOSS_PASS = {"Incomplete", "Out", "Pass Offside", "Unknown"}
RECOVERY_TYPES = {"Ball Recovery", "Interception"}
MAX_DRAWN = 450


# ============================================================ utilidades
def _num(s):
    return pd.to_numeric(s, errors="coerce")


def prepare(events: pd.DataFrame) -> pd.DataFrame:
    """Columnas numéricas y minuto de juego; columnas opcionales vacías si faltan."""
    e = events.copy()
    for c in ("location_x", "location_y", "end_location_x", "end_location_y", "statsbomb_xg",
              "obv_total_net", "timestamp_seconds", "pass_length", "minute", "second", "period", "possession"):
        e[c] = _num(e[c]) if c in e else np.nan
    for c in ("type_name", "outcome_name", "pass_outcome", "play_pattern_name", "player", "pass_recipient_name",
              "shot_outcome", "technique_name", "counterpress", "player_position_name"):
        if c not in e:
            e[c] = np.nan
    m = e["minute"].copy()
    second_half = e["period"].eq(2)
    if second_half.any() and m[second_half].median() < 45:
        m = m.where(~second_half, m + 45)
    e["minuto_juego"] = m + e["second"].fillna(0) / 60
    e["_cp"] = e["counterpress"].astype(str).str.lower().isin(["true", "1"])
    return e


def match_options(events: pd.DataFrame, team: str) -> list[tuple]:
    """[(match_id, «J01 · vs Rival»)] en orden de aparición."""
    e = events[events["match_id"].isin(events.loc[events["team"].eq(team), "match_id"].unique())]
    out = []
    for i, (mid, g) in enumerate(e.groupby("match_id", sort=False), start=1):
        rival = next((t for t in g["team"].dropna().unique() if t != team), "rival")
        out.append((mid, f"J{i:02d} · vs {rival}"))
    return out


def team_players(events: pd.DataFrame, team: str) -> list[str]:
    t = events[events["team"].eq(team) & events["player"].notna()]
    return t["player"].value_counts().index.tolist()


def apply_scope(df: pd.DataFrame, matches: list | None = None, player: str | None = None,
                player_col: str = "player") -> pd.DataFrame:
    d = df
    if matches:
        d = d[d["match_id"].isin(matches)]
    if player:
        d = d[d[player_col].eq(player)]
    return d


def _window_after(targets: pd.DataFrame, anchors: pd.DataFrame, seconds: float, same_possession: bool) -> pd.Series:
    """True si el evento ocurre en los `seconds` posteriores a un ancla del mismo partido y parte."""
    if targets.empty or anchors.empty:
        return pd.Series(False, index=targets.index)
    t = targets[["match_id", "period", "timestamp_seconds", "possession"]].reset_index()
    a = anchors[["match_id", "period", "timestamp_seconds", "possession"]].rename(
        columns={"timestamp_seconds": "t_anchor", "possession": "pos_anchor"})
    t = t.dropna(subset=["timestamp_seconds"]).sort_values("timestamp_seconds")
    a = a.dropna(subset=["t_anchor"]).sort_values("t_anchor")
    t["match_id"] = t["match_id"].astype(str); a["match_id"] = a["match_id"].astype(str)
    m = pd.merge_asof(t, a, left_on="timestamp_seconds", right_on="t_anchor", by=["match_id", "period"], direction="backward")
    ok = (m["timestamp_seconds"] - m["t_anchor"]).between(0, seconds)
    if same_possession:
        ok &= m["possession"].eq(m["pos_anchor"])
    res = pd.Series(False, index=targets.index)
    res.loc[m.loc[ok, "index"].values] = True
    return res


def losses(e: pd.DataFrame, team: str) -> pd.DataFrame:
    me = e[e["team"].eq(team)]
    failed = me["event_type"].eq("Pass") & me["pass_outcome"].isin(LOSS_PASS) & ~me["type_name"].isin(SET_PIECE_PASS_TYPES)
    return me[me["event_type"].isin(["Dispossessed", "Miscontrol"]) | failed]


def recoveries(e: pd.DataFrame, team: str) -> pd.DataFrame:
    me = e[e["team"].eq(team) & e["event_type"].isin(RECOVERY_TYPES)]
    return me[~me["outcome_name"].isin(["Lost In Play", "Lost Out"])]


# ============================================================ catálogos de acciones
def _progressive(d: pd.DataFrame) -> pd.Series:
    d0 = np.hypot(120 - d["location_x"], 40 - d["location_y"])
    d1 = np.hypot(120 - d["end_location_x"], 40 - d["end_location_y"])
    return (d1 <= 0.75 * d0) & (d["end_location_x"] >= 60)


def _in_box(x, y):
    return (x >= 102) & y.between(18, 62)


def attack_actions(e: pd.DataFrame, team: str) -> dict:
    """Acciones con balón en juego abierto (sin saques de balón parado)."""
    me = e[e["team"].eq(team)]
    passes = me[me["event_type"].eq("Pass") & ~me["type_name"].isin(SET_PIECE_PASS_TYPES)]
    ok = passes["pass_outcome"].isna()
    carry = "Carries" if me["event_type"].eq("Carries").any() else "Carry"
    carries = me[me["event_type"].eq(carry)]
    carries = carries[np.hypot(carries["end_location_x"] - carries["location_x"], carries["end_location_y"] - carries["location_y"]) >= 5]
    shots = me[me["event_type"].eq("Shot") & me["type_name"].ne("Penalty")]
    return {
        "Pases": ("arrows", passes),
        "Pases progresivos": ("arrows", passes[ok & _progressive(passes)]),
        "Pases al área": ("arrows", passes[ok & _in_box(passes["end_location_x"], passes["end_location_y"])
                                              & ~_in_box(passes["location_x"], passes["location_y"])]),
        "Conducciones": ("lines", carries),
        "Regates": ("points", me[me["event_type"].eq("Dribble")]),
        "Tiros": ("shots", shots),
    }


def defence_actions(e: pd.DataFrame, team: str) -> dict:
    me = e[e["team"].eq(team)]
    return {
        "Presiones": ("points", me[me["event_type"].eq("Pressure")]),
        "Recuperaciones": ("points", me[me["event_type"].eq("Ball Recovery")]),
        "Intercepciones": ("points", me[me["event_type"].eq("Interception")]),
        "Duelos": ("points", me[me["event_type"].eq("Duel")]),
        "Bloqueos": ("points", me[me["event_type"].eq("Block")]),
        "Despejes": ("points", me[me["event_type"].eq("Clearance")]),
        "Faltas cometidas": ("points", me[me["event_type"].eq("Foul Committed")]),
    }


def transition_frames(e: pd.DataFrame, team: str) -> dict:
    """Ventanas de transición: tras recuperar (≤15 s, misma posesión) y tras perder (≤5 s)."""
    me = e[e["team"].eq(team)]
    rec, lost = recoveries(e, team), losses(e, team)
    after_rec = _window_after(me, rec, 15, same_possession=True)
    after_loss = _window_after(me, lost, 5, same_possession=False)
    opp = e[~e["team"].eq(team)]
    # tiros rivales en los 15 s posteriores a una pérdida propia
    opp_after_loss = _window_after(opp, lost, 15, same_possession=False)
    carry = "Carries" if me["event_type"].eq("Carries").any() else "Carry"
    off = me[after_rec & ~me.index.isin(rec.index)]
    return {
        "off": off, "def_win": me[after_loss & ~me.index.isin(lost.index)], "rec": rec, "lost": lost,
        "opp_shots_after_loss": opp[opp_after_loss & opp["event_type"].eq("Shot")],
        "carry": carry,
    }


def transition_actions(e: pd.DataFrame, team: str, tf: dict | None = None) -> dict:
    tf = tf or transition_frames(e, team)
    off, dw = tf["off"], tf["def_win"]
    rec_to_shot = pd.Series(False, index=tf["rec"].index)
    shots_tr = off[off["event_type"].eq("Shot")]
    # recuperaciones que terminan en tiro: ancla cuyo tiro posterior está en la misma posesión
    if len(shots_tr):
        key = set(zip(shots_tr["match_id"].astype(str), shots_tr["possession"]))
        rec_to_shot = pd.Series([(str(m), p) in key for m, p in zip(tf["rec"]["match_id"], tf["rec"]["possession"])], index=tf["rec"].index)
    return {
        "Pérdidas": ("points", tf["lost"]),
        "Contrapresión (≤5 s tras perder)": ("points", dw[dw["event_type"].eq("Pressure")]),
        "Recuperación tras perder (≤5 s)": ("points", dw[dw["event_type"].isin(RECOVERY_TYPES)]),
        "Recuperaciones que inician transición": ("points", tf["rec"]),
        "Recuperaciones que acaban en tiro": ("points", tf["rec"][rec_to_shot]),
        "Pases en transición ofensiva (≤15 s)": ("arrows", off[off["event_type"].eq("Pass")]),
        "Conducciones en transición ofensiva (≤15 s)": ("lines", off[off["event_type"].eq(tf["carry"])]),
        "Tiros en transición": ("shots", shots_tr),
    }


# ============================================================ dibujo
def _pitch(half: bool = False, figsize=(8.2, 5.6)):
    if Pitch is None:  # pragma: no cover
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_xlim(60 if half else 0, 120); ax.set_ylim(80, 0); ax.axis("off")
        return fig, ax, None
    pitch = Pitch(pitch_type="statsbomb", pitch_color=BG, line_color="#94A3B8", linewidth=1.1, half=half,
                  pad_top=4, pad_bottom=2, line_zorder=2)
    fig, ax = pitch.draw(figsize=figsize)
    return fig, ax, pitch


def _success(d: pd.DataFrame) -> pd.Series:
    """Éxito de la acción según StatsBomb (pase completado, regate/duelo ganado, etc.)."""
    et, oc = d["event_type"].to_numpy(), d["outcome_name"].astype(str).to_numpy()
    ok = np.ones(len(d), dtype=bool)
    ok = np.where(et == "Pass", d["pass_outcome"].isna().to_numpy(), ok)
    ok = np.where(et == "Dribble", oc == "Complete", ok)
    ok = np.where(et == "Duel", np.isin(oc, ["Won", "Success In Play", "Success Out"]), ok)
    ok = np.where(et == "Interception", ~np.isin(oc, ["Lost In Play", "Lost Out"]), ok)
    return pd.Series(ok, index=d.index)


def action_pitch(d: pd.DataFrame, kind: str, title: str, subtitle: str = ""):
    fig, ax, pitch = _pitch()
    d = d.dropna(subset=["location_x", "location_y"])
    n = len(d)
    drawn = d.sample(MAX_DRAWN, random_state=7) if (kind in ("arrows", "lines") and n > MAX_DRAWN) else d
    ok = _success(drawn)
    legend = []
    if pitch is not None and len(drawn):
        if kind == "arrows":
            dd = drawn.dropna(subset=["end_location_x", "end_location_y"]); okk = ok.loc[dd.index]
            for mask, col, lab in ((okk, BLUE, "Completado"), (~okk, RED, "Fallado")):
                if mask.any():
                    pitch.arrows(dd.location_x[mask], dd.location_y[mask], dd.end_location_x[mask], dd.end_location_y[mask],
                                 ax=ax, color=col, alpha=.55 if n < 150 else .3, width=1.4, headwidth=4, headlength=4)
                    legend.append(Line2D([0], [0], color=col, lw=2, label=f"{lab} ({int(mask.sum())})"))
        elif kind == "lines":
            dd = drawn.dropna(subset=["end_location_x", "end_location_y"])
            pitch.lines(dd.location_x, dd.location_y, dd.end_location_x, dd.end_location_y, ax=ax, comet=True,
                        color=GOLD, alpha=.5 if n < 150 else .3, lw=2)
            pitch.scatter(dd.end_location_x, dd.end_location_y, ax=ax, s=8, color=GOLD, alpha=.6)
        elif kind == "shots":
            xg = drawn["statsbomb_xg"].fillna(.03).clip(0, .8)
            goal = drawn["shot_outcome"].eq("Goal")
            pitch.scatter(drawn.location_x[~goal], drawn.location_y[~goal], s=25 + 500 * xg[~goal], ax=ax, color=BLUE,
                          alpha=.4, edgecolors="white", linewidth=.5)
            pitch.scatter(drawn.location_x[goal], drawn.location_y[goal], s=120 + 500 * xg[goal], ax=ax, marker="*",
                          color=GOLD, edgecolors=NAVY, linewidth=.7, zorder=5)
            legend += [Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE, markersize=8, label=f"Tiro ({int((~goal).sum())})"),
                       Line2D([0], [0], marker="*", color="w", markerfacecolor=GOLD, markeredgecolor=NAVY, markersize=13,
                              label=f"Gol ({int(goal.sum())})")]
        else:
            for mask, col, lab in ((ok, GREEN, "Con éxito"), (~ok, RED, "Sin éxito")):
                if mask.any():
                    pitch.scatter(drawn.location_x[mask], drawn.location_y[mask], ax=ax, s=26, color=col,
                                  alpha=.55 if n < 300 else .3, edgecolors="white", linewidth=.3)
                    if not ok.all():
                        legend.append(Line2D([0], [0], marker="o", color="w", markerfacecolor=col, markersize=7,
                                             label=f"{lab} ({int(mask.sum())})"))
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=16)
    note = f"{n:,} acciones" + (f" · se dibujan {MAX_DRAWN} al azar" if len(drawn) < n else "") + " · ataque →"
    ax.text(0, 1.0, (subtitle + " · " if subtitle else "") + note, transform=ax.transAxes, fontsize=8.5, color="#64748B", va="bottom")
    if legend:
        ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(.5, -.06), ncol=len(legend), frameon=False, fontsize=8.5)
    return fig


def heatmap(d: pd.DataFrame, title: str, subtitle: str = "", cmap: str = "Blues"):
    """Mapa de calor suavizado (malla 24×16 con filtro gaussiano) + % por tercio."""
    fig, ax, pitch = _pitch()
    d = d.dropna(subset=["location_x", "location_y"])
    if pitch is not None and len(d):
        bs = pitch.bin_statistic(d.location_x, d.location_y, statistic="count", bins=(24, 16), normalize=True)
        try:
            from scipy.ndimage import gaussian_filter
            bs["statistic"] = gaussian_filter(bs["statistic"], 1.1)
        except Exception:
            pass
        pitch.heatmap(bs, ax=ax, cmap=cmap, edgecolors=None, alpha=.92)
        for (a, b), name in zip(((0, 40), (40, 80), (80, 120)), ("Tercio propio", "Tercio medio", "Último tercio")):
            share = 100 * d["location_x"].between(a, b, inclusive="left" if b < 120 else "both").mean()
            ax.text((a + b) / 2, 82.5, f"{name}: {share:.0f} %", ha="center", va="top", fontsize=9, color=NAVY)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=16)
    ax.text(0, 1.0, (subtitle + " · " if subtitle else "") + f"{len(d):,} acciones · ataque →",
            transform=ax.transAxes, fontsize=8.5, color="#64748B", va="bottom")
    return fig


# ============================================================ valor acumulado
# OBV (On-Ball Value): cuánto cambia la probabilidad de marcar menos la de recibir gol con cada acción.
# xG: probabilidad de gol de cada remate. Ambos se suman a lo largo de un partido o de un torneo.
def value_by_minute(obv_df: pd.DataFrame, xg_df: pd.DataFrame) -> pd.DataFrame:
    a = pd.DataFrame({"minuto": obv_df["minuto_juego"], "obv": obv_df["obv_total_net"].fillna(0), "xg": 0.0})
    b = pd.DataFrame({"minuto": xg_df["minuto_juego"], "obv": 0.0, "xg": xg_df["statsbomb_xg"].fillna(0)})
    d = pd.concat([a, b]).dropna(subset=["minuto"]).sort_values("minuto")
    return pd.DataFrame({"minuto": d["minuto"], "OBV acumulado": d["obv"].cumsum(), "xG acumulado": d["xg"].cumsum()})


def value_by_match(obv_df: pd.DataFrame, xg_df: pd.DataFrame, labels: dict) -> pd.DataFrame:
    o = obv_df.groupby("match_id")["obv_total_net"].sum()
    x = xg_df.groupby("match_id")["statsbomb_xg"].sum()
    ids = [m for m in labels if m in set(o.index) | set(x.index)]
    return pd.DataFrame({"match_id": ids, "partido": [labels[m] for m in ids],
                         "OBV": [float(o.get(m, 0)) for m in ids], "xG": [float(x.get(m, 0)) for m in ids]})


def value_by_player(obv_df: pd.DataFrame, xg_df: pd.DataFrame, top: int = 12) -> pd.DataFrame:
    o = obv_df.groupby("player")["obv_total_net"].sum()
    x = xg_df.groupby("player")["statsbomb_xg"].sum()
    d = pd.DataFrame({"OBV": o, "xG": x}).fillna(0)
    return d.sort_values("OBV", ascending=False).head(top).reset_index().rename(columns={"index": "Jugador", "player": "Jugador"})


# ============================================================ balón parado
SET_PIECE_KINDS = ["Tiro de esquina", "Tiro libre directo", "Tiro libre indirecto", "Tiro libre lateral",
                   "Tiro libre lejano", "Penalti"]
SP_COLORS = {"Tiro de esquina": BLUE, "Tiro libre directo": RED, "Tiro libre indirecto": GOLD,
             "Tiro libre lateral": GREEN, "Tiro libre lejano": "#7C3AED", "Penalti": NAVY}


def classify_set_piece(row) -> str | None:
    et, tn, x, y = row["event_type"], row["type_name"], row["location_x"], row["location_y"]
    if et == "Shot":
        return {"Penalty": "Penalti", "Free Kick": "Tiro libre directo"}.get(tn)
    if et != "Pass":
        return None
    if tn == "Corner":
        return "Tiro de esquina"
    if tn == "Free Kick" and not pd.isna(x):
        if x >= 80 and (y < 18 or y > 62):
            return "Tiro libre lateral"
        if x >= 80:
            return "Tiro libre indirecto"
        if x >= 60:
            return "Tiro libre lejano"
    return None


def set_piece_table(e: pd.DataFrame, team: str, against: bool = False, link_seconds: float = 10.0) -> pd.DataFrame:
    """Una fila por ejecución: tipo, ejecutor, trayectoria, receptor y rematador (si hubo remate)."""
    side = e[~e["team"].eq(team)] if against else e[e["team"].eq(team)]
    cand = side[side["event_type"].isin(["Pass", "Shot"]) & side["type_name"].isin(["Corner", "Free Kick", "Penalty"])].copy()
    if cand.empty:
        return pd.DataFrame(columns=["tipo"])
    cand["tipo"] = cand.apply(classify_set_piece, axis=1)
    cand = cand.dropna(subset=["tipo"])
    shots = side[side["event_type"].eq("Shot")].dropna(subset=["timestamp_seconds"])
    rows = []
    for idx, r in cand.iterrows():
        rem, sx, sy, xg, goal = None, np.nan, np.nan, np.nan, False
        if r["event_type"] == "Shot":
            rem, sx, sy, xg, goal = r["player"], r["location_x"], r["location_y"], r["statsbomb_xg"], r["shot_outcome"] == "Goal"
        elif not pd.isna(r["timestamp_seconds"]):
            s = shots[shots["match_id"].eq(r["match_id"]) & shots["period"].eq(r["period"]) & shots["possession"].eq(r["possession"])
                      & shots["timestamp_seconds"].between(r["timestamp_seconds"], r["timestamp_seconds"] + link_seconds)]
            if len(s):
                f = s.iloc[0]
                rem, sx, sy, xg, goal = f["player"], f["location_x"], f["location_y"], f["statsbomb_xg"], f["shot_outcome"] == "Goal"
        rows.append({"match_id": r["match_id"], "team": r["team"], "tipo": r["tipo"], "ejecutor": r["player"],
                     "minuto": r["minuto_juego"], "x": r["location_x"], "y": r["location_y"],
                     "end_x": r["end_location_x"], "end_y": r["end_location_y"],
                     "receptor": r["pass_recipient_name"] if r["event_type"] == "Pass" else None,
                     "completado": bool(pd.isna(r["pass_outcome"])) if r["event_type"] == "Pass" else True,
                     "comba": r["technique_name"], "rematador": rem, "remate_x": sx, "remate_y": sy,
                     "xg": xg, "gol": bool(goal), "es_tiro_directo": r["event_type"] == "Shot"})
    return pd.DataFrame(rows)


def set_piece_pitch(sp: pd.DataFrame, title: str, subtitle: str = ""):
    if VerticalPitch is not None:
        pitch = VerticalPitch(pitch_type="statsbomb", half=True, pitch_color=BG, line_color="#94A3B8", linewidth=1.1,
                              line_zorder=2, pad_bottom=2, pad_top=3)
        fig, ax = pitch.draw(figsize=(7.4, 6.6))
    else:  # pragma: no cover
        fig, ax, pitch = _pitch(half=True, figsize=(8.2, 6.4))
    legend = []
    if pitch is not None and len(sp):
        for kind, g in sp.groupby("tipo"):
            col = SP_COLORS.get(kind, GREY)
            dl = g[~g["es_tiro_directo"]].dropna(subset=["end_x", "end_y"])
            if len(dl):
                pitch.lines(dl.x, dl.y, dl.end_x, dl.end_y, ax=ax, comet=True, color=col, lw=2, alpha=.55 if len(dl) < 80 else .3)
                pitch.scatter(dl.end_x, dl.end_y, ax=ax, s=14, color=col, alpha=.7)
            ds = g[g["es_tiro_directo"]]
            if len(ds):
                pitch.lines(ds.x, ds.y, np.full(len(ds), 120.0), np.full(len(ds), 40.0), ax=ax, color=col, lw=1.2, alpha=.4, linestyle="--")
                pitch.scatter(ds.x, ds.y, ax=ax, s=40, color=col, edgecolors="white", zorder=4)
            legend.append(Line2D([0], [0], color=col, lw=3, label=f"{kind} ({len(g)})"))
        rem = sp.dropna(subset=["remate_x", "remate_y"])
        if len(rem):
            goal = rem["gol"]
            pitch.scatter(rem.remate_x[~goal], rem.remate_y[~goal], ax=ax, s=60 + 900 * rem.xg[~goal].fillna(.03).clip(0, .8),
                          facecolors="none", edgecolors=NAVY, linewidth=1.2, zorder=5)
            pitch.scatter(rem.remate_x[goal], rem.remate_y[goal], ax=ax, s=260, marker="*", color=GOLD, edgecolors=NAVY,
                          linewidth=.7, zorder=6)
            legend.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="none", markeredgecolor=NAVY, markersize=9,
                                 label=f"Remate ({len(rem)}; {int(goal.sum())} gol)"))
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=16)
    ax.text(0, 1.0, (subtitle + " · " if subtitle else "") + f"{len(sp):,} ejecuciones · se ataca hacia la portería de arriba",
            transform=ax.transAxes, fontsize=8.5, color="#64748B", va="bottom")
    if legend:
        ax.legend(handles=legend, loc="upper center", bbox_to_anchor=(.5, -.01), ncol=2, frameon=False, fontsize=8.5)
    return fig


# ============================================================ alineaciones por dibujo
POS_XY = {
    "Goalkeeper": (5, 40),
    "Right Back": (32, 70), "Right Center Back": (23, 57), "Center Back": (27, 40), "Left Center Back": (23, 23), "Left Back": (32, 10),
    "Right Wing Back": (46, 72), "Left Wing Back": (46, 8),
    "Right Defensive Midfield": (42, 50), "Center Defensive Midfield": (40, 40), "Left Defensive Midfield": (42, 30),
    "Right Center Midfield": (58, 54), "Center Center Midfield": (56, 40), "Left Center Midfield": (58, 26),
    "Right Midfield": (64, 70), "Left Midfield": (64, 10),
    "Right Attacking Midfield": (76, 56), "Center Attacking Midfield": (74, 40), "Left Attacking Midfield": (76, 24),
    "Right Wing": (86, 70), "Left Wing": (86, 10),
    "Right Center Forward": (98, 50), "Center Forward": (100, 40), "Left Center Forward": (98, 30), "Secondary Striker": (88, 40),
}


POS_ABBR = {
    "Goalkeeper": "POR", "Right Back": "LD", "Left Back": "LI", "Right Center Back": "DFC", "Center Back": "DFC",
    "Left Center Back": "DFC", "Right Wing Back": "CAD", "Left Wing Back": "CAI", "Right Defensive Midfield": "MCD",
    "Center Defensive Midfield": "MCD", "Left Defensive Midfield": "MCD", "Right Center Midfield": "MC",
    "Center Center Midfield": "MC", "Left Center Midfield": "MC", "Right Midfield": "MD", "Left Midfield": "MI",
    "Right Attacking Midfield": "MP", "Center Attacking Midfield": "MP", "Left Attacking Midfield": "MP",
    "Right Wing": "ED", "Left Wing": "EI", "Right Center Forward": "DC", "Center Forward": "DC",
    "Left Center Forward": "DC", "Secondary Striker": "SD",
}


def lineups_by_formation(starters: dict, formation_fn) -> dict:
    """{dibujo: {"partidos": n, "slots": [(posición, jugador, veces, alternativa)]}} a partir de los titulares por partido."""
    groups: dict[str, list] = {}
    for mid, pos in starters.items():
        if len(pos) >= 10:
            shape, _ = formation_fn(list(pos.values()))
            groups.setdefault(shape, []).append(pos)
    out = {}
    for shape, xis in groups.items():
        n = len(xis)
        pos_count = Counter(p for xi in xis for p in set(xi.values()))
        slots = []
        for position, c in pos_count.most_common():
            if c / n < 0.5 or position not in POS_XY:
                continue
            players = Counter(pl for xi in xis for pl, p in xi.items() if p == position)
            top = players.most_common(2)
            slots.append((position, top[0][0], top[0][1], top[1][0] if len(top) > 1 else None))
        out[shape] = {"partidos": n, "slots": slots}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["partidos"]))


def lineup_pitch(shape: str, info: dict, team: str, name_fn=lambda s: s, position_es: dict | None = None):
    fig, ax, pitch = _pitch(figsize=(9.5, 6.4))
    position_es = position_es or {}
    for position, player, times, alt in info["slots"]:
        x, y = POS_XY[position]
        if pitch is not None:
            pitch.scatter(x, y, ax=ax, s=900, color=NAVY, edgecolors=GOLD, linewidth=2, zorder=3)
        ax.text(x, y, POS_ABBR.get(position, position[:3].upper()), ha="center", va="center", fontsize=7.5,
                color="white", fontweight="bold", zorder=4)
        ax.text(x, y + 5.6, name_fn(player), ha="center", va="top", fontsize=9.5, color=NAVY, fontweight="bold", zorder=4)
        ax.text(x, y + 8.6, f"{times}/{info['partidos']} partidos" + (f" · alt. {name_fn(alt)}" if alt else ""),
                ha="center", va="top", fontsize=7, color="#475569", zorder=4)
    ax.set_title(f"{team} · {shape}", loc="left", fontsize=14, fontweight="bold", color=NAVY, pad=16)
    ax.text(0, 1.0, f"Once más repetido en los {info['partidos']} partidos que empezó con este dibujo · ataque →",
            transform=ax.transAxes, fontsize=8.5, color="#64748B", va="bottom")
    return fig


# ============================================================ momentos clave por partido
PHASES = ["Ataque organizado", "Defensa organizada", "Transiciones", "Balón parado"]
ACTION_ES = {"Pass": "Pase", "Carries": "Conducción", "Carry": "Conducción", "Dribble": "Regate", "Interception": "Intercepción",
             "Block": "Bloqueo", "Clearance": "Despeje", "Duel": "Duelo", "Ball Recovery": "Recuperación", "Pressure": "Presión"}
SP_PATTERNS = {"From Corner", "From Free Kick", "From Throw In"}


def _mm(v) -> str:
    return "—" if pd.isna(v) else f"{int(v)}′"


def key_moments(e: pd.DataFrame, team: str, match_id, tf: dict | None = None, sp_for: pd.DataFrame | None = None,
                sp_against: pd.DataFrame | None = None, per_phase: int = 3) -> pd.DataFrame:
    """Los momentos más importantes de un partido, por fase y a favor / en contra.

    Importancia: gol > mayor xG > mayor valor de la acción (OBV). Cada momento indica minuto, jugador y qué observar.
    """
    mid = str(match_id)
    g = e[e["match_id"].astype(str).eq(mid)]
    tf = tf or transition_frames(e, team)
    me, opp = g[g["team"].eq(team)], g[~g["team"].eq(team)]
    sp_shot = g["event_type"].eq("Shot") & (g["play_pattern_name"].isin(SP_PATTERNS) | g["type_name"].isin(["Penalty", "Free Kick"]))
    sp_idx = set(g.index[sp_shot])                      # prioridad: balón parado > transición > ataque/defensa
    in_tr = (set(tf["off"].index) | set(tf["opp_shots_after_loss"].index)) - sp_idx
    rows = []

    def add(phase, side, minute, player, text, xg=np.nan, obv=np.nan, goal=False, x=np.nan, y=np.nan):
        imp = (10 if goal else 0) + (0 if pd.isna(xg) else 3 * xg) + (0 if pd.isna(obv) else abs(obv))
        rows.append({"fase": phase, "lado": side, "minuto": minute, "jugador": player, "momento": text,
                     "xg": xg, "obv": obv, "gol": bool(goal), "x": x, "y": y, "importancia": imp})

    def is_sp(s):
        return s["play_pattern_name"].isin(SP_PATTERNS) | s["type_name"].isin(["Penalty", "Free Kick"])

    # --- Ataque organizado: remates y acciones de más valor fuera de transición y balón parado
    sh = me[me["event_type"].eq("Shot")]
    sh = sh[~is_sp(sh) & ~sh.index.isin(in_tr)]
    for _, r in sh.iterrows():
        goal = r["shot_outcome"] == "Goal"
        add("Ataque organizado", "A favor", r["minuto_juego"], r["player"],
            f"{'GOL' if goal else 'Remate'} de {r['player']} ({r['statsbomb_xg']:.2f} xG)", r["statsbomb_xg"], np.nan, goal,
            r["location_x"], r["location_y"])
    act = me[me["event_type"].isin(["Pass", "Carries", "Carry", "Dribble"]) & ~me.index.isin(in_tr)
             & ~me["type_name"].isin(SET_PIECE_PASS_TYPES)].nlargest(2, "obv_total_net")
    for _, r in act.iterrows():
        if r["obv_total_net"] > 0.05:
            add("Ataque organizado", "A favor", r["minuto_juego"], r["player"],
                f"{ACTION_ES.get(r['event_type'], r['event_type'])} de {r['player']} que suma {r['obv_total_net']:+.2f} de valor",
                np.nan, r["obv_total_net"], False, r["location_x"], r["location_y"])

    # --- Defensa organizada: ocasiones rivales en ataque posicional y acciones defensivas de más valor
    osh = opp[opp["event_type"].eq("Shot")]
    osh = osh[~is_sp(osh) & ~osh.index.isin(in_tr)]
    for _, r in osh.iterrows():
        goal = r["shot_outcome"] == "Goal"
        add("Defensa organizada", "En contra", r["minuto_juego"], r["player"],
            f"{'GOL rival' if goal else 'Ocasión rival'} de {r['player']} ({r['statsbomb_xg']:.2f} xG)", r["statsbomb_xg"], np.nan, goal,
            r["location_x"], r["location_y"])
    dfa = me[me["event_type"].isin(["Interception", "Block", "Clearance", "Duel", "Ball Recovery"])].nlargest(2, "obv_total_net")
    for _, r in dfa.iterrows():
        if r["obv_total_net"] > 0.02:
            add("Defensa organizada", "A favor", r["minuto_juego"], r["player"],
                f"{ACTION_ES.get(r['event_type'], r['event_type'])} de {r['player']} que evita peligro ({r['obv_total_net']:+.2f} de valor)",
                np.nan, r["obv_total_net"], False, r["location_x"], r["location_y"])

    # --- Transiciones: remates tras recuperar y ocasiones rivales tras perder
    off = tf["off"]; off = off[off["match_id"].astype(str).eq(mid)]
    rec = tf["rec"]; rec = rec[rec["match_id"].astype(str).eq(mid)]
    for _, r in off[off["event_type"].eq("Shot") & ~off.index.isin(sp_idx)].iterrows():
        goal = r["shot_outcome"] == "Goal"
        origin = rec[rec["possession"].eq(r["possession"])]
        rp = origin.iloc[0]["player"] if len(origin) else None
        who = (" tras recuperar él mismo el balón" if rp == r["player"] else f" tras recuperación de {rp}") if rp else " tras recuperar"
        add("Transiciones", "A favor", r["minuto_juego"], r["player"],
            f"{'GOL' if goal else 'Remate'} de {r['player']}{who} ({r['statsbomb_xg']:.2f} xG)", r["statsbomb_xg"], np.nan, goal,
            r["location_x"], r["location_y"])
    oa = tf["opp_shots_after_loss"]; oa = oa[oa["match_id"].astype(str).eq(mid)]
    lost = tf["lost"]; lost = lost[lost["match_id"].astype(str).eq(mid)]
    for _, r in oa[~oa.index.isin(sp_idx)].iterrows():
        goal = r["shot_outcome"] == "Goal"
        prev = lost[(lost["period"].eq(r["period"])) & (lost["timestamp_seconds"] <= r["timestamp_seconds"])].tail(1)
        who = f" tras pérdida de {prev.iloc[0]['player']}" if len(prev) else " tras pérdida"
        add("Transiciones", "En contra", r["minuto_juego"], r["player"],
            f"{'GOL rival' if goal else 'Ocasión rival'} de {r['player']}{who} ({r['statsbomb_xg']:.2f} xG)", r["statsbomb_xg"], np.nan, goal,
            r["location_x"], r["location_y"])

    # --- Goles en propia puerta (no son remates)
    for side, src in (("A favor", me), ("En contra", opp)):
        for _, r in src[src["event_type"].eq("Own Goal For")].iterrows():
            add("Ataque organizado" if side == "A favor" else "Defensa organizada", side, r["minuto_juego"], "",
                "GOL en propia puerta del rival" if side == "A favor" else "GOL en propia puerta", goal=True)

    # --- Balón parado: jugadas con remate, a favor y en contra
    PAT_ES = {"From Corner": "córner", "From Free Kick": "falta", "From Throw In": "saque de banda"}
    for side, src, sp in (("A favor", me, sp_for), ("En contra", opp, sp_against)):
        linked = set()
        if sp is not None and not sp.empty:
            q = sp[sp["match_id"].astype(str).eq(mid) & sp["rematador"].notna()]
            linked = {(r["rematador"], round(float(r["remate_x"]), 1), round(float(r["remate_y"]), 1)) for _, r in q.iterrows()}
        sps = src[src["event_type"].eq("Shot") & src["play_pattern_name"].isin(SP_PATTERNS) & ~src["type_name"].isin(["Penalty", "Free Kick"])]
        for _, r in sps.iterrows():
            if (r["player"], round(float(r["location_x"]), 1), round(float(r["location_y"]), 1)) in linked:
                continue
            goal = r["shot_outcome"] == "Goal"
            add("Balón parado", side, r["minuto_juego"], r["player"],
                f"{'GOL' if goal else 'Remate'} de {r['player']} en segunda jugada de {PAT_ES[r['play_pattern_name']]} ({r['statsbomb_xg']:.2f} xG)",
                r["statsbomb_xg"], np.nan, goal, r["location_x"], r["location_y"])
    for side, sp in (("A favor", sp_for), ("En contra", sp_against)):
        sp = sp if sp is not None else set_piece_table(e, team, against=(side == "En contra"))
        if sp is None or sp.empty:
            continue
        sp = sp[sp["match_id"].astype(str).eq(mid) & sp["rematador"].notna()]
        for _, r in sp.iterrows():
            lead = "GOL" if r["gol"] else "Remate"
            txt = (f"{r['tipo']}: {lead} de {r['rematador']} ({r['xg']:.2f} xG)" if r["es_tiro_directo"] else
                   f"{r['tipo']} de {r['ejecutor']} → {lead.lower() if lead == 'Remate' else lead} de {r['rematador']} ({r['xg']:.2f} xG)")
            add("Balón parado", side, r["minuto"], r["rematador"], txt, r["xg"], np.nan, r["gol"], r["remate_x"], r["remate_y"])

    d = pd.DataFrame(rows, columns=["fase", "lado", "minuto", "jugador", "momento", "xg", "obv", "gol", "x", "y", "importancia"])
    if d.empty:
        return d
    d = d.sort_values("importancia", ascending=False)
    top = d.groupby(["fase", "lado"], sort=False).head(per_phase)
    d = pd.concat([top, d[d["gol"]]]).loc[lambda x: ~x.index.duplicated()]   # los goles siempre aparecen
    d["fase"] = pd.Categorical(d["fase"], PHASES, ordered=True)
    return d.sort_values(["fase", "minuto"]).reset_index(drop=True)


def match_score(e: pd.DataFrame, team: str, match_id) -> tuple[int, int]:
    g = e[e["match_id"].astype(str).eq(str(match_id))]
    gf = int((g["team"].eq(team) & g["shot_outcome"].eq("Goal")).sum() + (g["team"].eq(team) & g["event_type"].eq("Own Goal For")).sum())
    gc = int((~g["team"].eq(team) & g["shot_outcome"].eq("Goal")).sum() + (~g["team"].eq(team) & g["event_type"].eq("Own Goal For")).sum())
    return gf, gc
