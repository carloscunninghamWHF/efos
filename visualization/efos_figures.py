"""EFOS — figuras para presentación académica.

Cada función recibe los CSV de salida de Sprint 3 y devuelve una figura Plotly.
Reglas comunes:
  * Un solo color de acento (equipo focal); el resto en grises.
  * El título enuncia el hallazgo; el subtítulo dice qué se mide y con qué n.
  * Ninguna figura sugiere diferencias que los datos no sostienen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------- estilo
NAVY = "#0F172A"      # enterprise ink
ACCENT = "#1D4ED8"    # primary action / focal evidence
GREY = "#64748B"      # secondary context
LIGHT = "#E2E8F0"     # grids / borders
RISK = "#B91C1C"      # critical states
PITCH_LINE = "#475569"

FONT = "Inter, Segoe UI, Helvetica Neue, Arial, sans-serif"

DIMENSIONS = {
    "OC": "Orden y compacidad",
    "HPS": "Estabilidad bajo presión",
    "RPS": "Seguridad en zona propia",
    "DS": "Decisión vs. probabilidad de pase",
    "DER": "Velocidad de respuesta tras pérdida",
}
ESI_WEIGHTS = {"OC": .25, "HPS": .20, "RPS": .20, "DS": .15, "DER": .20}

STATE_LABELS = {
    "stability": "Estabilidad", "adaptation": "Adaptación", "tension": "Tensión",
    "fragility": "Fragilidad", "collapse": "Colapso",
}
STATE_ORDER = ["stability", "adaptation", "tension", "fragility", "collapse"]
SCORE_LABELS = {"losing": "Perdiendo", "drawing": "Empatando", "winning": "Ganando"}

PRINCIPLE_LABELS = {
    "Immediate response after possession loss": "Respuesta inmediata tras pérdida (≤5 s)",
    "High pressure in attacking third": "Presión en último tercio (x > 80)",
    "Direct deep progression from X<40 to X>80": "Progresión directa (x < 40 → x > 80)",
}


def _title(main: str, sub: str) -> dict:
    return dict(
        text=f"<b>{main}</b>", x=0.01, xanchor="left", xref="container",
        y=0.98, yref="container", yanchor="top", font=dict(size=18),
        subtitle=dict(text=sub, font=dict(size=13, color=GREY)),
    )


def _base(fig: go.Figure, main: str, sub: str, note: str | None = None, height: int = 420,
          legend: bool = False) -> go.Figure:
    fig.update_layout(
        title=_title(main, sub),
        font=dict(family=FONT, size=13, color=NAVY),
        paper_bgcolor="white", plot_bgcolor="white",
        height=height, margin=dict(l=10, r=20, t=95, b=85 if note else 40),
        showlegend=legend,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LIGHT, tickfont=dict(color=NAVY))
    fig.update_yaxes(gridcolor=LIGHT, zeroline=False, linecolor=LIGHT, tickfont=dict(color=NAVY))
    if note:
        fig.add_annotation(text=note, xref="paper", yref="paper", x=0, y=0, yshift=-58, yanchor="top",
                           xanchor="left", showarrow=False, font=dict(size=11, color=GREY), align="left")
    return fig


# ------------------------------------------------------ 1. ESI y dimensiones
def fig_esi_dimensions(esi_overall: pd.DataFrame, team: str) -> go.Figure:
    row = esi_overall.iloc[0]
    esi = float(row["ESI"])
    d = pd.DataFrame({
        "key": list(DIMENSIONS),
        "label": [f"{DIMENSIONS[k]} ({k}) · peso {int(ESI_WEIGHTS[k]*100)} %" for k in DIMENSIONS],
        "value": [float(row[k]) for k in DIMENSIONS],
    }).sort_values("value")
    weakest = d.iloc[0]
    fig = go.Figure(go.Bar(
        x=d["value"], y=d["label"], orientation="h",
        marker_color=[ACCENT if k == weakest.key else NAVY for k in d["key"]],
        text=[f"{v:.1f}" for v in d["value"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:.1f}<extra></extra>",
    ))
    fig.add_vline(x=esi, line=dict(color=GREY, dash="dot", width=1.5))
    fig.add_annotation(x=esi, y=1.02, yref="paper", text=f"ESI global {esi:.1f}", showarrow=False,
                       font=dict(color=GREY, size=12), xanchor="center", yanchor="bottom")
    fig.update_xaxes(range=[0, 105], title="Puntuación (0–100)", showgrid=True, gridcolor=LIGHT)
    return _base(
        fig,
        f"El ESI de {team} ({esi:.1f}) lo limita {DIMENSIONS[weakest.key].lower()}",
        "Cinco dimensiones del Engine Stability Index; el ESI es su media ponderada",
        "Pesos definidos en metrics/esi.py (hipótesis v0.3, no calibradas).",
        height=380,
    )


# --------------------------------------------------- 2. ESI por marcador
def fig_esi_by_score(esi_ctx: pd.DataFrame, esi_global: float, team: str) -> go.Figure:
    d = esi_ctx.set_index("score_state").reindex(["losing", "drawing", "winning"]).reset_index()
    spread = d["ESI"].max() - d["ESI"].min()
    labels = [f"{SCORE_LABELS[s]}<br><span style='font-size:11px;color:{GREY}'>n = {int(n):,} eventos</span>"
              for s, n in zip(d["score_state"], d["n_events"])]
    fig = go.Figure()
    for k, symbol in zip(DIMENSIONS, ["circle", "square", "diamond", "triangle-up", "cross"]):
        fig.add_trace(go.Scatter(
            x=d[k], y=labels, mode="markers", name=k,
            marker=dict(color=GREY, size=9, symbol=symbol, line=dict(width=0)),
            hovertemplate=f"{DIMENSIONS[k]} ({k}): %{{x:.1f}}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=d["ESI"], y=labels, mode="markers+text", name="ESI",
        marker=dict(color=ACCENT, size=18, line=dict(color=NAVY, width=1.5)),
        text=[f"ESI {v:.1f}" for v in d["ESI"]], textposition="top center",
        textfont=dict(color=NAVY, size=12), hovertemplate="ESI: %{x:.2f}<extra></extra>", cliponaxis=False,
    ))
    fig.update_xaxes(range=[40, 100], title="Puntuación (0–100)", showgrid=True, gridcolor=LIGHT)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.28, x=0, font=dict(size=11)))
    return _base(
        fig,
        f"El marcador apenas mueve el ESI de {team}: {spread:.1f} puntos entre contextos",
        "ESI (amarillo) y sus dimensiones (gris) según el estado del marcador",
        None, height=420, legend=True,
    )


# -------------------------------------------- 3. ESI a lo largo del partido
def fig_esi_timeline(windows: pd.DataFrame, team: str, window_minutes: int = 15) -> go.Figure:
    g = windows.groupby("window_order")["ESI"]
    s = pd.DataFrame({"median": g.median(), "q1": g.quantile(.25), "q3": g.quantile(.75), "n": g.size()}).reset_index()
    s["label"] = [f"{w*window_minutes}–{(w+1)*window_minutes}′" if w < 6 else (f"{w*window_minutes}′ + añadido" if w == 6 else f"{w*window_minutes}′+")
                  for w in s["window_order"]]
    solid = s[s["n"] >= 10]
    sparse = s[s["n"] < 10]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(solid["label"]) + list(solid["label"][::-1]),
                             y=list(solid["q3"]) + list(solid["q1"][::-1]),
                             fill="toself", fillcolor="rgba(224,168,0,0.22)", line=dict(width=0), mode="lines",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=solid["label"], y=solid["median"], mode="lines+markers",
                             line=dict(color=NAVY, width=2.5), marker=dict(size=8, color=NAVY),
                             customdata=np.c_[solid["q1"], solid["q3"], solid["n"]],
                             hovertemplate="%{x}<br>Mediana %{y:.1f}<br>IQR %{customdata[0]:.1f}–%{customdata[1]:.1f}"
                                           "<br>n = %{customdata[2]} partidos<extra></extra>"))
    lo, hi = solid["q1"].min(), solid["q3"].max()
    fig.update_yaxes(range=[np.floor(lo) - 6, np.ceil(hi) + 6], title="ESI")
    fig.update_xaxes(title=f"Tramo del partido ({window_minutes} min, tiempo de juego)")
    note = "Banda: rango intercuartílico entre partidos."
    if len(sparse):
        note += " Excluidos por muestra insuficiente: " + ", ".join(
            f"{l} (n = {int(n)} partidos, ESI {m:.1f})" for l, n, m in zip(sparse["label"], sparse["n"], sparse["median"])) + "."
    return _base(fig, f"El ESI de {team} se mantiene entre {solid['median'].min():.1f} y {solid['median'].max():.1f} a lo largo del partido",
                 f"Mediana por tramo en {windows['match_id'].nunique()} partidos", note)


def fig_esi_match_heatmap(windows: pd.DataFrame, team: str, window_minutes: int = 15) -> go.Figure:
    n = windows.groupby("window_order")["match_id"].nunique()
    keep = n[n >= 10].index
    p = windows[windows["window_order"].isin(keep)].pivot_table(index="match_id", columns="window_order", values="ESI")
    p = p.loc[p.mean(axis=1).sort_values().index]
    cols = [f"{w*window_minutes}–{(w+1)*window_minutes}′" if w < 6 else f"{w*window_minutes}′ + añ." for w in p.columns]
    rows = [f"Partido {i+1}" for i in range(len(p))]
    fig = go.Figure(go.Heatmap(
        z=p.values, x=cols, y=rows, customdata=np.array([[m] * p.shape[1] for m in p.index]),
        colorscale=[[0, RISK], [0.5, "#F7F7F5"], [1, NAVY]],
        zmin=float(np.nanmedian(p.values)) - 8, zmax=float(np.nanmedian(p.values)) + 8,
        colorbar=dict(title="ESI", thickness=12, len=0.6),
        hovertemplate="match_id %{customdata}<br>%{x}: ESI %{z:.1f}<extra></extra>",
        xgap=1, ygap=1,
    ))
    fig.update_yaxes(showticklabels=False, title="Partidos (ordenados por ESI medio)")
    fig.update_xaxes(side="bottom", title="Tramo del partido")
    return _base(fig, "El ESI tramo a tramo en cada partido",
                 f"Rojo: por debajo de la mediana ({np.nanmedian(p.values):.1f}); azul: por encima. Escala ±8 puntos",
                 "Cada fila es un partido; pase el cursor para ver su match_id.", height=600)


# ------------------------------------------------------------- 4. DTC
def fig_dtc_states(states: pd.DataFrame, team: str) -> go.Figure:
    c = states["state"].value_counts().reindex(STATE_ORDER, fill_value=0)
    total = int(c.sum())
    colors = [NAVY, "#60A5FA", GREY, RISK, RISK]
    fig = go.Figure(go.Bar(
        x=[STATE_LABELS[s] for s in c.index], y=c.values, marker_color=colors,
        text=[f"{v} ({100*v/total:.0f} %)" if v else "0" for v in c.values], textposition="outside",
        cliponaxis=False, hovertemplate="%{x}: %{y} tramos<extra></extra>",
    ))
    fig.update_yaxes(title="Tramos de 15 min", range=[0, c.max() * 1.18])
    stable_share = 100 * (c["stability"] + c["adaptation"]) / total
    return _base(fig, f"{stable_share:.0f} % de los tramos: estabilidad o adaptación",
                 f"Estado DTC asignado a {total} tramos de {states['match_id'].nunique()} partidos",
                 "Umbrales en intelligence/dtc.py: estabilidad = ESI ≥ 70 y DER ≥ 60; adaptación = ESI ≥ 55.",
                 height=380)


def fig_dtc_matrix(states: pd.DataFrame) -> go.Figure:
    x = states.sort_values(["match_id", "window_order"]).dropna(subset=["next_state"])
    origins = [s for s in STATE_ORDER if s in set(x["state"])]
    targets = [s for s in STATE_ORDER if s in set(x["next_state"])]
    counts = pd.crosstab(x["state"], x["next_state"]).reindex(index=origins, columns=targets, fill_value=0)
    probs = counts.div(counts.sum(axis=1), axis=0)
    text = [[f"<b>{probs.iat[i, j]*100:.0f} %</b><br>n = {counts.iat[i, j]}" if counts.iat[i, j] else "–"
             for j in range(len(targets))] for i in range(len(origins))]
    fig = go.Figure(go.Heatmap(
        z=probs.values, x=[STATE_LABELS[s] for s in targets],
        y=[f"{STATE_LABELS[s]} (n = {int(counts.loc[s].sum())})" for s in origins],
        text=text, texttemplate="%{text}", textfont=dict(size=14, color=NAVY),
        colorscale=[[0, "white"], [1, "#BFDBFE"]], zmin=0, zmax=1,
        showscale=False, xgap=3, ygap=3, hovertemplate="De %{y} a %{x}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", title="Estado en el tramo t", showgrid=False)
    fig.update_xaxes(title="Estado en el tramo t + 1", side="bottom")
    missing = [STATE_LABELS[s] for s in STATE_ORDER if s not in origins]
    note = "Probabilidad por fila (cada fila suma 100 %)."
    if missing:
        note += " " + ", ".join(missing) + ": no aparecen como estado de origen."
    p_ss = probs.loc["stability", "stability"] if "stability" in probs.index and "stability" in probs.columns else np.nan
    return _base(fig, f"Tras un tramo estable, {p_ss*100:.0f} % de las veces el siguiente también lo es",
                 "Transiciones entre estados DTC en tramos consecutivos del mismo partido", note,
                 height=110 * len(origins) + 190)


# ------------------------------------------------------------- 5. LAP
def fig_lap(lap: pd.DataFrame, team: str, min_actions: int = 100, top: int = 12) -> go.Figure:
    d = lap[lap["final_third_actions"] >= min_actions].nlargest(top, "LAP").sort_values("LAP")
    excluded = int((lap["final_third_actions"] < min_actions).sum())
    median = float(lap.loc[lap["final_third_actions"] >= min_actions, "LAP"].median())
    fig = go.Figure()
    for _, r in d.iterrows():
        fig.add_shape(type="line", x0=median, x1=r["LAP"], y0=r["player"], y1=r["player"],
                      line=dict(color=LIGHT, width=3), layer="below")
    fig.add_trace(go.Scatter(
        x=d["LAP"], y=d["player"], mode="markers+text",
        marker=dict(color=NAVY, size=np.clip(np.sqrt(d["final_third_actions"]) / 2, 7, 22), line=dict(width=0)),
        text=[f"{v:.1f} %  (n = {n:,})" for v, n in zip(d["LAP"], d["final_third_actions"])],
        textposition="middle right", textfont=dict(size=12, color=NAVY), cliponaxis=False,
        customdata=np.c_[d["critical_actions"], d["final_third_actions"], d["xG"]],
        hovertemplate="%{y}<br>LAP %{x:.1f} %<br>%{customdata[0]} críticas de %{customdata[1]} acciones"
                      "<br>xG acumulado %{customdata[2]:.2f}<extra></extra>",
    ))
    fig.add_vline(x=median, line=dict(color=ACCENT, width=2, dash="dot"))
    fig.add_annotation(x=median, y=1.01, yref="paper", text=f"Mediana del plantel {median:.1f} %", showarrow=False,
                       font=dict(color=NAVY, size=12), yanchor="bottom")
    lo = np.floor(min(d["LAP"].min(), median)) - 3 if len(d) else 0
    hi = np.ceil(d["LAP"].max()) + 8 if len(d) else 100
    fig.update_xaxes(range=[lo, hi], title="LAP: % de acciones en último tercio que son pase, conducción, recepción, regate o tiro",
                     showgrid=True, gridcolor=LIGHT)
    spread = d["LAP"].max() - d["LAP"].min() if len(d) else 0
    return _base(fig, f"Top {len(d)} en LAP: separados por solo {spread:.1f} puntos",
                 f"Jugadores de {team} con al menos {min_actions} acciones en último tercio (x > 80); tamaño del punto = volumen",
                 f"{excluded} jugadores excluidos por muestra insuficiente. Eje ampliado: compare distancias, no longitudes.",
                 height=max(380, 34 * len(d) + 150))


# ------------------------------------------------------------- 6. Campo
def _pitch_shapes(fig: go.Figure) -> None:
    line = dict(color=PITCH_LINE, width=1.4)
    shapes = [
        dict(type="rect", x0=0, y0=0, x1=120, y1=80),
        dict(type="line", x0=60, y0=0, x1=60, y1=80),
        dict(type="circle", x0=50, y0=30, x1=70, y1=50),
        dict(type="rect", x0=0, y0=18, x1=18, y1=62), dict(type="rect", x0=102, y0=18, x1=120, y1=62),
        dict(type="rect", x0=0, y0=30, x1=6, y1=50), dict(type="rect", x0=114, y0=30, x1=120, y1=50),
        dict(type="rect", x0=-2, y0=36, x1=0, y1=44), dict(type="rect", x0=120, y0=36, x1=122, y1=44),
    ]
    for s in shapes:
        fig.add_shape(**s, line=line, fillcolor="rgba(0,0,0,0)", layer="above")
    for x in (40, 80):
        fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=80, line=dict(color=GREY, width=1, dash="dot"), layer="above")
    for x in (12, 108):
        fig.add_shape(type="circle", x0=x - .4, x1=x + .4, y0=39.6, y1=40.4, line=line, fillcolor=PITCH_LINE)


def fig_pitch_density(events: pd.DataFrame, team: str, event_types: list[str], bins=(6, 4)) -> go.Figure:
    e = events[events["team"].eq(team) & events["event_type"].isin(event_types)].copy()
    e["location_x"] = pd.to_numeric(e["location_x"], errors="coerce")
    e["location_y"] = pd.to_numeric(e["location_y"], errors="coerce")
    e = e.dropna(subset=["location_x", "location_y"])
    nx, ny = bins
    H, xe, ye = np.histogram2d(e["location_x"].clip(0, 119.99), e["location_y"].clip(0, 79.99),
                               bins=[nx, ny], range=[[0, 120], [0, 80]])
    share = 100 * H / max(H.sum(), 1)
    xc, yc = (xe[:-1] + xe[1:]) / 2, (ye[:-1] + ye[1:]) / 2
    fig = go.Figure(go.Heatmap(
        z=share.T, x=xc, y=yc, colorscale=[[0, "white"], [0.35, "#BFDBFE"], [1, ACCENT]],
        showscale=False,
        text=np.vectorize(lambda v: f"{v:.1f} %")(share.T), texttemplate="%{text}",
        textfont=dict(size=13, color=NAVY), hovertemplate="Zona x≈%{x:.0f}, y≈%{y:.0f}: %{z:.1f} %<extra></extra>",
        xgap=0, ygap=0,
    ))
    _pitch_shapes(fig)
    thirds = [100 * H[(xc >= a) & (xc < b)].sum() / max(H.sum(), 1) for a, b in ((0, 40), (40, 80), (80, 120))]
    for (a, b), v, name in zip(((0, 40), (40, 80), (80, 120)), thirds, ("Tercio propio", "Tercio medio", "Último tercio")):
        fig.add_annotation(x=(a + b) / 2, y=-4, text=f"{name}: <b>{v:.0f} %</b>", showarrow=False,
                           font=dict(size=12, color=NAVY))
    fig.add_annotation(x=100, y=86, ax=70, ay=86, xref="x", yref="y", axref="x", ayref="y", text="",
                       showarrow=True, arrowhead=2, arrowwidth=1.5, arrowcolor=NAVY)
    fig.add_annotation(x=68, y=86, text="Dirección de ataque", showarrow=False, xanchor="right",
                       font=dict(size=11, color=NAVY))
    for yy, name in ((6, "Banda izquierda"), (74, "Banda derecha")):
        fig.add_annotation(x=123, y=yy, text=name, showarrow=False, xanchor="left", font=dict(size=11, color=GREY))
    fig.update_xaxes(range=[-3, 140], visible=False, constrain="domain")
    fig.update_yaxes(range=[-8, 90], visible=False, scaleanchor="x", scaleratio=1, autorange=False)
    fig.update_yaxes(range=[90, -8])  # StatsBomb: y crece hacia abajo
    return _base(fig, f"{team} realiza el {thirds[1]:.0f} % de sus acciones con balón en el tercio medio",
                 f"% de {len(e):,} acciones con balón ({', '.join(event_types)}) por zona; campo StatsBomb 120 × 80",
                 f"Zonas de {120//nx} × {80/ny:.0f} unidades. Líneas punteadas: tercios (x = 40 y x = 80). El equipo ataca siempre hacia la derecha.",
                 height=600)


# ------------------------------------------------------------ 7. Principios
def fig_principles(principles: pd.DataFrame, team: str) -> go.Figure:
    d = principles.copy()
    d["label"] = d["principle"].map(PRINCIPLE_LABELS).fillna(d["principle"])
    d = d.sort_values("value_pct")
    fig = go.Figure(go.Bar(
        x=d["value_pct"], y=d["label"], orientation="h", marker_color=NAVY,
        text=[f"{v:.1f} %   (n = {int(n):,} situaciones, {int(m)} partidos · confianza {c:.0f})"
              for v, n, m, c in zip(d["value_pct"], d["evidence_n"], d["matches"], d["confidence"])],
        textposition="outside", cliponaxis=False, textfont=dict(size=12, color=NAVY),
        hovertemplate="%{y}<br>Se cumple en el %{x:.1f} % de las situaciones<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 100], title="% de situaciones elegibles en que se cumple el comportamiento",
                     showgrid=True, gridcolor=LIGHT)
    return _base(fig, f"Principios de juego candidatos de {team}",
                 "Frecuencia observada de cada comportamiento en la temporada",
                 "Confianza = 0.40·frecuencia + 0.35·consistencia entre partidos + 0.25·cobertura (coach_story/principles.py).",
                 height=340)


# ------------------------------------------------------- 8. Historia: estilo
STYLE_COLORS = {"estilo": NAVY, "rendimiento": "#6F8CAB"}


def _fmt_pair(r) -> str:
    if r.tipo == "rendimiento":
        return f"<b>{r.equipo:.2f}</b>  <span style='color:{GREY}'>(rivales {r.rivales:.2f})</span>"
    unit = "" if r.eje == "contrapresion" else " %"
    return f"<b>{r.equipo:.0f}{unit}</b>  <span style='color:{GREY}'>(rivales {r.rivales:.0f}{unit})</span>"


def fig_style_profile(profile: pd.DataFrame, team: str) -> go.Figure:
    """Termómetros 0-100: dónde está el equipo respecto a su rival promedio (50)."""
    d = profile.iloc[::-1].reset_index(drop=True)
    labels = [f"<b>{r.etiqueta}</b><br><span style='font-size:11px;color:{GREY}'>{r.unidad}</span>" for r in d.itertuples()]
    fig = go.Figure()
    fig.add_vrect(x0=0, x1=50, fillcolor="#F5F6F8", line_width=0, layer="below")
    for i, r in enumerate(d.itertuples()):
        fig.add_shape(type="line", x0=50, x1=r.indice, y0=i, y1=i, line=dict(color=ACCENT, width=6), layer="below")
    fig.add_trace(go.Scatter(
        x=d["indice"], y=list(range(len(d))), mode="markers+text",
        marker=dict(size=20, color=ACCENT, line=dict(color=NAVY, width=1.5)),
        text=[_fmt_pair(r) for r in d.itertuples()],
        textposition=["middle right" if v >= 50 else "middle left" for v in d["indice"]],
        textfont=dict(size=13, color=NAVY), cliponaxis=False,
        customdata=np.c_[d["equipo"], d["rivales"]],
        hovertemplate=f"{team}: %{{customdata[0]:.2f}}<br>Rival promedio: %{{customdata[1]:.2f}}<extra></extra>",
    ))
    fig.add_vline(x=50, line=dict(color=NAVY, width=1.5))
    fig.add_annotation(x=50, y=len(d) - 0.35, text="Rival promedio", showarrow=False, yanchor="bottom",
                       font=dict(size=12, color=NAVY))
    fig.add_annotation(x=8, y=len(d) - 0.35, text="← Menos que sus rivales", showarrow=False, xanchor="left",
                       yanchor="bottom", font=dict(size=11, color=GREY))
    fig.add_annotation(x=92, y=len(d) - 0.35, text="Más que sus rivales →", showarrow=False, xanchor="right",
                       yanchor="bottom", font=dict(size=11, color=GREY))
    n_style = int((profile["tipo"] == "estilo").sum())
    fig.add_hline(y=len(d) - n_style - 0.5, line=dict(color=LIGHT, width=2))
    fig.update_yaxes(tickvals=list(range(len(d))), ticktext=labels, range=[-0.6, len(d) + 0.2], showgrid=False)
    fig.update_xaxes(range=[0, 100], tickvals=[0, 25, 50, 75, 100], title="Índice frente a sus rivales (0–100)")
    fig.update_layout(margin=dict(b=100))
    return _base(fig, f"Así juega {team}", "Arriba: estilo de juego. Abajo: resultados. Cada punto compara al equipo con su rival promedio",
                 "50 = rival promedio; 20 puntos = una desviación típica de los rivales.<br>"
                 "En «Evita ocasiones del rival», más a la derecha significa que concede menos.",
                 height=540)


def fig_coach_fit(fit: pd.DataFrame, team: str, margin: float = 5) -> go.Figure:
    d = fit.iloc[::-1]
    best = fit.iloc[0]["nombre"]
    colors = [ACCENT if n == best else LIGHT for n in d["nombre"]]
    labels = [f"<b>{r.nombre}</b><br><span style='font-size:11px;color:{GREY}'>p. ej. {r.ejemplos}</span>"
              for r in d.itertuples()]
    fig = go.Figure(go.Bar(
        x=d["encaje"], y=labels, orientation="h", marker=dict(color=colors, line=dict(color=NAVY, width=1)),
        text=[f"<b>{v:.0f}</b> / 100" for v in d["encaje"]], textposition="outside", cliponaxis=False,
        textfont=dict(size=14, color=NAVY), hovertemplate="Encaje %{x:.1f}/100<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 110], title="Encaje con el estilo actual del equipo (0–100)", showgrid=True, gridcolor=LIGHT)
    tie = fit.iloc[0]["encaje"] - fit.iloc[1]["encaje"] < margin
    headline = (f"Empate técnico entre «{fit.iloc[0]['nombre']}» y «{fit.iloc[1]['nombre']}»" if tie
                else f"«{best}» es el perfil de entrenador que mejor encaja con {team}")
    if tie:
        colors = [ACCENT if n in set(fit["nombre"].iloc[:2]) else LIGHT for n in d["nombre"]]
        fig.update_traces(marker_color=colors)
    return _base(fig, headline,
                 "Similitud entre el estilo del equipo y el estilo típico de cada perfil",
                 "Encaje = 100 − diferencia media en los cuatro ejes de estilo. Perfiles y ejemplos: config/coach_archetypes.yaml.",
                 height=400)


def fig_team_vs_archetype(profile: pd.DataFrame, archetypes: dict, key: str, team: str) -> go.Figure:
    a = archetypes["arquetipos"][key]
    d = profile[profile["tipo"].eq("estilo")].iloc[::-1].reset_index(drop=True)
    target = [float(a["perfil"][k]) for k in d["eje"]]
    fig = go.Figure()
    for i, (v, t) in enumerate(zip(d["indice"], target)):
        fig.add_shape(type="line", x0=min(v, t), x1=max(v, t), y0=i, y1=i, line=dict(color=LIGHT, width=6), layer="below")
    fig.add_trace(go.Scatter(x=target, y=d["etiqueta"], mode="markers", name=f"Perfil «{a['nombre']}»",
                             marker=dict(symbol="diamond", size=16, color="white", line=dict(color=NAVY, width=2)),
                             hovertemplate="Perfil: %{x:.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=d["indice"], y=d["etiqueta"], mode="markers", name=team,
                             marker=dict(size=18, color=ACCENT, line=dict(color=NAVY, width=1.5)),
                             hovertemplate=f"{team}: %{{x:.0f}}<extra></extra>"))
    fig.add_vline(x=50, line=dict(color=GREY, width=1, dash="dot"))
    fig.update_xaxes(range=[0, 100], title="Índice frente a sus rivales (0–100)", showgrid=True, gridcolor=LIGHT)
    fig.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=12)))
    return _base(fig, f"{team} frente al perfil «{a['nombre']}»",
                 "Cuanto más cerca estén el círculo y el rombo, mejor encaje", None, height=360, legend=True)


# ------------------------------------------------ 9. Perfil del entrenador
from plotly.subplots import make_subplots  # noqa: E402

SCORE_ORDER = ["losing", "drawing", "winning"]
REACTION_METRICS = [("posesion", "Posesión", "%"), ("presion_alta", "Presión en campo rival", "%"),
                    ("altura_bloque", "Altura de su defensa", "m"), ("pase_largo", "Pase largo", "%")]


def fig_formations(estructura: dict, team: str) -> go.Figure:
    d = pd.Series(estructura.get("dibujos", {})).sort_values()
    main = estructura.get("dibujo_principal")
    fig = go.Figure(go.Bar(
        x=d.values, y=d.index, orientation="h",
        marker_color=[ACCENT if k == main else NAVY for k in d.index],
        text=[f"{v} partido{'s' if v != 1 else ''}" for v in d.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x} partidos<extra></extra>",
    ))
    fig.update_xaxes(range=[0, d.max() * 1.25 if len(d) else 1], title="Partidos como dibujo inicial",
                     showgrid=True, gridcolor=LIGHT)
    fig.update_yaxes(type="category")
    return _base(fig, f"Dibujo habitual: {main} ({estructura.get('dibujo_principal_pct', 0):.0f} % de los partidos)",
                 f"Dibujos iniciales de {team}, reconstruidos con las posiciones de los titulares",
                 "Aproximado: se deduce de la posición de cada titular antes del primer cambio.",
                 height=max(300, 34 * len(d) + 170))


def fig_score_reaction(por_marcador: list[dict], team: str) -> go.Figure:
    d = pd.DataFrame(por_marcador).set_index("segmento").reindex(SCORE_ORDER).reset_index()
    labels = [SCORE_LABELS[s] for s in d["segmento"]]
    fig = make_subplots(rows=1, cols=4, subplot_titles=[f"{t} ({u})" for _, t, u in REACTION_METRICS],
                        horizontal_spacing=0.07)
    for i, (k, t, u) in enumerate(REACTION_METRICS, start=1):
        fig.add_trace(go.Scatter(x=labels, y=d[f"rival_{k}"], mode="lines+markers", name="Sus rivales en la misma situación",
                                 line=dict(color=GREY, width=2, dash="dot"), marker=dict(size=8, color=GREY),
                                 showlegend=i == 1, hovertemplate=f"Rivales · %{{x}}: %{{y:.1f}} {u}<extra></extra>"), row=1, col=i)
        fig.add_trace(go.Scatter(x=labels, y=d[k], mode="lines+markers", name=team,
                                 line=dict(color=ACCENT, width=3), marker=dict(size=11, color=ACCENT, line=dict(color=NAVY, width=1)),
                                 showlegend=i == 1, hovertemplate=f"{team} · %{{x}}: %{{y:.1f}} {u}<extra></extra>"), row=1, col=i)
        fig.update_yaxes(gridcolor=LIGHT, row=1, col=i)
        fig.update_xaxes(tickfont=dict(size=11), row=1, col=i)
    for a in fig.layout.annotations:
        a.font = dict(size=12, color=NAVY)
    fig.update_layout(legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=12)))
    return _base(fig, f"Cómo cambia {team} según el marcador",
                 "Cada panel: el equipo (amarillo) frente a sus rivales cuando están en la misma situación (gris)",
                 None, height=400, legend=True)


def fig_substitutions(gestion: dict, team: str) -> go.Figure:
    mins = pd.Series(gestion.get("minutos_cambios", []), dtype=float)
    fig = go.Figure(go.Histogram(x=mins, xbins=dict(start=0, end=100, size=5), marker_color=NAVY,
                                 marker_line=dict(color="white", width=1),
                                 hovertemplate="Minutos %{x}: %{y} cambios<extra></extra>"))
    med = gestion.get("primer_cambio_mediana")
    if med is not None:
        fig.add_vline(x=med, line=dict(color=ACCENT, width=3))
        fig.add_annotation(x=med, y=1.02, yref="paper", text=f"Primer cambio (mediana): min {med:.0f}",
                           showarrow=False, yanchor="bottom", font=dict(size=12, color=NAVY))
    fig.add_vrect(x0=45, x1=47, fillcolor=LIGHT, line_width=0, layer="below")
    fig.update_xaxes(range=[0, 100], dtick=15, title="Minuto de juego")
    fig.update_yaxes(title="Número de cambios")
    return _base(fig, f"Cuándo mueve el banquillo: {gestion.get('cambios_por_partido', 0):.1f} cambios por partido",
                 f"Minuto de los {len(mins)} cambios de {team}; franja gris = descanso",
                 "Incluye cambios por lesión, que no son decisiones tácticas.", height=380)


# ------------------------------------------- Informe de fútbol: once medio
def fig_average_positions(pos: pd.DataFrame, team: str) -> go.Figure:
    """Once más utilizado en su posición media con balón (coordenadas StatsBomb, ataca a la derecha)."""
    d = pos.dropna(subset=["x", "y"]).copy()
    d["sx"], d["sy"] = d["x"] / 0.9144, d["y"] / 0.9144
    fig = go.Figure()
    _pitch_shapes(fig)
    fig.add_trace(go.Scatter(
        x=d["sx"], y=d["sy"], mode="markers+text", text=d["etiqueta"], textposition="bottom center",
        textfont=dict(size=12, color=NAVY), cliponaxis=False,
        marker=dict(size=np.clip(10 + d["titularidades"], 14, 40), color=ACCENT, line=dict(color="white", width=2)),
        customdata=np.c_[d["player"], d["posicion_es"], d["titularidades"], d["x"]],
        hovertemplate="%{customdata[0]}<br>%{customdata[1]}<br>%{customdata[2]} titularidades"
                      "<br>Altura media con balón: %{customdata[3]:.0f} m<extra></extra>",
    ))
    fig.add_annotation(x=100, y=86, ax=70, ay=86, xref="x", yref="y", axref="x", ayref="y", text="",
                       showarrow=True, arrowhead=2, arrowwidth=1.5, arrowcolor=NAVY)
    fig.add_annotation(x=68, y=86, text="Dirección de ataque", showarrow=False, xanchor="right", font=dict(size=11, color=NAVY))
    fig.update_xaxes(range=[-3, 123], visible=False, constrain="domain")
    fig.update_yaxes(range=[90, -6], visible=False, scaleanchor="x", scaleratio=1)
    return _base(fig, f"El once de {team} tal como juega",
                 "Posición media con balón de los 11 jugadores con más titularidades; tamaño = titularidades",
                 "Mediana de la ubicación de pases, conducciones, recepciones, regates y tiros.", height=560)

# ------------------------------------------------------------- v2. CTS radar / similarity
CTS_LABELS = {
    "construction": "Construcción",
    "progression": "Progresión",
    "attack": "Ataque",
    "defense": "Defensa",
    "transition": "Transición",
    "adaptation": "Adaptación",
}


def fig_cts_radar(cts: dict, team: str) -> go.Figure:
    keys=["construction","progression","attack","defense","transition","adaptation"]
    vals=[cts.get(k) for k in keys]
    vals=[50.0 if v is None or pd.isna(v) else float(v) for v in vals]
    labels=[CTS_LABELS[k] for k in keys]
    fig=go.Figure(go.Scatterpolar(
        r=vals+[vals[0]], theta=labels+[labels[0]], fill="toself",
        fillcolor="rgba(37,99,235,.16)", line=dict(color=ACCENT,width=3),
        marker=dict(size=7,color=ACCENT),
        hovertemplate="%{theta}: %{r:.1f}/100<extra></extra>"
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0,100],tickvals=[20,40,60,80,100],gridcolor=LIGHT,linecolor=LIGHT),
                   angularaxis=dict(gridcolor=LIGHT,linecolor=LIGHT)),
        showlegend=False, margin=dict(l=45,r=45,t=80,b=35), height=470,
        paper_bgcolor="white",font=dict(family="Inter, Segoe UI, sans-serif",color=NAVY),
        title=dict(text=f"Firma táctica (CTS) · {team}",x=.02,y=.96,font=dict(size=19,color=NAVY)),
    )
    fig.add_annotation(x=.02,y=1.07,xref="paper",yref="paper",showarrow=False,xanchor="left",
                       text="Seis dimensiones 0–100; Adaptación usa recuperación observable tras tramos de desajuste.",
                       font=dict(size=11,color=GREY))
    return fig


def fig_similarity_bars(similarity_df: pd.DataFrame, team: str) -> go.Figure:
    d=similarity_df.head(6).sort_values("similitud")
    fig=go.Figure(go.Bar(x=d["similitud"],y=d["entrenador"],orientation="h",marker_color=ACCENT,
                         text=[f"{v:.0f}%" for v in d["similitud"]],textposition="outside",cliponaxis=False))
    fig.update_xaxes(range=[0,105],title="Similitud técnica (0–100)",gridcolor=LIGHT)
    return _base(fig,f"Perfiles de Liga MX más similares a {team}",
                 "Comparación entre perfiles CTS calculados con el mismo motor EFOS; no usa arquetipos europeos.",
                 "Solo se muestran equipos/DT con datos reales procesados en el repositorio.",height=max(320,55*len(d)+150))
