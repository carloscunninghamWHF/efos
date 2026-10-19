"""EFOS — Dibujo del diagrama de Voronoi de una transición.

Usa el campo de action_explorer (mplsoccer o, si no carga, el campo propio de EFOS). El equipo analizado
ataca siempre hacia la derecha: en las transiciones defensivas la fotografía del rival se gira 180°.
"""
from __future__ import annotations

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Polygon  # noqa: E402

import action_explorer as X  # noqa: E402
from intelligence import transition_voronoi as V  # noqa: E402

TEAM_C, RIVAL_C = "#2563EB", "#B91C1C"
GOLD, GREEN, NAVY, GREY, ORANGE = "#C89B3C", "#15803D", "#0F172A", "#94A3B8", "#EA580C"
LAYERS = ["Voronoi", "Espacio libre (≥ 8 m del defensor)", "Carriles", "Líneas de pase", "Presión y coberturas",
          "Bloque defensivo", "Recorrido desde la recuperación"]


def _tf(xy, flip):
    xy = np.asarray(xy, float).reshape(-1, 2)
    return np.column_stack([V.LENGTH - xy[:, 0], V.WIDTH - xy[:, 1]]) if flip else xy


def draw_transition(frame: dict, sit: dict, team: str, layers: set | None = None, title: str = "", subtitle: str = ""):
    layers = set(LAYERS) if layers is None else set(layers)
    flip = bool(frame.get("flip"))
    team_attacks = sit.get("lado") == "Ofensiva"
    c_att, c_def = (TEAM_C, RIVAL_C) if team_attacks else (RIVAL_C, TEAM_C)
    att, dfn, ball = frame["attackers"], frame["defenders"], np.array(frame["ball"], float)
    half = sit.get("momento") != "recuperacion"      # el remate ocurre en campo rival: basta media cancha
    fig, ax, _ = X._pitch(figsize=(7.4, 7.4) if half else (9.6, 6.6))
    if half:
        ax.set_xlim(-8, 63) if flip else ax.set_xlim(57, 128)
    legend = []

    # Voronoi
    pts = np.vstack([att, dfn]) if len(dfn) else att
    if "Voronoi" in layers and len(pts) >= 2:
        for i, poly in enumerate(V.voronoi_polygons(pts)):
            col = c_att if i < len(att) else c_def
            ax.add_patch(Polygon(_tf(poly, flip), closed=True, facecolor=col, alpha=.2, edgecolor="white", lw=1.2, zorder=1.5))
        legend += [Patch(facecolor=TEAM_C, alpha=.35, label=f"Espacio de {team}"), Patch(facecolor=RIVAL_C, alpha=.35, label="Espacio del rival")]

    o = V.ownership(frame)
    gx, gy = V.GRID[:, 0], V.GRID[:, 1]
    bx, by = ball
    zone = (gx >= min(bx, V.ZONE_MIN_X)) & (np.hypot(gx - bx, gy - by) <= V.ZONE_RADIUS)

    # Fuera de la zona analizada (más de 30 m del balón o por detrás del último tercio): se atenúa
    X_, Y_ = (V.LENGTH - V._GX, V.WIDTH - V._GY) if flip else (V._GX, V._GY)
    ax.contourf(X_, Y_, (~zone).reshape(V._GX.shape).astype(float), levels=[.5, 1.5], colors=["white"], alpha=.55, zorder=1.7)

    # Espacio vulnerable
    if "Espacio libre (≥ 8 m del defensor)" in layers:
        vul = (zone & (o["d_def"] >= V.FREE_DIST)).reshape(V._GX.shape).astype(float)
        if vul.any():
            ax.contourf(X_, Y_, vul, levels=[.5, 1.5], colors=[GOLD], alpha=.3, zorder=1.8)
            ax.contour(X_, Y_, vul, levels=[.5], colors=[GOLD], linewidths=1.2, zorder=1.9)
        legend.append(Patch(facecolor=GOLD, alpha=.45, label="Espacio a ≥ 8 m de cualquier defensor"))

    # Carriles
    if "Carriles" in layers:
        x0 = min(bx, V.ZONE_MIN_X)
        lanes = sit.get("carriles_pct") or {}
        for _, y0, y1 in V.CORRIDORS[1:]:
            (a, b) = _tf([[x0, y0], [V.LENGTH, y0]], flip)
            ax.plot([a[0], b[0]], [a[1], b[1]], ls=(0, (4, 3)), color=NAVY, lw=.8, alpha=.5, zorder=2)
        for name, y0, y1 in V.CORRIDORS:
            if name in lanes:
                p = _tf([[V.LENGTH + 4.5, (y0 + y1) / 2]], flip)[0]
                ax.text(p[0], p[1], f"{lanes[name]:.0f}%", ha="center", va="center", fontsize=8, color=NAVY,
                        bbox=dict(boxstyle="round,pad=.2", fc="white", ec="none", alpha=.85), zorder=6)

    # Recorrido desde la recuperación
    rx, ry = sit.get("rec_x"), sit.get("rec_y")
    if "Recorrido desde la recuperación" in layers and rx is not None and not np.isnan(rx):
        p0, p1 = _tf([[rx, ry], [bx, by]], flip)
        ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.6, ls="--"), zorder=4)
        ax.scatter([p0[0]], [p0[1]], s=90, marker="X", color=NAVY, zorder=5)
        legend.append(Line2D([0], [0], marker="X", color=NAVY, ls="--", markersize=8,
                             label=f"Recuperación → remate ({sit.get('seg_desde_recuperacion', 0):.0f} s)"))

    # Líneas de pase desde el poseedor
    if "Líneas de pase" in layers and len(att) > 1:
        ci = int(np.argmin(np.linalg.norm(att - ball, axis=1)))
        for k, q in enumerate(att):
            if k == ci or np.linalg.norm(q - ball) > 2 * V.SUPPORT_RADIUS:
                continue
            blocked = len(dfn) and (V._seg_dist(dfn, ball, q) < V.PASS_LANE).any()
            a, b = _tf([ball, q], flip)
            ax.plot([a[0], b[0]], [a[1], b[1]], color=GREY if blocked else GREEN, lw=1.4 if blocked else 2.2,
                    ls=":" if blocked else "-", alpha=.9, zorder=3)
        legend += [Line2D([0], [0], color=GREEN, lw=2.2, label="Línea de pase libre"),
                   Line2D([0], [0], color=GREY, lw=1.4, ls=":", label="Línea de pase tapada")]

    # Presión y coberturas
    if "Presión y coberturas" in layers and len(dfn):
        db = np.linalg.norm(dfn - ball, axis=1); pi = int(np.argmin(db)); presser = dfn[pi]
        others = np.delete(dfn, pi, axis=0)
        cov = others[(others[:, 0] > presser[0]) & (np.linalg.norm(others - presser, axis=1) < V.COVER_RADIUS)] if len(others) else others
        pp = _tf([presser], flip)[0]
        circ = plt.Circle(_tf([ball], flip)[0], V.PRESS_RADII[1], fill=False, ec=c_def, lw=1, ls="--", alpha=.6, zorder=2)
        ax.add_patch(circ)
        for q in cov:
            qq = _tf([q], flip)[0]
            ax.plot([pp[0], qq[0]], [pp[1], qq[1]], color=ORANGE, lw=1.6, zorder=3)
            ax.scatter([qq[0]], [qq[1]], s=260, facecolors="none", edgecolors=ORANGE, linewidths=1.6, zorder=4)
        ax.scatter([pp[0]], [pp[1]], s=330, facecolors="none", edgecolors=ORANGE, linewidths=2.4, zorder=4)
        legend += [Line2D([0], [0], marker="o", color=ORANGE, markerfacecolor="none", ls="-", markersize=10,
                          label=f"Presiona y {len(cov)} cobertura(s)"),
                   Line2D([0], [0], color=c_def, ls="--", label="Radio de 10 m al balón")]

    # Bloque defensivo
    if "Bloque defensivo" in layers and len(dfn) >= 4:
        field = dfn[np.argsort(dfn[:, 0])[:-1]]
        try:
            from scipy.spatial import ConvexHull
            h = ConvexHull(field)
            ax.add_patch(Polygon(_tf(field[h.vertices], flip), closed=True, fill=False, edgecolor=c_def, lw=2, ls="-.", zorder=3))
            legend.append(Line2D([0], [0], color=c_def, lw=2, ls="-.", label="Bloque defensivo visible"))
        except Exception:
            pass

    # Jugadores y balón
    if len(att):
        A = _tf(att, flip); ax.scatter(A[:, 0], A[:, 1], s=120, color=c_att, edgecolors="white", linewidths=1.2, zorder=5)
    if len(dfn):
        D = _tf(dfn, flip); ax.scatter(D[:, 0], D[:, 1], s=120, color=c_def, edgecolors="white", linewidths=1.2, zorder=5, marker="D")
    B = _tf([ball], flip)[0]
    ax.scatter([B[0]], [B[1]], s=70, color="white", edgecolors=NAVY, linewidths=1.6, zorder=6)
    legend += [Line2D([0], [0], marker="o", color="w", markerfacecolor=c_att, markersize=9, label="Ataca"),
               Line2D([0], [0], marker="D", color="w", markerfacecolor=c_def, markersize=8, label="Defiende"),
               Line2D([0], [0], marker="o", color="w", markerfacecolor="white", markeredgecolor=NAVY, markersize=8, label="Balón")]

    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=16)
    ax.text(0, 1.0, subtitle, transform=ax.transAxes, fontsize=8.5, color="#64748B", va="bottom")
    ax.legend(handles=legend, loc="upper center", bbox_to_anchor=(.5, -.01), ncol=3 if half else 4, frameon=False, fontsize=8)
    return fig


def lanes_figure(lanes_df, title: str, color: str):
    """Barras horizontales: control medio de cada carril por parte del equipo que ataca."""
    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    d = lanes_df.iloc[::-1]
    vals = d["Control medio del atacante (%)"].to_numpy(float)
    ax.barh(d["Carril"], vals, color=color, alpha=.85)
    ax.axvline(50, color=GREY, ls="--", lw=1)
    for i, v in enumerate(vals):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=9, color=NAVY)
    ax.set_xlim(0, 100); ax.set_xlabel("% del carril controlado por quien ataca", fontsize=9)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=NAVY)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    return fig
