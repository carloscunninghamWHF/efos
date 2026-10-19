"""EFOS — Los 10 mapas de transiciones con StatsBomb 360 (uno por análisis).

Mapas de campo (O1, O2, O3, D2, D3): probabilidad por zona agregada sobre todas las recuperaciones o
pérdidas seleccionadas, a partir del Voronoi de cada fotografía.
Mapas relativos al balón (O4, O5, D1, D4, D5): posiciones de los jugadores medidas desde el balón (o desde
el que presiona) en metros, con la dirección de ataque hacia la derecha.

Orientación:
  * Ofensiva: el equipo analizado ataca hacia la derecha (→).
  * Defensiva (campo): la portería del equipo analizado está a la IZQUIERDA y el rival ataca hacia ella (←).
"""
from __future__ import annotations

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Patch, Polygon, Wedge  # noqa: E402

import action_explorer as X  # noqa: E402
from intelligence import transition_voronoi_360 as T  # noqa: E402

TEAM_C, RIVAL_C = "#2563EB", "#B91C1C"
NAVY, MUTED, GREY, GOLD, GREEN, ORANGE = "#0F172A", "#64748B", "#94A3B8", "#C89B3C", "#15803D", "#EA580C"
CONTROL_CMAP = LinearSegmentedColormap.from_list("control", [RIVAL_C, "#F1F5F9", TEAM_C])
FREE_CMAP = LinearSegmentedColormap.from_list("free", ["#FFF7ED", "#FDBA74", "#C2410C"])
EDGES_X = np.arange(0, T.LENGTH + T.STEP, T.STEP)
EDGES_Y = np.arange(0, T.WIDTH + T.STEP, T.STEP)


def _titles(ax, title, subtitle):
    ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold", color=NAVY, pad=16)
    ax.text(0, 1.0, subtitle, transform=ax.transAxes, fontsize=8.3, color=MUTED, va="bottom")


def _grid_on_pitch(ax, rate, cmap, norm, flip=False, alpha=.9):
    r = rate[::-1, ::-1] if flip else rate
    ax.pcolormesh(EDGES_X, EDGES_Y, np.ma.masked_invalid(r), cmap=cmap, norm=norm, alpha=alpha, zorder=1, shading="flat")


def _colorbar(fig, ax, cmap, norm, label, ticks=None, fmt=None):
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=.045, pad=.02, aspect=40)
    cb.set_label(label, fontsize=8, color=MUTED); cb.ax.tick_params(labelsize=7.5, colors=MUTED)
    cb.outline.set_visible(False)
    if ticks is not None:
        cb.set_ticks(ticks)
    if fmt:
        cb.set_ticklabels([fmt.format(t) for t in (ticks or cb.get_ticks())])
    return cb


def _arrow(ax, text, to_right=True):
    # a la derecha, encima del campo: no se cruza con el subtítulo (alineado a la izquierda)
    y = -2.6
    a, b = (88, 119) if to_right else (119, 88)
    ax.annotate("", xy=(b, y), xytext=(a, y), arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.2), annotation_clip=False)
    ax.text(119, y - 1.4, text, ha="right", va="bottom", fontsize=7.8, color=NAVY)


def _empty(ax, msg="Sin fotografías 360 suficientes para esta selección"):
    ax.text(60, 40, msg, ha="center", va="center", fontsize=10, color=MUTED, zorder=10,
            bbox=dict(boxstyle="round,pad=.5", fc="white", ec=GREY))


