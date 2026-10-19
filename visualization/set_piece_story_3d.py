"""EFOS premium Plotly 3D *illustration* for set-piece restarts.

Uses P0 coordinates already identified by EFOS Set Piece Story. The 3D z
coordinate is categorical visual relief: it is NOT measured ball elevation,
flight path, player tracking, or an inferred point of first contact.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go

INK = "#132136"
GOLD = "#C79A3D"
BLUE = "#426B98"
WHITE = "#FCFCFE"
GRID = "#CBD4E1"


def _valid_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    valid = pd.Series(True, index=df.index)
    for col, min_val, max_val in [
        ("start_x",0,120), ("end_x",0,120),
        ("start_y",0,80), ("end_y",0,80),
    ]:
        if col not in df:
            return df.iloc[:0].copy()
        valid &= pd.to_numeric(df[col], errors="coerce").between(min_val, max_val)
    return df.loc[valid].copy()


def available_views(sequences: pd.DataFrame, profile: dict) -> list[str]:
    """Only expose evidence-backed selection options."""
    choices = []
    if profile.get("frequent"):
        choices.append("Patrón más repetido")
    if profile.get("productive"):
        choices.append("Patrón con mayor xG")
    for flank in ("Izquierda", "Derecha"):
        if "flank" in sequences and sequences["flank"].eq(flank).any():
            choices.append("Desde " + flank.lower())
    return choices


def select_view(sequences: pd.DataFrame, profile: dict, view: str) -> pd.DataFrame:
    """Return actual observed executions. Selection is independent of display caps."""
    if sequences.empty:
        return sequences.copy()
    if view == "Patrón más repetido":
        p = profile.get("frequent")
        return sequences[sequences["flank"].eq(p["flank"]) &
                         sequences["target_zone"].eq(p["zone"])].copy() if p else sequences.iloc[:0].copy()
    if view == "Patrón con mayor xG":
        p = profile.get("productive")
        return sequences[sequences["flank"].eq(p["flank"]) &
                         sequences["target_zone"].eq(p["zone"])].copy() if p else sequences.iloc[:0].copy()
    if view.startswith("Desde "):
        return sequences[sequences["flank"].eq(view.replace("Desde ", "").capitalize())].copy()
    return sequences.iloc[:0].copy()


def _line(fig, xs, ys, zs=None, color=GRID, width=2):
    if zs is None:zs=[0.02]*len(xs)
    fig.add_trace(go.Scatter3d(x=xs,y=ys,z=zs,mode="lines",line=dict(color=color,width=width),
                               hoverinfo="skip",showlegend=False))


def _pitch(fig):
    # Geometry: Plotly x = StatsBomb y; Plotly y = StatsBomb x; z is illustration-only.
    fig.add_trace(go.Mesh3d(x=[0,80,80,0],y=[80,80,120,120],z=[0,0,0,0],
                            i=[0,0],j=[1,2],k=[2,3],color=WHITE,opacity=.94,
                            hoverinfo="skip",showlegend=False))
    _line(fig,[0,80,80,0,0],[80,80,120,120,80],width=4)
    _line(fig,[18,62,62,18,18],[102,102,120,120,102],width=3)
    _line(fig,[30,50,50,30,30],[114,114,120,120,114],width=3)
    _line(fig,[36,44],[120,120],color=INK,width=7)
    _line(fig,[40,40],[108,108],color=GRID,width=5)


def _height_class(value):
    """Illustrative tiers, never physical metres; unobserved stays on ground plane."""
    if pd.isna(value):return "Altura sin dato; arco puramente ilustrativo", 0.63
    name = str(value).strip().lower()
    if "ground" in name or "raso" in name:return "Pase raso (etiqueta)", 0.0
    if "low" in name or "bajo" in name:return "Pase bajo (etiqueta)", 0.42
    if "high" in name or "alto" in name:return "Pase alto (etiqueta)", 0.85
    return "Altura sin categoría válida; arco ilustrativo", 0.63


def spatial_illustration(data: pd.DataFrame, max_events: int = 8) -> tuple[go.Figure, dict]:
    """3D without fabricated flight heights; categorical relief only when labeled.

    Always display the first N chronological eligible executions with full disclosure.
    """
    if not 1 <= max_events <= 20:
        raise ValueError("max_events must be between 1 and 20")
    valid = _valid_coordinates(data)
    valid = valid.sort_values([c for c in ("match_id", "period", "t0", "set_piece_id") if c in valid],
                              kind="stable")
    total = len(valid)
    selected = valid.head(max_events)
    fig=go.Figure()
    _pitch(fig)
    tagged=0
    for _,r in selected.iterrows():
        (x0,y0,x1,y1)=(float(r["start_x"]), float(r["start_y"]),
                       float(r["end_x"]), float(r["end_y"]))
        cls, relieve=_height_class(r.get("pass_height_name"))
        if cls.startswith("Pase "):tagged+=1
        t=np.linspace(0,1,28)
        # z is categorically illustrative, not inferred ball height in metres.
        z=relieve*np.sin(np.pi*t)
        color=GOLD if str(r.get("flank"))=="Izquierda" else BLUE
        fig.add_trace(go.Scatter3d(x=y0+(y1-y0)*t,y=x0+(x1-x0)*t,z=z,
             mode="lines",line=dict(color=color,width=5),showlegend=False,
             text=[f"{r.get('flank','')} · {r.get('executor','Sin ejecutor')} · "
                   f"{r.get('target_zone','Sin zona')} · {cls}"]*len(t),
             hovertemplate="%{text}<extra></extra>"))
        fig.add_trace(go.Scatter3d(x=[y1],y=[x1],z=[0],mode="markers",
             marker=dict(color=color,size=4,opacity=.9),showlegend=False,
             customdata=[[r.get("match_id"),r.get("target_zone")]],
             hovertemplate="Partido: %{customdata[0]}<br>Destino registrado: %{customdata[1]}<extra></extra>"))
    fig.update_layout(
      height=520, paper_bgcolor="rgba(0,0,0,0)",
      font=dict(color=INK,family="Inter, -apple-system, sans-serif",size=12),
      margin=dict(l=0,r=0,t=8,b=0),showlegend=False,
      scene=dict(bgcolor="rgba(255,255,255,0)",
         xaxis=dict(title="",range=[-3,83],showbackground=False,visible=False,showgrid=False),
         yaxis=dict(title="",range=[79,122],showbackground=False,visible=False,showgrid=False),
         zaxis=dict(title="",range=[0,1.9],showbackground=False,visible=False,showgrid=False),
         camera=dict(eye=dict(x=1.6,y=-1.85,z=1.16),up=dict(x=0,y=0,z=1)),
         aspectmode="manual",aspectratio=dict(x=1.2,y=.85,z=.31)),
      uirevision="efos_premium_set_piece")
    return fig,{"observations_with_coordinates":total,"drawn":len(selected),
                "drawn_with_labeled_height_relief":tagged,
                "method":"ILLUSTRATIVE_CATEGORICAL_RELIEF_NOT_MEASURED_TRAJECTORY"}
