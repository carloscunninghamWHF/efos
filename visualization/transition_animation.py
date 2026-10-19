"""EFOS — Animación 2D de una transición con StatsBomb 360.

Qué se anima y qué no
  * StatsBomb 360 da una FOTOGRAFÍA por evento (pase, conducción, presión, remate…), no tracking continuo,
    y no identifica a cada jugador de una fotografía a la siguiente.
  * La animación es un RECORRIDO CONTINUO en tiempo real de juego: las fotografías reales son los puntos de
    paso y, entre dos fotografías, cada jugador se desplaza en línea recta hacia su posición más probable en la
    siguiente (emparejamiento de mínima distancia total por equipo, con un tope de velocidad realista).
    Quien entra o sale del encuadre de la cámara aparece o se desvanece. El Voronoi se recalcula en cada
    fotograma. El movimiento entre fotografías es una ESTIMACIÓN, no tracking.

Orientación: el equipo analizado ataca siempre hacia la derecha (como en el resto de mapas de Transiciones).
Salidas: figura Plotly animada (portal) y GIF (presentaciones).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LENGTH, WIDTH = 120.0, 80.0
TEAM_C, RIVAL_C, NAVY, GOLD, MUTED = "#2563EB", "#B91C1C", "#0F172A", "#C89B3C", "#64748B"
EVENT_ES = {
    "Pass": "Pase", "Carry": "Conducción", "Carries": "Conducción", "Ball Receipt*": "Recepción", "Shot": "Remate",
    "Pressure": "Presión", "Ball Recovery": "Recuperación", "Interception": "Intercepción", "Dribble": "Regate",
    "Duel": "Duelo", "Clearance": "Despeje", "Block": "Bloqueo", "Dispossessed": "Pierde el balón",
    "Miscontrol": "Control fallido", "Foul Committed": "Falta", "Foul Won": "Falta recibida", "Goal Keeper": "Portero",
    "Dribbled Past": "Superado en el regate", "50/50": "Balón dividido", "Shield": "Protege el balón",
}
SKIP = {"Ball Receipt*"}          # la recepción coincide con el destino del pase: no aporta una fotografía nueva


# ============================================================== secuencia
def build_sequence(ev: pd.DataFrame, frames: dict, team: str, start_event_id: str, window: float = 15.0,
                   max_steps: int = 16) -> list[dict]:
    """Eventos con fotografía 360 desde la recuperación/pérdida hasta `window` s después (o hasta un gol)."""
    e = ev
    s = e[e["event_id"].astype(str).eq(str(start_event_id))]
    if s.empty:
        return []
    s = s.iloc[0]
    t0 = float(s["timestamp_seconds"])
    g = e[e["match_id"].eq(s["match_id"]) & e["period"].eq(s["period"])
          & pd.to_numeric(e["timestamp_seconds"], errors="coerce").between(t0, t0 + window)].copy()
    g["timestamp_seconds"] = pd.to_numeric(g["timestamp_seconds"], errors="coerce")
    g = g.sort_values(["timestamp_seconds"], kind="stable")
    steps = []
    for _, r in g.iterrows():
        if r["event_type"] in SKIP and str(r["event_id"]) != str(start_event_id):
            continue
        fr = frames.get(str(r["event_id"]))
        if fr is None or pd.isna(r.get("location_x")):
            continue
        step = _step(r, fr, team, t0)
        if step is None:
            continue
        steps.append(step)
        if (r["event_type"] == "Shot" and r.get("shot_outcome") == "Goal") or len(steps) >= max_steps:
            break
    return steps


def _step(r, fr: dict, team: str, t0: float) -> dict | None:
    ff = fr.get("freeze_frame") or []
    if not ff:
        return None
    flip = r["team"] != team                    # las fotografías vienen orientadas hacia el ataque del actor
    tf = (lambda x, y: (LENGTH - x, WIDTH - y)) if flip else (lambda x, y: (x, y))
    pts, is_team, actor = [], [], []
    for p in ff:
        x, y = tf(float(p["location"][0]), float(p["location"][1]))
        pts.append((x, y)); actor.append(bool(p.get("actor")))
        is_team.append(bool(p.get("teammate")) == (r["team"] == team))   # teammate es relativo al actor
    bx, by = tf(float(r["location_x"]), float(r["location_y"]))
    ex, ey = r.get("end_location_x"), r.get("end_location_y")
    end = tf(float(ex), float(ey)) if r["event_type"] in ("Pass", "Carry", "Carries", "Shot") and pd.notna(ex) and pd.notna(ey) else (bx, by)
    va = fr.get("visible_area")
    vis = None
    if va and len(va) >= 6:
        v = np.array(va, float).reshape(-1, 2)
        vis = np.array([tf(x, y) for x, y in v])
    who = "" if pd.isna(r.get("player")) else str(r["player"])
    sec = float(r["timestamp_seconds"]) - t0
    label = f"+{sec:.1f} s · {EVENT_ES.get(r['event_type'], r['event_type'])}" + (f" · {who}" if who else "") + \
            (f" ({'propio' if r['team'] == team else 'rival'})")
    if r["event_type"] == "Shot":
        xg = r.get("statsbomb_xg")
        label += f" · {xg:.2f} xG" if pd.notna(xg) else ""
        label += " · GOL" if r.get("shot_outcome") == "Goal" else ""
    return {"t": sec, "label": label, "event_type": r["event_type"], "is_team_event": r["team"] == team,
            "pts": np.array(pts, float), "is_team": np.array(is_team, bool), "actor": np.array(actor, bool),
            "ball": (bx, by), "ball_end": end, "visible": vis, "player": who}


def ball_path(steps: list[dict], sub: int = 6) -> list[tuple[int, float, float]]:
    """(Compatibilidad) Fotogramas (evento, x, y) del recorrido continuo con `sub` fotogramas por segundo."""
    return [(f["k"], *f["ball"]) for f in timeline(steps, fps=sub)]


def view_x(steps: list[dict], min_width: float = 64.0) -> tuple[float, float]:
    """Encuadre horizontal: la zona por donde pasan el balón y los jugadores, con al menos media cancha."""
    xs = np.concatenate([np.r_[[s["ball"][0], s["ball_end"][0]], s["pts"][:, 0]] for s in steps])
    lo, hi = float(np.percentile(xs, 3)) - 6, float(np.percentile(xs, 97)) + 6
    bx = [v for s in steps for v in (s["ball"][0], s["ball_end"][0])]     # el balón (p. ej. un gol) siempre entra
    lo, hi = min(lo, min(bx) - 6), max(hi, max(bx) + 6)
    if hi - lo < min_width:
        c = (lo + hi) / 2; lo, hi = c - min_width / 2, c + min_width / 2
    if lo < -4: hi, lo = hi + (-4 - lo), -4
    if hi > 124: lo, hi = lo - (hi - 124), 124
    return max(lo, -4), min(hi, 124)


# ============================================================== recorrido continuo
MAX_SPEED = 8.5        # yd/s (~7,8 m/s): tope para emparejar al mismo jugador entre dos fotografías
MATCH_SLACK = 3.0      # yd de tolerancia (error de posición de la fotografía)
MIN_GAP = 0.6          # s mínimos entre dos fotografías (eventos simultáneos)
TAIL = 1.2             # s finales: el último pase/remate llega a destino y la imagen se mantiene


def _match(a: np.ndarray, b: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Parejas (i, j) jugador a jugador entre dos fotografías del mismo equipo (asignación húngara con tope)."""
    if not len(a) or not len(b):
        return np.empty(0, int), np.empty(0, int)
    from scipy.optimize import linear_sum_assignment
    d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    lim = MATCH_SLACK + MAX_SPEED * max(dt, MIN_GAP)
    i, j = linear_sum_assignment(np.where(d <= lim, d, 1e6))
    ok = d[i, j] <= lim
    return i[ok], j[ok]