# ============================================================== mapas de campo
def control_map(keys, capas, team, title, subtitle, defensive=False):
    """O1 / D2: % de veces que el equipo analizado controla cada zona (Voronoi) por delante del balón."""
    fig, ax, _ = X._pitch(figsize=(8.6, 6.2))
    den = "central" if defensive else "ahead"
    rate, n = T.grid_rate(keys, capas, "own_att", den, invert=defensive, min_n=12)
    norm = TwoSlopeNorm(vmin=0, vcenter=.5, vmax=1)
    if np.isfinite(rate).any():
        _grid_on_pitch(ax, rate, CONTROL_CMAP, norm, flip=defensive)
        _colorbar(fig, ax, CONTROL_CMAP, norm, f"% de veces que la zona es de {team} (rojo = del rival)",
                  ticks=[0, .25, .5, .75, 1], fmt="{:.0%}")
    else:
        _empty(ax)
    if defensive:
        for y in T.CENTRAL:
            ax.plot([0, 120], [y, y], color=NAVY, lw=.8, ls=(0, (4, 3)), alpha=.6, zorder=3)
        ax.text(1.5, (T.CENTRAL[0] + T.CENTRAL[1]) / 2, "carril\ncentral", fontsize=7.5, color=NAVY, va="center", zorder=4)
    _arrow(ax, f"el rival ataca hacia la portería de {team}" if defensive else f"ataca {team}", to_right=not defensive)
    _titles(ax, title, subtitle)
    return fig


def free_space_map(keys, capas, team, title, subtitle, defensive=False):
    """O3 / D3: % de veces que la zona queda a ≥ 8 m de cualquier defensor (por delante del balón)."""
    fig, ax, _ = X._pitch(figsize=(8.6, 6.2))
    rate, n = T.grid_rate(keys, capas, "free", "near", min_n=12)
    vmax = float(np.nanpercentile(rate, 98)) if np.isfinite(rate).any() else 1
    norm = plt.Normalize(0, max(vmax, .1))
    if np.isfinite(rate).any():
        _grid_on_pitch(ax, rate, FREE_CMAP, norm, flip=defensive)
        _colorbar(fig, ax, FREE_CMAP, norm, "% de veces que la zona queda a ≥ 8 m de cualquier defensor",
                  ticks=list(np.linspace(0, max(vmax, .1), 5)), fmt="{:.0%}")
    else:
        _empty(ax)
    _arrow(ax, f"el rival ataca hacia la portería de {team}" if defensive else f"ataca {team}", to_right=not defensive)
    _titles(ax, title, subtitle)
    return fig


def lanes_map(d, capas, team, title, subtitle, max_arrows=220):
    """O2: control de cada corredor por delante del balón + primeras progresiones reales tras recuperar."""
    fig, ax, _ = X._pitch(figsize=(8.6, 6.2))
    if d.empty:
        _empty(ax); _titles(ax, title, subtitle); return fig
    lt = T.lane_table(d)
    norm = TwoSlopeNorm(vmin=0, vcenter=50, vmax=100)
    for (name, y0, y1), v, used in zip(T.CORRIDORS, lt["Control medio por delante del balón (%)"], lt["Progresiones reales por ese carril"]):
        if np.isfinite(v):
            ax.add_patch(plt.Rectangle((0, y0), 120, y1 - y0, color=CONTROL_CMAP(norm(v)), alpha=.55, zorder=1, lw=0))
        ax.plot([0, 120], [y0, y0], color="white", lw=2, zorder=1.5)
        ax.text(2, (y0 + y1) / 2, f"{name}\n{v:.0f} % control · {used} progresiones", fontsize=7.6, color=NAVY,
                va="center", zorder=6, bbox=dict(boxstyle="round,pad=.25", fc="white", ec="none", alpha=.85))
    prog = [capas[k]["prog"] for k in d["clave"] if capas[k].get("prog")]
    rng = np.random.default_rng(3)
    if len(prog) > max_arrows:
        prog = [prog[i] for i in rng.choice(len(prog), max_arrows, replace=False)]
    for x0, y0, x1, y1, kind in prog:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=4,
                    arrowprops=dict(arrowstyle="-|>", color=NAVY if kind == "Pass" else GOLD, lw=.9, alpha=.45, mutation_scale=7))
    ax.legend(handles=[Line2D([0], [0], color=NAVY, lw=1.5, label="Pase progresivo"),
                       Line2D([0], [0], color=GOLD, lw=1.5, label="Conducción progresiva"),
                       Patch(color=TEAM_C, alpha=.55, label=f"Carril dominado por {team}"),
                       Patch(color=RIVAL_C, alpha=.55, label="Carril dominado por el rival")],
              loc="upper center", bbox_to_anchor=(.5, -.01), ncol=4, frameon=False, fontsize=7.8)
    _arrow(ax, f"ataca {team}")
    _titles(ax, title, subtitle)
    return fig


