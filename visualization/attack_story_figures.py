"""Editorial, single-pitch EFOS attack visuals over *observed* events.

Same EFOS normalized sample as the narrative, never reconstructed tracking.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from visualization import efos_smart_attack_graphs as G


def _base(title: str, subtitle: str, height: int=530) -> go.Figure:
    f=go.Figure()
    G._pitch(f)
    G._axes(f)
    f.update_layout(paper_bgcolor=G.BG,plot_bgcolor=G.BG,
        title=dict(text=f"<b>{title}</b><br><span style='font-size:13px;color:{G.MUTED}'>{subtitle}</span>",
                   font=dict(size=20,color=G.INK),x=.04,xanchor="left"),
        font=dict(color=G.INK,size=13,family='Arial'),height=height,
        margin=dict(t=100,b=40,l=40,r=40),showlegend=False,
        hoverlabel=dict(bgcolor=G.PANEL,font_color=G.INK))
    return f


def _valid(g: pd.DataFrame) -> pd.DataFrame:
    return g[g.location_x.between(0,120)&g.location_y.between(0,80)].copy()


def figure_sequence_board(d: pd.DataFrame, sequence_key, *, max_actions: int = 14) -> go.Figure:
    """One observed possession segment; chronological numbered on-ball actions."""
    g=d[d['_poss_key'].isin([sequence_key])].sort_values('index',kind='stable')
    g=g[g['_type'].isin(['pass','carry','carries','shot','dribble'])]
    f=_base('Una secuencia, una historia',"Acciones numeradas · origen y destino registrados · ataque →",height=555)
    if g.empty:
        G._blank(f,"Sin acciones para la selección")
        return f
    g=_valid(g).head(max_actions)
    if g.empty:
        G._blank(f, 'La secuencia existe, pero sus acciones no tienen coordenadas válidas')
        return f
    for idx,(_,r) in enumerate(g.iterrows(),1):
        origin=(float(r.location_x),float(r.location_y))
        kind=str(r['_type'])
        color=G.CORAL if kind=='shot' else G.GOLD if kind in ('carry','carries') else G.TEAL
        if kind in ('pass','carry','carries') and pd.notna(r.end_location_x) and pd.notna(r.end_location_y):
            x,y=r.end_location_x,r.end_location_y
            if 0<=x<=120 and 0<=y<=80:
                G._arrow(f,origin,(float(x),float(y)),color,scale=3.2,
                    hover=f"{idx}. {str(r.player) if pd.notna(r.player) else 'Jugador'} · {kind} · {r.minute}′")
        f.add_trace(go.Scatter(x=[origin[0]],y=[origin[1]],mode='markers+text',
             text=[str(idx)],textposition='top center',textfont=dict(size=15,color=G.INK),
             marker=dict(size=12,color=color,line=dict(color=G.BG,width=1)),
             hovertemplate=f"{idx}. {r.get('player','Jugador')} · {r.get('event_type','')} · minuto {r.get('minute','—')}<extra></extra>"))
    f.add_annotation(text=f"{len(g)} acciones visibles · secuencia observada",
        x=.02,y=-.05,xref='paper',yref='paper',showarrow=False,xanchor='left',font=dict(size=12,color=G.MUTED))
    return f


def sequence_script(d: pd.DataFrame, sequence_key, max_lines: int=5) -> list[str]:
    """Literal event summary for the chosen sequence, no invented tactical actions."""
    g=d[d['_poss_key'].isin([sequence_key])].sort_values('index',kind='stable')
    g=g[g['_type'].isin(['pass','carry','carries','shot','dribble'])]
    out=[]
    for _,r in g.head(max_lines).iterrows():
        kind=str(r['_type'])
        who=str(r.get('player') or 'Jugador no identificado') if pd.notna(r.get('player')) else 'Jugador no identificado'
        if kind=='pass':
            recipient=r.get('pass_recipient_name');to=str(recipient) if pd.notna(recipient) else 'destino sin receptor identificado'
            state='completado' if bool(r['_pass_done']) else 'sin finalización confirmada'
            detail=f"{who} pasa a {to} ({state})"
        elif kind in ('carry','carries'):detail=f"{who} conduce el balón"
        elif kind=='shot':detail=f"{who} remata"
        elif kind=='dribble':detail=f"{who} realiza un regate registrado"
        else:detail=f"{who} interviene"
        out.append(detail)
    if len(g)>max_lines:out.append(f"… y {len(g)-max_lines} acciones adicionales en la misma secuencia")
    return out


def figure_attack_route(d: pd.DataFrame, stage: str="Progresión", *, max_actions: int=42) -> go.Figure:
    """Single full-size pitch with observed passes/carries, stage by *origin*.
    Do not interpret as formation or off-ball trajectories.
    """
    f=_base(f"Mapa de acciones · {stage.lower()}",
            "Trayectorias registradas de pases completos y conducciones · solo una muestra visual",height=515)
    masks={"Construcción":(0,40),"Progresión":(40,80),"Creación":(80,120.01)}
    low,high=masks.get(stage,masks['Progresión'])
    g=d[d['_type'].isin(['pass','carry','carries'])].copy()
    g=g[g['_pass_done']|g['_type'].isin(['carry','carries'])]
    g=G._xyvalid(g[g.location_x.ge(low)&g.location_x.lt(high)])
    n=len(g)
    if n==0:
        G._blank(f,"Sin acciones en este tramo")
        return f
    sample=g.iloc[::max(1,n//max_actions)].head(max_actions)
    for _,r in sample.iterrows():
        ispass=r['_type']=='pass'
        G._arrow(f,(float(r.location_x),float(r.location_y)),(float(r.end_location_x),float(r.end_location_y)),
                 G.TEAL if ispass else G.GOLD,scale=2.2,
                 hover=f"{r.get('player','')} · {r.get('event_type','')} · {r.get('minute','')}′")
    f.add_annotation(text=f"{len(sample)} trayectorias dibujadas de {n} · {g.match_id.nunique()} partidos",
        x=.02,y=-.05,xref='paper',yref='paper',showarrow=False,xanchor='left',font=dict(size=12,color=G.MUTED))
    return f


def figure_attack_outcomes(d: pd.DataFrame, view: str="Remates", max_points:int=110) -> go.Figure:
    """Observed endpoints; xG values size markers only when available."""
    f=_base('Dónde concluyen los ataques', 'Puntos observados · tamaño de remate proporcional al xG si existe',height=520)
    if view=="Remates":
        g=_valid(d[d['_type'].eq('shot')])
        n=len(g)
        if not n:
            G._blank(f,"Sin remates registrados")
            return f
        g=g.iloc[::max(1,n//max_points)].head(max_points)
        xg=pd.to_numeric(g.statsbomb_xg,errors='coerce')
        f.add_trace(go.Scatter(x=g.location_x,y=g.location_y,mode='markers',
            marker=dict(size=[12 if pd.isna(v) else 11+min(24,max(0,v)*40) for v in xg],
                        color=G.CORAL,opacity=.75,line=dict(width=1,color=G.BG)),
            customdata=np.column_stack([g.player.fillna('Sin nombre').astype(str),g.match_id.astype(str)]),
            hovertemplate='%{customdata[0]} · Partido %{customdata[1]}<extra></extra>'))
    else:
        a=d[d['_type'].isin(['pass','carry','carries'])]
        a=a[a['_pass_done']|a['_type'].isin(['carry','carries'])]
        box=a.end_location_x.ge(102)&a.end_location_y.between(18,62)&~(a.location_x.ge(102)&a.location_y.between(18,62))
        g=G._xyvalid(a.loc[box]);n=len(g)
        if not n:G._blank(f,"Sin entradas al área registradas");return f
        g=g.iloc[::max(1,n//max_points)].head(max_points)
        for _,r in g.iterrows():
            G._arrow(f,(float(r.location_x),float(r.location_y)),(float(r.end_location_x),float(r.end_location_y)),
                     G.GOLD,scale=1.8,hover=f"{r.get('player','')} · entrada al área")
    f.add_annotation(text=f"{len(g)} elementos visibles de {n} · no equivale a movimientos sin balón",
        x=.02,y=-.05,xref='paper',yref='paper',showarrow=False,xanchor='left',font=dict(size=12,color=G.MUTED))
    return f