def _ring(poly, n: int = 36):
    """Polígono de cámara remuestreado en n radios desde su centro (permite interpolar dos cámaras)."""
    if poly is None or len(poly) < 3:
        return None
    P = np.asarray(poly, float); c = P.mean(axis=0)
    out = []
    for th in np.linspace(0, 2 * np.pi, n, endpoint=False):
        d = np.array([np.cos(th), np.sin(th)]); best = 0.0
        for p, q in zip(P, np.roll(P, -1, axis=0)):
            e = q - p; M = np.array([[d[0], -e[0]], [d[1], -e[1]]])
            if abs(np.linalg.det(M)) < 1e-9:
                continue
            t, u = np.linalg.solve(M, p - c)
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = max(best, t)
        out.append(c + best * d)
    return np.array(out)


def _ball_at(s: dict, nxt, f: float) -> np.ndarray:
    """Balón a lo largo de origen → destino → siguiente acción, a velocidad constante."""
    pts = [np.array(s["ball"], float), np.array(s["ball_end"], float)]
    if nxt is not None:
        pts.append(np.array(nxt["ball"], float))
    seg = [np.linalg.norm(q - p) for p, q in zip(pts, pts[1:])]
    L = sum(seg)
    if L < 1e-6:
        return pts[0]
    d = f * L
    for p, q, l in zip(pts, pts[1:], seg):
        if d <= l or l == seg[-1]:
            return p + (q - p) * (min(d, l) / l if l > 0 else 0)
        d -= l
    return pts[-1]