# ============================================================== mapas relativos al balón
def _rel_axes(xlim=(-30, 40), ylim=(-32, 32), figsize=(7.6, 6.0)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white"); ax.set_facecolor("#F8FAFC")
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal")
    for r in (5, 10, 20, 30):
        ax.add_patch(Circle((0, 0), r, fill=False, ec=GREY, lw=.8, ls=(0, (3, 3)), zorder=1))
        ax.text(r * .71 + .4, r * .71 + .4, f"{r} m", fontsize=7, color=MUTED, zorder=2)
    ax.axhline(0, color="#E2E8F0", lw=.8, zorder=0); ax.axvline(0, color="#E2E8F0", lw=.8, zorder=0)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    return fig, ax


def _density(ax, pts, cmap, levels=6, bw=1.6, lim=(-30, 40, -32, 32), alpha=.75):
    if len(pts) < 10:
        return
    from scipy.ndimage import gaussian_filter
    H, xe, ye = np.histogram2d(pts[:, 0], pts[:, 1], bins=[70, 64], range=[[lim[0], lim[1]], [lim[2], lim[3]]])
    H = gaussian_filter(H.T, bw)
    if H.max() <= 0:
        return
    xc, yc = (xe[:-1] + xe[1:]) / 2, (ye[:-1] + ye[1:]) / 2
    ax.contourf(xc, yc, H / H.max(), levels=np.linspace(.08, 1, levels), cmap=cmap, alpha=alpha, zorder=2)


def _ball(ax, label="Balón"):
    ax.scatter([0], [0], s=150, color="white", edgecolors=NAVY, linewidths=1.8, zorder=8)
    ax.text(0, -2.6, label, ha="center", va="top", fontsize=8, color=NAVY, zorder=8)


def _fwd(ax, text, y=None):
    """Flecha de la dirección de ataque, dentro de los ejes (esquina inferior derecha)."""
    ax.annotate("", xy=(.97, .04), xytext=(.70, .04), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.3))
    ax.text(.97, .075, text, transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=NAVY,
            bbox=dict(boxstyle="round,pad=.2", fc="white", ec="none", alpha=.85))


def supports_map(keys, capas, team, title, subtitle, n_moments):
    """O4: dónde están los compañeros (a < 20 m) respecto al que recupera; verde = línea de pase libre."""
    fig, ax = _rel_axes(xlim=(-25, 25), ylim=(-25, 25), figsize=(6.8, 6.4))
    rel = [capas[k]["support_rel"] * T.YD for k in keys if len(capas[k]["support_rel"])]
    ok = [capas[k]["support_free"] for k in keys if len(capas[k]["support_rel"])]
    if rel:
        P, F = np.vstack(rel), np.concatenate(ok)
        _density(ax, P, plt.cm.Blues, lim=(-25, 25, -25, 25), alpha=.45)
        idx = np.random.default_rng(1).permutation(len(P))[:900]
        ax.scatter(P[idx][~F[idx], 0], P[idx][~F[idx], 1], s=10, color=GREY, alpha=.6, zorder=4, lw=0)
        ax.scatter(P[idx][F[idx], 0], P[idx][F[idx], 1], s=12, color=GREEN, alpha=.7, zorder=5, lw=0)
        front, behind = (P[:, 0] > 2).sum(), (P[:, 0] < -2).sum()
        for xx, txt in ((14, f"Por delante\n{front / max(n_moments, 1):.1f} por jugada"), (-14, f"Por detrás\n{behind / max(n_moments, 1):.1f} por jugada")):
            ax.text(xx, 21.5, txt, ha="center", fontsize=8, color=NAVY, bbox=dict(boxstyle="round,pad=.3", fc="white", ec="none", alpha=.9))
    else:
        ax.text(0, 10, "Sin apoyos registrados", ha="center", color=MUTED)
    _ball(ax, "Quien recupera")
    ax.legend(handles=[Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN, markersize=7, label="Compañero con línea de pase libre"),
                       Line2D([0], [0], marker="o", color="w", markerfacecolor=GREY, markersize=7, label="Compañero con la línea tapada")],
              loc="upper center", bbox_to_anchor=(.5, -.01), ncol=2, frameon=False, fontsize=8)
    _fwd(ax, f"ataca {team}")
    _titles(ax, title, subtitle)
    return fig


def advantage_map(keys, capas, team, title, subtitle, n_moments):
    """O5: posición de los atacantes libres (sin defensor a 5 m) por delante del balón al recuperar."""
    fig, ax = _rel_axes(xlim=(-5, 40), ylim=(-32, 32), figsize=(6.8, 6.6))
    P = T.stack_rel(keys, capas, "free_att_rel")
    if len(P):
        _density(ax, P, LinearSegmentedColormap.from_list("g", ["#DCFCE7", GREEN]), lim=(-5, 40, -32, 32), alpha=.8)
        idx = np.random.default_rng(2).permutation(len(P))[:700]
        ax.scatter(P[idx, 0], P[idx, 1], s=10, color=GREEN, alpha=.55, zorder=4, lw=0, edgecolors="white")
        ax.text(20, 29, f"{len(P) / max(n_moments, 1):.1f} atacantes libres por recuperación", ha="center", fontsize=8.5, color=NAVY,
                bbox=dict(boxstyle="round,pad=.3", fc="white", ec="none", alpha=.9))
    _ball(ax, "Recuperación")
    ax.add_patch(Wedge((0, 0), 25, -90, 90, fill=False, ec=NAVY, lw=1, ls="--", zorder=3))
    ax.text(17.7, -19.5, "25 m: zona donde se\ncuenta la superioridad", fontsize=7, color=MUTED, ha="left")
    _fwd(ax, f"ataca {team}")
    _titles(ax, title, subtitle)
    return fig


def pressure_map(keys, capas, team, title, subtitle, n_moments):
    """D1: jugadores del equipo analizado alrededor del balón en el instante de la pérdida."""
    fig, ax = _rel_axes(xlim=(-25, 25), ylim=(-25, 25), figsize=(6.8, 6.4))
    P = T.stack_rel(keys, capas, "def_rel")
    if len(P):
        P = P[np.hypot(P[:, 0], P[:, 1]) < 25]
        _density(ax, P, plt.cm.Blues, lim=(-25, 25, -25, 25), alpha=.7)
        d = np.hypot(P[:, 0], P[:, 1])
        for r, col in ((5, RIVAL_C), (10, ORANGE)):
            ax.add_patch(Circle((0, 0), r, fill=False, ec=col, lw=1.8, zorder=6))
        ax.text(0, 22, f"Por pérdida: {(d < 5).sum() / max(n_moments, 1):.1f} jugadores a < 5 m · {(d < 10).sum() / max(n_moments, 1):.1f} a < 10 m",
                ha="center", fontsize=8.5, color=NAVY, bbox=dict(boxstyle="round,pad=.3", fc="white", ec="none", alpha=.9))
    _ball(ax, "Balón (lo recibe el rival)")
    ax.legend(handles=[Line2D([0], [0], color=RIVAL_C, lw=2, label="5 m: presión directa"),
                       Line2D([0], [0], color=ORANGE, lw=2, label="10 m: cierre del espacio"),
                       Patch(color=TEAM_C, alpha=.6, label=f"Dónde suelen estar los jugadores de {team}")],
              loc="upper center", bbox_to_anchor=(.5, -.01), ncol=3, frameon=False, fontsize=7.6)
    _fwd(ax, f"hacia la portería de {team}")
    _titles(ax, title, subtitle)
    return fig