def timeline(steps: list[dict], fps: int = 10, max_frames: int = 260) -> list[dict]:
    """Fotogramas del recorrido continuo, uniformes en tiempo de juego.

    Cada fotograma: t (s), k (evento vigente), xy (jugadores), team (bool), alpha (0–1: aparece/desaparece),
    actor (xy del que ejecuta la acción o None), ball (x, y), vis (polígono de cámara o None), label.
    """
    if not steps:
        return []
    te = [0.0]
    for s in steps[1:]:
        te.append(max(float(s["t"]) - float(steps[0]["t"]), te[-1] + MIN_GAP))
    total = te[-1] + TAIL
    fps = max(1, min(fps, int(max_frames / max(total, 1e-6))))
    rings = [_ring(s["visible"]) for s in steps]
    out = []

    def pieces(k):
        """Trayectorias del intervalo k → k+1: lista de (xy0, xy1, team, a0, a1, es_actor)."""
        s = steps[k]; n = steps[k + 1] if k + 1 < len(steps) else None
        dt = (te[k + 1] - te[k]) if n is not None else TAIL
        res = []
        for side in (True, False):
            ia = np.where(s["is_team"] == side)[0]
            A = s["pts"][ia]
            if n is None:
                for q, i in enumerate(ia):
                    res.append((A[q], A[q], side, 1.0, 1.0, bool(s["actor"][i])))
                continue
            ib = np.where(n["is_team"] == side)[0]; B = n["pts"][ib]
            mi, mj = _match(A, B, dt)
            for a, b in zip(mi, mj):
                res.append((A[a], B[b], side, 1.0, 1.0, bool(s["actor"][ia[a]])))
            for a in sorted(set(range(len(A))) - set(mi.tolist())):
                res.append((A[a], A[a], side, 1.0, 0.0, bool(s["actor"][ia[a]])))
            for b in sorted(set(range(len(B))) - set(mj.tolist())):
                res.append((B[b], B[b], side, 0.0, 1.0, False))
        return res

    for k, s in enumerate(steps):
        nxt = steps[k + 1] if k + 1 < len(steps) else None
        t0, t1 = te[k], (te[k + 1] if nxt is not None else total)
        nf = max(2, int(round((t1 - t0) * fps)))
        tr = pieces(k)
        P0 = np.array([p[0] for p in tr]).reshape(-1, 2); P1 = np.array([p[1] for p in tr]).reshape(-1, 2)
        side = np.array([p[2] for p in tr], bool)
        a0 = np.array([p[3] for p in tr]); a1 = np.array([p[4] for p in tr]); act = np.array([p[5] for p in tr], bool)
        r0, r1 = rings[k], (rings[k + 1] if nxt is not None else rings[k])
        if r0 is None: r0 = r1
        if r1 is None: r1 = r0
        tail_ball = nxt is None
        for q in range(nf if nxt is not None else nf + 1):
            f = q / nf
            xy = P0 + f * (P1 - P0)
            alpha = a0 + f * (a1 - a0)
            if tail_ball:                                       # el último pase/remate llega a destino y se queda
                g = min(1.0, f * TAIL / 0.8)
                ball = np.array(s["ball"]) + g * (np.array(s["ball_end"]) - np.array(s["ball"]))
            else:
                ball = _ball_at(s, nxt, f)
            vis = None if r0 is None else r0 + f * (r1 - r0)
            out.append({"t": t0 + f * (t1 - t0), "k": k, "xy": xy, "team": side, "alpha": alpha,
                        "actor": xy[act][0] if act.any() and f < .75 else None,
                        "ball": (float(ball[0]), float(ball[1])), "vis": vis, "label": s["label"]})
    return out