def cover_map(keys, capas, d, team, title, subtitle):
    """D4: compañeros que cubren al que presiona (más cerca de su portería y a < 15 m de él)."""
    fig, ax = _rel_axes(xlim=(-16, 18), ylim=(-17, 17), figsize=(6.8, 6.4))
    ax.add_patch(Wedge((0, 0), 15, -90, 90, color=ORANGE, alpha=.08, zorder=1))
    ax.add_patch(Wedge((0, 0), 15, -90, 90, fill=False, ec=ORANGE, lw=1.2, ls="--", zorder=2))
    P = T.stack_rel(keys, capas, "cover_rel")
    if len(P):
        _density(ax, P, LinearSegmentedColormap.from_list("o", ["#FFEDD5", ORANGE]), lim=(-16, 18, -17, 17), alpha=.6)
        idx = np.random.default_rng(4).permutation(len(P))[:700]
        ax.scatter(P[idx, 0], P[idx, 1], s=12, color=ORANGE, alpha=.6, zorder=4, lw=0)
    ax.scatter([0], [0], s=260, color=TEAM_C, edgecolors="white", linewidths=1.6, zorder=8)
    ax.text(0, -1.8, "Presiona", ha="center", va="top", fontsize=8, color=NAVY)
    if len(d):
        dist = d["coberturas"].clip(upper=3).value_counts(normalize=True).reindex([0, 1, 2, 3], fill_value=0)
        txt = " · ".join(f"{'3+' if k == 3 else k}: {v:.0%}" for k, v in dist.items())
        ax.text(1, 15.5, f"Coberturas por jugada → {txt}", ha="center", fontsize=8.2, color=NAVY,
                bbox=dict(boxstyle="round,pad=.3", fc="white", ec="none", alpha=.9))
    _fwd(ax, f"hacia la portería de {team}")
    _titles(ax, title, subtitle)
    return fig


def compaction_map(keys, capas, d, team, title, subtitle):
    """D5: ocupación del bloque cerca del balón en la pérdida (línea) frente a 2–6 s después (relleno).

    Ambas densidades se expresan en jugadores por m² y por jugada, con la misma escala, para que la
    comparación sea directa. El jugador que pierde el balón no cuenta.
    """
    fig, ax = _rel_axes(xlim=(-30, 35), ylim=(-32, 32), figsize=(7.4, 6.4))
    keys = [k for k in keys if capas[k].get("after") is not None]
    P0 = T.stack_rel(keys, capas, "blk_rel")
    P1 = np.vstack([capas[k]["after"]["blk_rel"] for k in keys if len(capas[k]["after"]["blk_rel"])]) * T.YD if keys else np.empty((0, 2))
    if len(P0) > 20 and len(P1) > 20:
        from scipy.ndimage import gaussian_filter
        rng = [[-30, 35], [-32, 32]]

        def dens(P):
            H, xe, ye = np.histogram2d(P[:, 0], P[:, 1], bins=[65, 64], range=rng)
            return (xe[:-1] + xe[1:]) / 2, (ye[:-1] + ye[1:]) / 2, gaussian_filter(H.T, 2.2) / max(len(keys), 1)
        xc, yc, H0 = dens(P0); _, _, H1 = dens(P1)
        top = max(H0.max(), H1.max())
        lv = [top * f for f in (.2, .45, .7)]
        ax.contourf(xc, yc, H1, levels=lv + [top * 1.01], colors=["#BFDBFE", "#60A5FA", TEAM_C], alpha=.55, zorder=2)
        ax.contour(xc, yc, H0, levels=lv[:2], colors=[NAVY], linestyles=["--", "-"], linewidths=1.4, zorder=3)
        if len(d):
            a0, a1 = d["bloque_m2"].median(), d["bloque_m2_despues"].median()
            w0, w1 = d["bloque_ancho_m"].median(), d["bloque_ancho_m_despues"].median()
            p0, p1 = d["bloque_prof_m"].median(), d["bloque_prof_m_despues"].median()
            ax.text(2.5, 28.5, f"Superficie {a0:.0f} → {a1:.0f} m² · Anchura {w0:.0f} → {w1:.0f} m · Profundidad {p0:.0f} → {p1:.0f} m",
                    ha="center", fontsize=8.2, color=NAVY, bbox=dict(boxstyle="round,pad=.3", fc="white", ec="none", alpha=.9))
    else:
        ax.text(2, 0, "Sin pares de fotografías suficientes", ha="center", color=MUTED)
    _ball(ax, "Balón")
    ax.legend(handles=[Line2D([0], [0], color=NAVY, lw=1.4, ls="--", label="Ocupación en el instante de la pérdida"),
                       Patch(color=TEAM_C, alpha=.6, label="Ocupación 2–6 s después")],
              loc="upper center", bbox_to_anchor=(.5, -.01), ncol=2, frameon=False, fontsize=8)
    _fwd(ax, f"hacia la portería de {team}")
    _titles(ax, title, subtitle)
    return fig


# ============================================================== jugada concreta (Voronoi real)
def play_map(capa: dict, team: str, fase: str, title: str, subtitle: str):
    """Voronoi completo de una recuperación o pérdida concreta con la fotografía 360."""
    from intelligence.transition_voronoi import voronoi_polygons
    s = capa["snap"]; att, dfn, ball = s["att"], s["dfn"], s["ball"]
    defensive = fase == "Defensiva"
    flip = defensive                                    # la portería del equipo analizado, a la izquierda
    tf = (lambda P: np.column_stack([T.LENGTH - P[:, 0], T.WIDTH - P[:, 1]])) if flip else (lambda P: P)
    c_att, c_def = (RIVAL_C, TEAM_C) if defensive else (TEAM_C, RIVAL_C)
    fig, ax, _ = X._pitch(figsize=(9.4, 6.6))
    pts = np.vstack([att, dfn])
    vis = s["vis"].reshape(T.GX.shape)
    if len(pts) >= 2:
        for i, poly in enumerate(voronoi_polygons(pts)):
            ax.add_patch(Polygon(tf(poly), closed=True, facecolor=c_att if i < len(att) else c_def, alpha=.22,
                                 edgecolor="white", lw=1.2, zorder=1.5))
    hidden = (~vis)[::-1, ::-1] if flip else ~vis
    ax.pcolormesh(EDGES_X, EDGES_Y, np.ma.masked_where(~hidden, np.ones_like(hidden, float)),
                  cmap=LinearSegmentedColormap.from_list("h", ["#FFFFFF", "#FFFFFF"]), alpha=.72, zorder=1.7, shading="flat")
    free = capa["free"].reshape(T.GX.shape).astype(float)
    free = free[::-1, ::-1] if flip else free
    if free.any():
        ax.contour(EDGES_X[:-1] + 1, EDGES_Y[:-1] + 1, free, levels=[.5], colors=[GOLD], linewidths=1.6, zorder=2)
    A, D, B = tf(att), tf(dfn), tf(ball.reshape(1, 2))[0]
    ax.scatter(A[:, 0], A[:, 1], s=120, color=c_att, edgecolors="white", linewidths=1.2, zorder=5)
    ax.scatter(D[:, 0], D[:, 1], s=110, color=c_def, edgecolors="white", linewidths=1.2, marker="D", zorder=5)
    ax.scatter([B[0]], [B[1]], s=80, color="white", edgecolors=NAVY, linewidths=1.8, zorder=6)
    for r in (T.PRESS_RADII[1],):
        ax.add_patch(Circle(B, r, fill=False, ec=NAVY, lw=1, ls="--", alpha=.6, zorder=3))
    if capa.get("prog"):
        x0, y0, x1, y1, _k = capa["prog"]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=2), zorder=6)
    ax.legend(handles=[Patch(facecolor=TEAM_C, alpha=.4, label=f"Espacio de {team}"), Patch(facecolor=RIVAL_C, alpha=.4, label="Espacio del rival"),
                       Line2D([0], [0], color=GOLD, lw=1.6, label="Zona a ≥ 8 m de cualquier defensor"),
                       Patch(facecolor="white", edgecolor=GREY, label="Fuera de cámara (atenuado, sin datos)"),
                       Line2D([0], [0], color=NAVY, ls="--", label="10 m alrededor del balón")],
              loc="upper center", bbox_to_anchor=(.5, -.01), ncol=3, frameon=False, fontsize=7.8)
    _titles(ax, title, subtitle)
    return fig