# ============================================================== Voronoi de un fotograma
def _voronoi(pts: np.ndarray) -> list[np.ndarray]:
    from intelligence.transition_voronoi import voronoi_polygons
    return voronoi_polygons(pts) if len(pts) >= 2 else []


def _frame_voronoi(fr: dict) -> list[tuple[np.ndarray, bool]]:
    """Voronoi de los jugadores presentes (alpha ≥ 0,5) del fotograma, sin puntos duplicados."""
    keep = np.where(fr["alpha"] >= .5)[0]
    P = np.clip(fr["xy"][keep], [0.05, 0.05], [LENGTH - .05, WIDTH - .05])
    sel = []
    for i, p in enumerate(P):
        if all(np.linalg.norm(p - P[j]) > .15 for j in sel):
            sel.append(i)
    if len(sel) < 2:
        return []
    try:
        polys = _voronoi(P[sel])
    except Exception:
        return []
    return [(poly, bool(fr["team"][keep[i]])) for poly, i in zip(polys, sel)]


# ============================================================== Plotly (portal)
def plotly_animation(steps: list[dict], team: str, title: str, fps: int = 10, sub_frames: int | None = None):
    """Recorrido continuo: ▶ reproduce a tiempo real de juego sin detenerse en cada evento (▶▶ al doble)."""
    import plotly.graph_objects as go
    if sub_frames is not None:
        fps = sub_frames
    pitch = _pitch_shapes_plotly()
    tl = timeline(steps, fps=fps)
    fps_eff = (len(tl) - 1) / max(tl[-1]["t"], 1e-6) if len(tl) > 1 else fps

    def shapes_for(fr):
        sh = []
        for poly, is_t in _frame_voronoi(fr):
            path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in poly) + " Z"
            sh.append(dict(type="path", path=path, fillcolor=TEAM_C if is_t else RIVAL_C, opacity=.18,
                           line=dict(color="white", width=1), layer="below"))
        if fr["vis"] is not None:
            vis = " L ".join(f"{x:.2f},{y:.2f}" for x, y in fr["vis"])
            sh.append(dict(type="path", path=f"M -4,-4 L 124,-4 L 124,84 L -4,84 Z M {vis} Z",
                           fillcolor="rgba(255,255,255,0.72)", fillrule="evenodd", line=dict(width=0), layer="below"))
            sh.append(dict(type="path", path=f"M {vis} Z", line=dict(color=MUTED, width=1, dash="dot"),
                           fillcolor="rgba(0,0,0,0)", layer="below"))
        return pitch + sh

    def traces(fr):
        P, T, al = fr["xy"], fr["team"], fr["alpha"]
        ax_ = [] if fr["actor"] is None else [fr["actor"][0]]
        ay_ = [] if fr["actor"] is None else [fr["actor"][1]]
        return [
            go.Scatter(x=P[T, 0], y=P[T, 1], mode="markers", marker=dict(size=13, color=TEAM_C, opacity=al[T],
                       line=dict(color="white", width=1.5)), name=team, hoverinfo="skip"),
            go.Scatter(x=P[~T, 0], y=P[~T, 1], mode="markers", marker=dict(size=12, color=RIVAL_C, symbol="diamond",
                       opacity=al[~T], line=dict(color="white", width=1.5)), name="Rival", hoverinfo="skip"),
            go.Scatter(x=ax_, y=ay_, mode="markers", marker=dict(size=24, color="rgba(0,0,0,0)", line=dict(color=GOLD, width=3)),
                       name="Ejecuta la acción", hoverinfo="skip"),
            go.Scatter(x=[fr["ball"][0]], y=[fr["ball"][1]], mode="markers",
                       marker=dict(size=11, color="white", line=dict(color=NAVY, width=2)), name="Balón", hoverinfo="skip"),
        ]

    frames, slider_steps = [], []
    for i, fr in enumerate(tl):
        name = str(i)
        frames.append(go.Frame(name=name, data=traces(fr), layout=dict(shapes=shapes_for(fr), annotations=[_label(fr["label"])])))
        slider_steps.append(dict(method="animate", label=f"{fr['t']:.1f} s", args=[[name], dict(
            mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))]))
    dur = 1000 / fps_eff

    def play(speed):
        return dict(frame=dict(duration=dur / speed, redraw=True), fromcurrent=True, mode="immediate", transition=dict(duration=0))

    fig = go.Figure(data=traces(tl[0]), frames=frames)
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0.01, font=dict(size=16, color=NAVY)),
        shapes=shapes_for(tl[0]), annotations=[_label(tl[0]["label"])],
        xaxis=dict(range=list(view_x(steps)), visible=False), yaxis=dict(range=[84, -4], visible=False, scaleanchor="x"),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", height=620, margin=dict(l=10, r=10, t=60, b=10),
        legend=dict(orientation="h", y=-0.02, x=0, font=dict(size=11)),
        updatemenus=[dict(type="buttons", direction="left", x=0.01, y=1.06, xanchor="left", showactive=False, buttons=[
            dict(label="▶ Reproducir", method="animate", args=[None, play(1)]),
            dict(label="▶▶ x2", method="animate", args=[None, play(2)]),
            dict(label="❚❚ Pausa", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(active=0, x=0.33, len=0.66, y=1.08, ticklen=0, minorticklen=0, tickcolor="rgba(0,0,0,0)",
                      font=dict(size=1, color="rgba(0,0,0,0)"),
                      currentvalue=dict(prefix="Tiempo +", font=dict(size=11, color=NAVY)), steps=slider_steps)],
        font=dict(family="Inter, Segoe UI, sans-serif", color=NAVY),
    )
    return fig


def _label(text):
    return dict(text=text, x=0.5, y=1.0, xref="paper", yref="paper", showarrow=False, yanchor="bottom",
                font=dict(size=13, color=NAVY), bgcolor="rgba(255,255,255,.9)")


def _pitch_shapes_plotly() -> list[dict]:
    line = dict(color="#94A3B8", width=1.3)
    sh = [dict(type="rect", x0=0, y0=0, x1=120, y1=80), dict(type="line", x0=60, y0=0, x1=60, y1=80),
          dict(type="circle", x0=50, y0=30, x1=70, y1=50), dict(type="rect", x0=0, y0=18, x1=18, y1=62),
          dict(type="rect", x0=102, y0=18, x1=120, y1=62), dict(type="rect", x0=0, y0=30, x1=6, y1=50),
          dict(type="rect", x0=114, y0=30, x1=120, y1=50), dict(type="rect", x0=-2, y0=36, x1=0, y1=44),
          dict(type="rect", x0=120, y0=36, x1=122, y1=44)]
    return [{**s, "line": line, "fillcolor": "rgba(0,0,0,0)", "layer": "above"} for s in sh]


# ============================================================== GIF (presentaciones)
def gif_bytes(steps: list[dict], team: str, title: str, fps: int = 8, sub_frames: int | None = None) -> bytes:
    """GIF del recorrido continuo a tiempo real de juego (Pillow, sin dependencias externas)."""
    import tempfile
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    from matplotlib.patches import PathPatch, Polygon
    from matplotlib.path import Path as MPath
    from matplotlib.colors import to_rgba
    import action_explorer as X

    if sub_frames is not None:
        fps = sub_frames
    tl = timeline(steps, fps=fps, max_frames=200)
    fps_eff = max(1, round((len(tl) - 1) / max(tl[-1]["t"], 1e-6))) if len(tl) > 1 else fps
    lo, hi = view_x(steps)
    fig, ax, _ = X._pitch(figsize=(8.4, 6.0) if hi - lo > 90 else (7.2, 6.6))
    ax.set_xlim(lo, hi)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=NAVY, pad=16)
    lab = ax.text(0, 1.0, "", transform=ax.transAxes, fontsize=9.5, color=NAVY, va="bottom")
    clock = ax.text(.02, .03, "", transform=ax.transAxes, fontsize=8.5, color=NAVY, va="bottom", zorder=9,
                    bbox=dict(boxstyle="round,pad=.2", fc="white", ec="none", alpha=.85))
    ax.text(.98, .03, f"ataca {team} →", transform=ax.transAxes, fontsize=8.5, color=NAVY, va="bottom", ha="right", zorder=9,
            bbox=dict(boxstyle="round,pad=.2", fc="white", ec="none", alpha=.85))
    patches = []
    sc_t = ax.scatter([], [], s=110, color=TEAM_C, edgecolors="white", linewidths=1.2, zorder=5, label=team)
    sc_r = ax.scatter([], [], s=100, color=RIVAL_C, marker="D", edgecolors="white", linewidths=1.2, zorder=5, label="Rival")
    sc_a = ax.scatter([], [], s=380, facecolors="none", edgecolors=GOLD, linewidths=2.4, zorder=6, label="Ejecuta la acción")
    sc_b = ax.scatter([], [], s=80, color="white", edgecolors=NAVY, linewidths=1.8, zorder=7, label="Balón")
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.01), ncol=4, frameon=False, fontsize=8)
    outer = np.array([[-4, -4], [124, -4], [124, 84], [-4, 84], [-4, -4]], float)
    empty = np.empty((0, 2))

    def draw(i):
        fr = tl[i]
        for p in patches:
            p.remove()
        patches.clear()
        for poly, is_t in _frame_voronoi(fr):
            pg = Polygon(poly, closed=True, facecolor=TEAM_C if is_t else RIVAL_C, alpha=.18, edgecolor="white", lw=1, zorder=1.5)
            ax.add_patch(pg); patches.append(pg)
        if fr["vis"] is not None:
            inner = np.vstack([fr["vis"], fr["vis"][:1]])[::-1]
            codes = [MPath.MOVETO] + [MPath.LINETO] * (len(outer) - 2) + [MPath.CLOSEPOLY] + \
                    [MPath.MOVETO] + [MPath.LINETO] * (len(inner) - 2) + [MPath.CLOSEPOLY]
            pg = PathPatch(MPath(np.vstack([outer, inner]), codes), facecolor="white", alpha=.72, lw=0, zorder=1.7)
            ax.add_patch(pg); patches.append(pg)
            pg = Polygon(fr["vis"], closed=True, fill=False, edgecolor=MUTED, lw=1, ls=":", zorder=1.8)
            ax.add_patch(pg); patches.append(pg)
        P, T, al = fr["xy"], fr["team"], fr["alpha"]
        for sc, m, col in ((sc_t, T, TEAM_C), (sc_r, ~T, RIVAL_C)):
            sc.set_offsets(P[m] if m.any() else empty)
            if m.any():
                c = np.array([to_rgba(col, a) for a in al[m]]); sc.set_facecolors(c)
                sc.set_edgecolors(np.array([to_rgba("white", a) for a in al[m]]))
        sc_a.set_offsets(empty if fr["actor"] is None else [fr["actor"]])
        sc_b.set_offsets([fr["ball"]])
        lab.set_text(fr["label"]); clock.set_text(f"+{fr['t']:.1f} s")
        return []

    seq = list(range(len(tl))) + [len(tl) - 1] * fps_eff         # 1 s de pausa final antes de repetir
    anim = FuncAnimation(fig, draw, frames=seq, interval=1000 / fps_eff, blit=False)
    with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
        anim.save(tmp.name, writer=PillowWriter(fps=fps_eff), dpi=80)
        data = Path(tmp.name).read_bytes()
    Path(tmp.name).unlink(missing_ok=True)
    plt.close(fig)
    return data


def snapshot_figure(step: dict, team: str, show_voronoi: bool = False):
    """One *observed* StatsBomb 360 freeze-frame. No interpolated locations.

    The Voronoi is a geometric nearest-neighbour diagram from visible player
    positions ONLY, and is visually masked outside StatsBomb's visible area.
    It does not measure actual control, interceptability or hidden players.
    """
    import plotly.graph_objects as go
    pts = step["pts"]
    sides = step["is_team"]
    visible = step.get("visible")
    extra=[]
    # Show diagrams only with multiple players on BOTH sides and a valid camera mask.
    if show_voronoi and visible is not None and len(visible) >= 3 and sides.sum() >= 2 and (~sides).sum() >= 2:
        for poly, side in zip(_voronoi(pts), sides):
            if len(poly) < 3:
                continue
            path="M " + " L ".join(f"{x:.2f},{y:.2f}" for x,y in poly) + " Z"
            extra.append(dict(type='path',path=path,fillcolor=TEAM_C if side else RIVAL_C,
                              opacity=.17,line=dict(width=0),layer='below'))
    if visible is not None and len(visible) >= 3:
        p=" L ".join(f"{x:.2f},{y:.2f}" for x,y in visible)
        extra.append(dict(type='path',path=f'M -4,-4 L 124,-4 L 124,84 L -4,84 Z M {p} Z',
                          fillcolor='rgba(255,255,255,0.81)',fillrule='evenodd',
                          line=dict(width=0),layer='below'))
        extra.append(dict(type='path',path=f'M {p} Z',fillcolor='rgba(0,0,0,0)',
                          line=dict(width=1,color=MUTED,dash='dot'),layer='below'))
    fig=go.Figure()
    for side,label,color,sym in [(True,team,TEAM_C,'circle'),(False,'Rival',RIVAL_C,'diamond')]:
        xy=pts[sides == side]
        fig.add_trace(go.Scatter(x=xy[:,0],y=xy[:,1],mode='markers',name=label,
            marker=dict(color=color,symbol=sym,size=12,line=dict(width=1.5,color='white')),hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=[step['ball'][0]],y=[step['ball'][1]],mode='markers',
        name='Balón · evento registrado',marker=dict(color='white',size=13,line=dict(color=NAVY,width=2))))
    fig.update_layout(shapes=_pitch_shapes_plotly()+extra,
        xaxis=dict(range=list(view_x([step])),visible=False),
        yaxis=dict(range=[84,-4],visible=False,scaleanchor='x'),
        height=490,plot_bgcolor='#F8FAFC',paper_bgcolor='white',
        margin=dict(l=10,r=10,t=25,b=25),legend=dict(orientation='h',y=-.05),
        annotations=[_label(step['label'])])
    return fig
