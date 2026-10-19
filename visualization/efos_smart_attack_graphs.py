"""EFOS | Ataque Organizado — seis gráficos para integrar con Streamlit.

Usa únicamente eventos observados y etiquetas explícitas. Los gráficos son
componentes autónomos: importar desde visualization/ y usar st.plotly_chart.

Requiere pandas, numpy, plotly.  Coordenadas StatsBomb 120 x 80 con el ataque
del equipo estudiado hacia x=120 (convenio original de eventos de ataque).
No muestra estructuras 3-2-5, desplazamientos sin balón ni posiciones del rival.
"""
from __future__ import annotations
from collections import Counter
import math
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BG = "#0C1520"
PANEL = "#142331"
LINE = "rgba(189,207,220,.28)"
INK = "#F1F5F7"
MUTED = "#96AEBF"
TEAL = "#45C4AE"
GOLD = "#E1AD58"
CORAL = "#EA7772"
BLUE = "#73A9EF"
NEG = "#D86B7F"
NEUTRAL = "#B2C3CE"
SETS = ("corner", "free kick", "throw-in", "throw in", "penalty", "kick off", "kick-off", "goal kick")
PASS_TYPES = ("corner", "free kick", "throw-in", "throw in", "goal kick", "kick off", "penalty")
START, END = (0, 120)


def prepare_events(raw: pd.DataFrame, team: str, *, open_play: bool = True) -> pd.DataFrame:
    """EFOS wide CSV or normalized columns. Keeps only selected team's on-ball possessions.

    Entire possession excluded on restart markers; do not treat restart continuations
    as organized attack. Team must be exact as recorded in team/team_name.
    """
    d = raw.copy()
    source_columns = set(d.columns)
    required = {'match_id', 'period', 'possession', 'index'}
    if not required.issubset(source_columns):
        raise ValueError('Faltan campos para secuencias: ' + ', '.join(sorted(required-source_columns)))
    outcome_available = bool({'pass_outcome', 'outcome_name'} & source_columns)
    d = d.replace(r'^\s*$', np.nan, regex=True)
    renamed = {
        "event_type_name": "event_type", "team_name": "team", "player_name": "player",
        "possession_team_name": "possession_team", "id": "event_id",
    }
    d = d.rename(columns={k:v for k,v in renamed.items() if v not in d and k in d})
    need = ("event_type", "team", "player", "match_id", "period", "possession", "index",
            "minute", "second", "location_x", "location_y", "end_location_x", "end_location_y",
            "pass_recipient_name", "play_pattern_name", "type_name", "outcome_name", "pass_outcome",
            "under_pressure", "pass_switch", "pass_cross", "statsbomb_xg", "obv_total_net")
    for c in need:
        if c not in d: d[c] = pd.NA
    if "possession_team" not in d:
        # Used only if the CSV lacks possession ownership; team acts as best-available proxy.
        d["possession_team"] = d["team"]
    numeric = ("period", "possession", "index", "minute", "second", "location_x", "location_y",
               "end_location_x", "end_location_y", "statsbomb_xg", "obv_total_net")
    for c in numeric: d[c] = pd.to_numeric(d[c], errors="coerce")
    d["match_id"] = d["match_id"].astype(str)
    if d["index"].isna().all(): d["index"] = np.arange(len(d))
    if d["period"].isna().all(): d["period"] = 1
    if d["possession"].isna().all():
        raise ValueError("Falta el identificador de posesión: necesario para reconstruir secuencias.")
    d = d.dropna(subset=['period', 'possession', 'index'])
    d['_seconds'] = pd.to_numeric(d['minute'], errors='coerce')*60 + pd.to_numeric(d['second'], errors='coerce')
    d["_type"] = d["event_type"].fillna("").astype(str).str.lower()
    d["_pass_done"] = d["_type"].eq("pass") & (
        d["pass_outcome"].isna() & d["outcome_name"].isna() |
        d["pass_outcome"].fillna("").astype(str).str.lower().isin(("complete", "success")) |
        d["pass_outcome"].isna() & d["outcome_name"].fillna("").astype(str).str.lower().isin(("complete", "success"))
    )
    if not outcome_available: d['_pass_done'] = False
    # A 'Shot' has an outcome; it must never affect pass completion.
    for c in ("under_pressure", "pass_switch", "pass_cross"):
        d["_" + c] = d[c].astype("string").fillna("false").str.lower().isin(("true", "1", "1.0", "yes"))
    d["_poss_key"] = list(zip(d["match_id"], d["period"], d["possession"]))
    if "event_id" in d:
        identified = d['event_id'].notna()
        d = pd.concat([d[identified].drop_duplicates(subset=['match_id','event_id']), d[~identified]])
    d = d.sort_values(["match_id", "period", "index"], kind="mergesort").reset_index(drop=True)
    if open_play:
        pat = d["play_pattern_name"].fillna("").astype(str).str.lower()
        pt = d["type_name"].fillna("").astype(str).str.lower()
        restarted = pat.apply(lambda s: any(x in s for x in SETS)) | (d["_type"].eq("pass") & pt.apply(lambda s: any(x in s for x in PASS_TYPES)))
        bad_keys = set(d.loc[restarted, "_poss_key"])
        d = d[~d["_poss_key"].isin(bad_keys)].copy()
    # Split evidence chains after opponent on-ball touches or explicit interruptions.
    blockers = d['_type'].isin(['ball out','offside','half end','foul committed','foul won']) | (
        d['team'].astype(str).ne(str(team)) & d['_type'].isin(['pass','carry','carries','interception','ball recovery','dispossessed']))
    d['_segment'] = blockers.groupby(d['_poss_key']).cumsum()
    d['_poss_key'] = [(*k, int(seg)) for k,seg in zip(d['_poss_key'],d['_segment'])]
    # Belongs to focal team possession, not every event in the match.
    d = d[d["possession_team"].astype(str).eq(str(team)) & d["team"].astype(str).eq(str(team))].copy()
    d.attrs['source_columns'] = sorted(source_columns)
    d.attrs['outcome_available'] = outcome_available
    d.attrs["team"] = team
    d.attrs["open_play"] = open_play
    return d.reset_index(drop=True)


def _style(fig, title, subtitle="", height=530, width=None):
    fig.update_layout(title=dict(text=f"<b>{title}</b><br><span style='font-size:12px;color:{MUTED}'>{subtitle}</span>",x=.03,xanchor="left",font=dict(size=20,color=INK)),
        height=height, width=width, paper_bgcolor=BG, plot_bgcolor=BG, font=dict(family="Arial",size=11,color=INK),
        margin=dict(l=25,r=25,t=115,b=95), showlegend=False, hoverlabel=dict(bgcolor=PANEL,font_color=INK),
        hovermode="closest")
    return fig


def _pitch(fig, xref="x", yref="y", vertical=False):
    """StatsBomb pitch. Vertical: own goal at bottom, attack toward top."""
    def tr(x,y): return (y,x) if vertical else (x,y)
    def ln(a,b,color=LINE,width=1,dash="solid"):
        x0,y0=tr(*a); x1,y1=tr(*b)
        fig.add_shape(type="line",x0=x0,y0=y0,x1=x1,y1=y1,xref=xref,yref=yref,line=dict(color=color,width=width,dash=dash),layer="below")
    def rect(x0,y0,x1,y1):
        a,b=tr(x0,y0); c,d=tr(x1,y1)
        fig.add_shape(type="rect",x0=a,y0=b,x1=c,y1=d,xref=xref,yref=yref,line=dict(color=LINE,width=1),fillcolor="rgba(0,0,0,0)",layer="below")
    rect(0,0,120,80);ln((60,0),(60,80))
    rect(0,18,18,62);rect(102,18,120,62)
    rect(0,30,6,50);rect(114,30,120,50)
    cx,cy=tr(60,40)
    fig.add_shape(type="circle",x0=cx-10,y0=cy-10,x1=cx+10,y1=cy+10,xref=xref,yref=yref,line=dict(color=LINE),layer="below")
    if vertical:
        fig.update_xaxes(range=[-2,82],visible=False,showgrid=False,zeroline=False)
        fig.update_yaxes(range=[-3,123],visible=False,showgrid=False,zeroline=False,scaleanchor=xref.replace('x','x') if xref!='x' else 'x',scaleratio=1)
    return tr


def _axes(fig, row=None, col=None, vertical=False):
    kw = dict(row=row,col=col) if row and col else {}
    fig.update_xaxes(range=([-2,82] if vertical else [-3,123]),visible=False,showgrid=False,zeroline=False,**kw)
    fig.update_yaxes(range=([-3,123] if vertical else [-3,83]),visible=False,showgrid=False,zeroline=False,**kw)


def _arrow(fig,a,b,color=TEAL,scale=1, row=None,col=None,vertical=False, hover=""):
    if any(pd.isna(v) for v in (*a,*b)):return
    x0,y0=(a[1],a[0]) if vertical else a
    x1,y1=(b[1],b[0]) if vertical else b
    kw=dict(row=row,col=col) if row and col else {}
    fig.add_trace(go.Scatter(x=[x0,x1],y=[y0,y1],mode="lines",line=dict(color=color,width=scale),opacity=.75,hovertext=hover,hoverinfo="text",showlegend=False),**kw)
    dx=x1-x0;dy=y1-y0
    if abs(dx)+abs(dy)>0.2:
        ang=np.degrees(np.arctan2(dy,dx))
        fig.add_trace(go.Scatter(x=[x1],y=[y1],mode="markers",marker=dict(symbol="arrow",size=max(7,min(10,4+scale)),color=color,angle=-ang,angleref="up"),hoverinfo="skip",showlegend=False),**kw)


def _blank(fig,txt,row=None,col=None,vertical=False):
    kw=dict(row=row,col=col) if row and col else {}
    fig.add_trace(go.Scatter(x=[40 if vertical else 60],y=[60 if vertical else 40],text=[txt],mode="text",textfont=dict(size=12,color=MUTED),hoverinfo="skip",showlegend=False),**kw)


def _all_passes(df):
    return df[df["_type"].eq("pass")].copy()


def _xyvalid(d):
    return d[d.location_x.between(0,120) & d.end_location_x.between(0,120) & d.location_y.between(0,80) & d.end_location_y.between(0,80)].copy()


def _legends(fig, labels):
    fig.add_annotation(x=0,y=-.10,xref="paper",yref="paper",showarrow=False,xanchor="left",text="  ·  ".join(labels),font=dict(size=11,color=MUTED))


def figure_identity_atlas(d):
    """Three-phase observed pass/carry route atlas. Curves and locations from real events only."""
    d=d[d["_type"].isin(["pass","carry","carries"])].copy()
    d=d[d["_pass_done"] | ~d["_type"].eq("pass")]
    phases=(("01 / CONSTRUCCIÓN",0,40),("02 / PROGRESIÓN",40,80),("03 / CREACIÓN",80,120.1))
    fig=make_subplots(rows=1,cols=3,subplot_titles=[p[0] for p in phases],horizontal_spacing=.035)
    for j,(title,low,hi) in enumerate(phases,1):
        sub=_xyvalid(d[d["location_x"].ge(low)&d["location_x"].lt(hi)])
        _pitch(fig,xref='x'+(str(j) if j>1 else ''),yref='y'+(str(j) if j>1 else ''))
        _axes(fig,1,j)
        if sub.empty:_blank(fig,"Sin eventos",1,j);continue
        # Display up to 38 actual observed trajectories; no invented centroids.
        sample=sub.sort_values(["match_id","period","index"]).iloc[::max(1,len(sub)//38)].head(38)
        for _,r in sample.iterrows():
            _arrow(fig,(r.location_x,r.location_y),(r.end_location_x,r.end_location_y),
                GOLD if r._type=="carry" else TEAL,scale=1.3,row=1,col=j,
                hover=f"{r.player}: {r._type} · {r.match_id} · {r.minute}′")
        n_pos=sub["_poss_key"].nunique(); n=len(sub)
        fig.add_annotation(x=.5,y=1.09,text=f"{n:,} acciones · {n_pos:,} posesiones",xref=f'x{j} domain' if j>1 else 'x domain',yref=f'y{j} domain' if j>1 else 'y domain',showarrow=False,font=dict(size=10,color=MUTED))
    _style(fig,"Atlas ofensivo | Dónde se construye y progresa", "Trayectorias observadas por zona de origen · muestra limitada para legibilidad",height=450)
    _legends(fig,["Verde: pases completos","Oro: conducciones","Todas las cifras proceden de eventos"])
    return fig


def figure_executive_lane_origins(possessions):
    """Pitch bands show *observed possession start lanes*, not an inferred path.

    The bands cover the field for visual orientation only. There are no arrows
    and no invented player locations; numbers are exact sample proportions.
    """
    valid = possessions[possessions['lane'].isin(('Izquierda', 'Centro', 'Derecha'))]
    counts = valid['lane'].value_counts()
    total = int(counts.sum())
    fig = go.Figure()
    _pitch(fig)
    _axes(fig)
    palette = {'Izquierda': 'rgba(69,196,174,1)',
               'Centro': 'rgba(225,173,88,1)', 'Derecha': 'rgba(115,169,239,1)'}
    for label, low, high in (('Izquierda', 0, 80/3), ('Centro', 80/3, 160/3), ('Derecha', 160/3, 80)):
        amount = int(counts.get(label, 0))
        pct = 100 * amount / total if total else 0
        intensity = .08 + .45 * amount / total if total else .08
        rgb = {'Izquierda': '69,196,174', 'Centro': '225,173,88', 'Derecha': '115,169,239'}[label]
        fig.add_shape(type='rect', x0=0, x1=120, y0=low, y1=high,
                      fillcolor=f'rgba({rgb},{intensity:.3f})',
                      line=dict(color='rgba(255,255,255,.17)', width=1),layer='below')
        fig.add_annotation(x=60,y=(low+high)/2, text=(f'<b>{label}</b> · {amount} de {total} ({pct:.1f}%)' if total
                       else f'{label} · sin datos'),font=dict(color=INK,size=15),
                       showarrow=False, bgcolor='rgba(12,21,32,.65)',borderpad=8)
    _style(fig,'Dónde comienzan las secuencias',
           f'Primer evento con coordenadas · {total} inicios válidos · juego abierto',height=400)
    fig.update_layout(margin=dict(l=22,r=22,t=94,b=38))
    return fig


def figure_pass_network(d, max_players=11, max_links=26, *, vertical=True, height=None):
    """Directional network of completed passes, with OBV applied to pass-link when available."""
    passes=_xyvalid(_all_passes(d));passes=passes[passes["_pass_done"] & passes["pass_recipient_name"].notna()]
    passes=passes[passes["player"].notna() & passes["player"].ne(passes["pass_recipient_name"])]
    fig=go.Figure();_pitch(fig,vertical=vertical);_axes(fig,vertical=vertical)
    if passes.empty:
        _blank(fig,"Sin pases completos con destinatario",vertical=True)
        return _style(fig,"Red de conexiones ofensivas","Hace falta pass_recipient_name y pases completos",height=height or (690 if vertical else 460))
    counts=pd.concat([passes["player"],passes["pass_recipient_name"]]).value_counts()
    players=set(counts.head(max_players).index)
    passes=passes[passes["player"].isin(players)&passes["pass_recipient_name"].isin(players)]
    coords={}
    for p in players:
        origin=passes.loc[passes["player"].eq(p),["location_x","location_y"]].to_numpy()
        dest=passes.loc[passes["pass_recipient_name"].eq(p),["end_location_x","end_location_y"]].to_numpy()
        xx=np.concatenate([origin,dest]) if len(origin)+len(dest) else np.zeros((0,2))
        if len(xx):coords[p]=(float(np.nanmedian(xx[:,0])),float(np.nanmedian(xx[:,1])))
    links=passes.groupby(["player","pass_recipient_name"],dropna=False).agg(
        n=("_pass_done","size"),obv=("obv_total_net","sum"),obv_n=("obv_total_net","count")).reset_index().sort_values("n",ascending=False).head(max_links)
    maxn=max(1,int(links["n"].max()))
    for _,r in links.iloc[::-1].iterrows():
        a,b=r["player"],r["pass_recipient_name"]
        if a not in coords or b not in coords:continue
        value=r['obv'];n=int(r['n'])
        color=TEAL if r['obv_n'] and value>0 else (CORAL if r['obv_n'] and value<0 else GOLD)
        ht=f"{a} → {b}<br>Completados: {n}"+(f"<br>OBV acumulado: {value:+.3f}" if r['obv_n'] else "<br>OBV: no disponible")
        _arrow(fig,coords[a],coords[b],color,scale=1+5*math.sqrt(n/maxn),vertical=vertical,hover=ht)
    for p in sorted(coords):
        x,y=coords[p]
        n=int(counts[p]); size=12+24*math.sqrt(n/max(1,counts.max()))
        fig.add_trace(go.Scatter(x=[y if vertical else x],y=[x if vertical else y],mode="markers+text",text=[str(p).split(" ")[-1]],
            textposition="top center",textfont=dict(color=INK,size=10),
            marker=dict(size=size,color=GOLD,line=dict(color=BG,width=2)),
            hovertemplate=f"{p}<br>Participaciones en enlaces: {n}<extra></extra>",showlegend=False))
    _style(fig,"Red de conexiones | Quién organiza el ataque",f"Pases completados · {passes['_poss_key'].nunique()} posesiones · aristas dirigidas · nodos en zonas medianas de evento",height=height or (700 if vertical else 460))
    _legends(fig,["Grosor: volumen de pases","Verde: OBV positivo","Coral: OBV negativo","Oro: OBV nulo/no disponible"])
    return fig


def _sequence_group(d, preferred_key=None):
    grouped=d.groupby("_poss_key",sort=False)
    if preferred_key is not None:
        if preferred_key not in grouped.groups:raise KeyError(f"Posesión no encontrada: {preferred_key}")
        return grouped.get_group(preferred_key)
    # choose visibly complex observed possession; explicit rule to avoid synthetic examples.
    quality=[]
    for k,g in grouped:
        if len(g)>=3:
            actions=int(g["_type"].isin(["pass","carry","carries"]).sum())
            shot=int(g["_type"].eq("shot").any())
            quality.append((shot, min(actions,15),len(g),str(k),k))
    if not quality:return d.iloc[0:0]
    quality.sort(reverse=True)
    return grouped.get_group(quality[0][-1]).sort_values("index",kind="mergesort")


def figure_tactical_sequence(d,possession_key=None):
    """Three snapshots of actual event sequence, grouped chronologically; not tracking."""
    fig=make_subplots(rows=1,cols=3,subplot_titles=["01 / INICIO","02 / PROGRESIÓN","03 / DESENLACE"],horizontal_spacing=.03)
    seq=_sequence_group(d,possession_key)
    for col in range(1,4):
        _pitch(fig,xref='x'+(str(col) if col>1 else ''),yref='y'+(str(col) if col>1 else ''))
        _axes(fig,1,col)
    if seq.empty:
        for i in range(1,4):_blank(fig,"No hay secuencia",1,i)
        return _style(fig,"Pizarra de secuencias reales","Sin posesiones con al menos tres eventos",height=460)
    moves=seq[seq["_type"].isin(["pass","carry","carries","shot","dribble"])]
    partitions=np.array_split(np.arange(len(moves)),3)
    for col,ix in enumerate(partitions,1):
        for order,(_,r) in enumerate(moves.iloc[ix].iterrows(),1):
            ax,ay=r.location_x,r.location_y
            if pd.isna(ax) or pd.isna(ay):continue
            clr=CORAL if r._type=="shot" else (GOLD if r._type=="carry" else TEAL)
            if r._type in ("pass","carry","carries") and pd.notna(r.end_location_x) and pd.notna(r.end_location_y):
                _arrow(fig,(ax,ay),(r.end_location_x,r.end_location_y),clr,scale=2.3,row=1,col=col,
                    hover=f"{r.player} · {r.event_type} · {r.minute}′")
            fig.add_trace(go.Scatter(x=[ax],y=[ay],mode="markers+text",text=[str(int(ix[order-1]+1))],
                textposition="top center",textfont=dict(color=INK,size=10),
                marker=dict(color=clr,size=9,line=dict(color=BG,width=1)),
                hovertemplate=f"{r.player} · {r.event_type} · minuto {r.minute}<extra></extra>",showlegend=False),row=1,col=col)
    key=seq.iloc[0]["_poss_key"]
    _style(fig,"Pizarra táctica | Secuencia observada",f"Partido {key[0]} · periodo {int(key[1])} · posesión {int(key[2])} · acciones numeradas en orden registrado",height=465)
    _legends(fig,["Verde: pase","Oro: conducción","Coral: remate","Sin desplazamientos inferidos"])
    return fig


def _after_pressure(d):
    """Every completed pressured pass and the recipient's next event in same possession.
    Mark evidence on follow-up rather than assumed decision or causality.
    """
    all_pass=d[(d["_type"].eq("pass"))&(d["_under_pressure"])&(d["_pass_done"]) & d["pass_recipient_name"].notna()].copy()
    res=[]
    for k,g in d.groupby("_poss_key",sort=False):
        g=g.sort_values("index").reset_index(drop=True)
        for i,r in g.iterrows():
            if r["_type"]!="pass" or not r["_under_pressure"] or not r["_pass_done"] or pd.isna(r["pass_recipient_name"]):continue
            forward=g.iloc[i+1:]
            forward=forward[forward['_type'].isin(['pass','carry','carries','dribble','shot','miscontrol','dispossessed'])]
            if len(forward) and str(forward.iloc[0]['player']) != str(r['pass_recipient_name']): forward=forward.iloc[0:0]
            nxt=forward.iloc[0] if len(forward) else None
            if nxt is not None and pd.notna(r["index"]) and pd.notna(nxt["index"]) and (nxt["index"]-r["index"]>6 or not (pd.notna(nxt["_seconds"]-r["_seconds"]) and 0<=nxt["_seconds"]-r["_seconds"]<=8)):nxt=None
            res.append((r,nxt))
    return res


def figure_pressure_exits(d):
    """Three-stage trace: pressured pass, receiver next action, observable outcome."""
    fig=make_subplots(rows=1,cols=3,subplot_titles=["01 / BAJO PRESIÓN","02 / SIGUIENTE ACCIÓN","03 / CONTINUIDAD"],horizontal_spacing=.03)
    for i in range(1,4):
        _pitch(fig,xref='x'+(str(i) if i>1 else ''),yref='y'+(str(i) if i>1 else ''))
        _axes(fig,1,i)
    links=_after_pressure(d)
    if not links:
        for i in range(1,4):_blank(fig,"Sin secuencias verificables",1,i)
        return _style(fig,"Salida bajo presión | Acción → continuación", "Requiere under_pressure, receptor y pases completos",height=470)
    # Focus on one audited pair (not invent an averaged path).
    r,nxt=next(((a,b) for a,b in links if b is not None),links[0])
    def point(row,col,clr):
        if row is None:return
        if pd.notna(row.location_x) and pd.notna(row.location_y):
            fig.add_trace(go.Scatter(x=[row.location_x],y=[row.location_y],mode="markers",marker=dict(size=11,color=clr),
                hovertemplate=f"{row.player} · {row.event_type} · {row.minute}′<extra></extra>"),row=1,col=col)
    if pd.notna(r.location_x) and pd.notna(r.end_location_x) and pd.notna(r.location_y) and pd.notna(r.end_location_y):
        _arrow(fig,(r.location_x,r.location_y),(r.end_location_x,r.end_location_y),GOLD,3,row=1,col=1,
            hover=f"{r.player} → {r.pass_recipient_name} · pase bajo presión")
    point(r,1,GOLD)
    if nxt is not None:
        point(nxt,2,TEAL)
        if pd.notna(nxt.end_location_x) and pd.notna(nxt.end_location_y):
            _arrow(fig,(nxt.location_x,nxt.location_y),(nxt.end_location_x,nxt.end_location_y),TEAL,3,row=1,col=2,hover=f"{nxt.player} · siguiente acción")
        point(nxt,3,TEAL)
        if pd.notna(nxt.end_location_x) and pd.notna(nxt.end_location_y):
            fig.add_trace(go.Scatter(x=[nxt.end_location_x],y=[nxt.end_location_y],mode="markers",marker=dict(symbol="circle-open",size=18,color=TEAL,line=dict(width=3)),hovertemplate="Fin de la acción registrada<extra></extra>"),row=1,col=3)
    else:
        _blank(fig,"Siguiente acción no disponible",1,2);_blank(fig,"Continuación no observable",1,3)
    paired=sum(1 for a,b in links if b is not None)
    _style(fig,"Salida bajo presión | Qué ocurre después",f"{len(links)} pases completos bajo presión con receptor · {paired} con siguiente acción observada · caso mostrado: partido {r.match_id} {r.minute}′",height=465)
    _legends(fig,["Ejemplo real de la selección","Una acción bajo presión no prueba atracción deliberada"])
    return fig


def figure_halfspace_receptions(d):
    """Receipts in geometric half-spaces, not proven between opposition lines."""
    p=_xyvalid(_all_passes(d)); p=p[p["_pass_done"] & p["pass_recipient_name"].notna()].copy()
    # Definition is explicit/configurable: 16 <= y < 30 and 50 < y <= 64, x >= 40.
    m=(p["end_location_x"].between(70,95) & ((p["end_location_y"].between(18,30)) | (p["end_location_y"].between(50,62))))
    p=p[m]
    fig=go.Figure();_pitch(fig);_axes(fig)
    for y0,y1 in ((18,30),(50,62)):
        fig.add_shape(type="rect",x0=70,x1=95,y0=y0,y1=y1,fillcolor="rgba(225,173,88,.15)",line=dict(width=0),layer="below")
    if p.empty:
        _blank(fig,"No hay recepciones en los pasillos definidos")
    else:
        p2=p.sort_values(["match_id","period","index"]).iloc[::max(1,len(p)//140)].head(140)
        who=p2["pass_recipient_name"].fillna("Sin identificar")
        fig.add_trace(go.Scatter(x=p2["end_location_x"],y=p2["end_location_y"],mode="markers",
            marker=dict(size=7,color=p2["_under_pressure"].map({True:CORAL,False:TEAL}),opacity=.75,line=dict(width=1,color=BG)),
            text=[f"{a} → {b}<br>{mid} · {minuto}′<br>Bajo presión: {'sí' if pp else 'no etiquetado'}" for a,b,mid,minuto,pp in zip(p2["player"],who,p2["match_id"],p2["minute"],p2["_under_pressure"])],hoverinfo="text"))
        # Receiver follow-up via same-possession events (not off-ball movement).
        continuation=[]
        for k,g in d.groupby("_poss_key",sort=False):
            g=g.sort_values("index").reset_index(drop=True)
            for ix,r in g.iterrows():
                if not (r["_type"]=="pass" and r["_pass_done"] and r["pass_recipient_name"] is not pd.NA and pd.notna(r["pass_recipient_name"])):continue
                if not (pd.notna(r.end_location_x) and pd.notna(r.end_location_y) and 70<=r.end_location_x<=95 and (18<=r.end_location_y<=30 or 50<=r.end_location_y<=62)):continue
                fw=g.iloc[ix+1:]
                fw=fw[fw['_type'].isin(['pass','carry','carries','shot','dribble','miscontrol','dispossessed'])]
                if len(fw) and str(fw.iloc[0]['player']) != str(r.pass_recipient_name): fw=fw.iloc[0:0]
                if len(fw):
                    nxt=fw.iloc[0]
                    if pd.notna(nxt.end_location_x) and pd.notna(nxt.end_location_y) and nxt["index"]-r["index"]<=6 and pd.notna(nxt["_seconds"]-r["_seconds"]) and 0<=nxt["_seconds"]-r["_seconds"]<=8:
                        continuation.append((r,nxt))
        # Include at most eight next actions; all other counts remain uncapped.
        for r,nxt in continuation[:8]:
            _arrow(fig,(r.end_location_x,r.end_location_y),(nxt.end_location_x,nxt.end_location_y),GOLD,1.8,hover=f"{r.pass_recipient_name}: siguiente acción")
        detail=f"{len(p):,} recepciones observadas · {len(continuation):,} continuaciones con movimiento etiquetado"
    _style(fig,"Recepciones interiores | Qué hace después el receptor",detail if len(p) else "Half-spaces geométricos · no equivale a recepción entre líneas",height=580)
    _legends(fig,["Franjas oro: definición espacial EFOS","Verde: pase sin presión marcada","Coral: pase etiquetado bajo presión","Oro: siguiente acción observada"])
    return fig


def figure_final_routes(d):
    """Observed passes/carries into final third and passes into box, plus linked shots.
    Same-possession shots are associated, not claimed caused by prior pass.
    """
    fig=make_subplots(rows=1,cols=3,subplot_titles=["01 / PASE AL ÚLTIMO TERCIO","02 / CONDUCCIÓN AL ÚLTIMO TERCIO","03 / ENTRADA AL ÁREA"],horizontal_spacing=.03)
    for i in range(1,4):
        _pitch(fig,xref='x'+(str(i) if i>1 else ''),yref='y'+(str(i) if i>1 else ''))
        _axes(fig,1,i)
    valid=_xyvalid(d)
    to_last=valid[valid["location_x"].lt(80)&valid["end_location_x"].ge(80)]
    p1=to_last[to_last["_pass_done"]]
    p2=to_last[to_last["_type"].isin(["carry","carries"])]
    p3=valid[(valid["_type"].eq("pass")) & valid["_pass_done"] &
             (valid["end_location_x"].ge(102)) & (valid["end_location_y"].between(18,62)) &
             ~(valid["location_x"].ge(102) & valid["location_y"].between(18,62))]
    shots=d[d["_type"].eq("shot")]
    for i,ds in enumerate((p1,p2,p3),1):
        if ds.empty:
            _blank(fig,"Sin eventos registrados",1,i);continue
        subset=ds.sort_values(["match_id","period","index"]).iloc[::max(1,len(ds)//36)].head(36)
        for _,r in subset.iterrows():
            clr=GOLD if i==2 else TEAL
            _arrow(fig,(r.location_x,r.location_y),(r.end_location_x,r.end_location_y),clr,1.6,1,i,hover=f"{r.player} · {r.event_type}")
        keys=set(ds["_poss_key"])
        # A shot may be associated only if observed AFTER the entry in that same possession.
        first_entry=ds.groupby("_poss_key")["index"].min().to_dict()
        shot_grp=shots[shots["_poss_key"].isin(keys) & shots["location_x"].notna() & shots["location_y"].notna()].copy()
        shot_grp=shot_grp[shot_grp.apply(lambda r: r["index"]>first_entry.get(r["_poss_key"],float("inf")),axis=1)]
        if not shot_grp.empty:
            shot_grp=shot_grp.head(36)
            fig.add_trace(go.Scatter(x=shot_grp["location_x"],y=shot_grp["location_y"],mode="markers",
                marker=dict(color=CORAL,size=8,symbol="diamond"),text=[f"Remate {s.player} | xG: {s.statsbomb_xg if pd.notna(s.statsbomb_xg) else 'sin dato'}" for _,s in shot_grp.iterrows()],hoverinfo="text"),row=1,col=i)
        shot_poses=int(sum(r['index'] > first_entry.get(r['_poss_key'],float('inf')) for _,r in shots.iterrows()))
        fig.add_annotation(x=.5,y=1.09,xref=f'x{i} domain' if i>1 else 'x domain',yref=f'y{i} domain' if i>1 else 'y domain',
            text=f"{len(ds):,} entradas · {len(keys):,} posesiones · {shot_poses} remates vinculados",showarrow=False,font=dict(size=10,color=MUTED))
    _style(fig,"Rutas de llegada | De la progresión al remate", "Trayectorias de eventos · remates en la misma posesión, no atribución causal",height=465)
    _legends(fig,["Verde: pase","Oro: conducción","Coral: remate posterior en posesión"])
    return fig



def _find_abc(d):
    """Linked progressive passes within 4 seconds; no off-ball third-man claim."""
    result=[]
    for key,g in d.groupby('_poss_key',sort=False):
        actions=g[g['_type'].isin(['pass','carry','carries','dribble','shot','miscontrol','dispossessed'])].sort_values('index')
        rows=list(actions.to_dict('records'))
        for a,b in zip(rows,rows[1:]):
            if not (a['_pass_done'] and b['_pass_done']): continue
            if pd.isna(a['pass_recipient_name']) or pd.isna(b['pass_recipient_name']): continue
            dt=b['_seconds']-a['_seconds']
            if not (pd.notna(dt) and 0 <= dt <= 4): continue
            if a['pass_recipient_name'] != b['player']: continue
            if len({str(a['player']),str(b['player']),str(b['pass_recipient_name'])}) != 3: continue
            if b['end_location_x']-a['location_x'] >= 15 and b['end_location_x']-b['location_x'] >= 8:
                result.append((a,b,key))
    return result


def figure_mechanism_board(d):
    """Four fact-based tactical whiteboards: switches, A-B-C, interior receipts, crosses."""
    p=_xyvalid(_all_passes(d));p=p[p["_pass_done"]]
    switches=p[p["_pass_switch"] & (p["end_location_y"]-p["location_y"]).abs().ge(20)]
    abc=_find_abc(d)
    half=p[p["end_location_x"].between(70,95) & ((p["end_location_y"].between(18,30)) | p["end_location_y"].between(50,62))]
    crosses=p[p["_pass_cross"]]
    tiles=[("01 / CAMBIO DE ORIENTACIÓN",len(switches)),("02 / COMBINACIÓN A→B→C",len(abc)),("03 / RECEPCIÓN INTERIOR",len(half)),("04 / CENTRO REGISTRADO",len(crosses))]
    fig=make_subplots(rows=2,cols=2,subplot_titles=[v[0]+f" · {v[1]}" for v in tiles],horizontal_spacing=.08,vertical_spacing=.16)
    for row in (1,2):
        for col in (1,2):
            axis=(row-1)*2+col
            _pitch(fig,xref="x"+(str(axis) if axis>1 else ""),yref="y"+(str(axis) if axis>1 else ""))
            _axes(fig,row,col)
    for col,sub in [(1,switches),(2,half),(3,crosses)]:
        actual_row,actual_col={1:(1,1),2:(2,1),3:(2,2)}[col]
        if sub.empty:_blank(fig,"Sin ejemplos",actual_row,actual_col);continue
        for _,r in sub.head(7).iterrows():
            _arrow(fig,(r.location_x,r.location_y),(r.end_location_x,r.end_location_y),TEAL if col<3 else GOLD,
                    2,row=actual_row,col=actual_col,hover=f"{r.player} → {r.pass_recipient_name} | {r.match_id} {r.minute}′")
    if abc:
        for a,b,key in abc[:4]:
            try:
                _arrow(fig,(a["location_x"],a["location_y"]),(a["end_location_x"],a["end_location_y"]),TEAL,2,row=1,col=2,
                    hover=f"A→B: {a['player']} → {a['pass_recipient_name']} | {key}")
                _arrow(fig,(b["location_x"],b["location_y"]),(b["end_location_x"],b["end_location_y"]),GOLD,2,row=1,col=2,
                    hover=f"B→C: {b['player']} → {b['pass_recipient_name']} | {key}")
            except (ValueError,TypeError):continue
    else:_blank(fig,"Sin A→B→C verificables",1,2)
    _style(fig,"Pizarras de mecanismos | Patrones del ataque", "Acciones observadas de juego abierto · A→B→C no demuestra por sí solo tercer hombre",height=700)
    _legends(fig,["Verde: pases completos","Oro: centro o segundo pase","Las flechas son eventos, no carreras sin balón"])
    return fig


def figure_primary_network_atlas(d, max_players=9, max_links=14):
    """Atlas de redes ofensivas principales en small multiples.

    Paneles basados en patrones observables del texto del módulo de ataque.
    No representa formaciones ni posiciones simultáneas, solo zonas medianas
    de intervención y conexiones de pase observadas en juego abierto.
    """
    passes=_xyvalid(_all_passes(d))
    passes=passes[passes["_pass_done"] & passes["pass_recipient_name"].notna()].copy()
    passes=passes[passes["player"].notna() & passes["player"].ne(passes["pass_recipient_name"])]

    def _pattern(name):
        if name=="Salida por derecha":
            return passes[(passes["location_x"]<80) & (passes["location_y"]>=45)]
        if name=="Salida por izquierda":
            return passes[(passes["location_x"]<80) & (passes["location_y"]<=35)]
        if name=="Conexión interior":
            return passes[(passes["location_y"].between(22,58)) & (passes["end_location_y"].between(22,58))]
        if name=="Cambio de orientación":
            return passes[(passes["_pass_switch"]) & ((passes["end_location_y"]-passes["location_y"]).abs()>=20)]
        if name=="Recepción en medio espacio":
            return passes[(passes["end_location_x"].between(70,95)) & (((passes["end_location_y"].between(18,30)) | (passes["end_location_y"].between(50,62))))]
        if name=="Ruta de llegada":
            return passes[((passes["end_location_x"].ge(90)) | ((passes["end_location_x"].ge(102)) & (passes["end_location_y"].between(18,62))))]
        return passes.iloc[0:0]

    panels=[
        ("Salida por derecha","Receptor clave"),
        ("Salida por izquierda","Receptor clave"),
        ("Conexión interior","Receptor clave"),
        ("Cambio de orientación","Receptor clave"),
        ("Recepción en medio espacio","Receptor clave"),
        ("Ruta de llegada","Receptor clave"),
    ]
    subtitles=[]
    for name,_ in panels:
        sub=_pattern(name)
        subtitles.append(f"{name}<br><span style='font-size:10px;color:{MUTED}'>{sub['_poss_key'].nunique()} posesiones · {sub['match_id'].nunique()} partidos</span>")

    fig=make_subplots(rows=2, cols=3, subplot_titles=subtitles, horizontal_spacing=.05, vertical_spacing=.12)

    def _xaxis_id(idx):
        return 'x' if idx==1 else f'x{idx}'
    def _yaxis_id(idx):
        return 'y' if idx==1 else f'y{idx}'

    def _draw_panel(sub,row,col,idx):
        xref=_xaxis_id(idx); yref=_yaxis_id(idx)
        _pitch(fig,xref=xref,yref=yref,vertical=True); _axes(fig,row,col,vertical=True)
        if sub.empty:
            _blank(fig,'Sin eventos suficientes',row,col,vertical=True)
            return
        counts=pd.concat([sub['player'],sub['pass_recipient_name']]).value_counts()
        players=set(counts.head(max_players).index)
        sub=sub[sub['player'].isin(players)&sub['pass_recipient_name'].isin(players)]
        coords={}
        for pl in players:
            origin=sub.loc[sub['player'].eq(pl),['location_x','location_y']].to_numpy()
            dest=sub.loc[sub['pass_recipient_name'].eq(pl),['end_location_x','end_location_y']].to_numpy()
            xx=np.concatenate([origin,dest]) if len(origin)+len(dest) else np.zeros((0,2))
            if len(xx): coords[pl]=(float(np.nanmedian(xx[:,0])),float(np.nanmedian(xx[:,1])))
        if not coords:
            _blank(fig,'Sin red verificable',row,col,vertical=True)
            return
        links=sub.groupby(['player','pass_recipient_name'],dropna=False).agg(
            n=('_pass_done','size'), obv=('obv_total_net','sum'), obv_n=('obv_total_net','count')).reset_index().sort_values('n',ascending=False).head(max_links)
        maxn=max(1,int(links['n'].max())) if len(links) else 1
        for _,r in links.iloc[::-1].iterrows():
            a,b=r['player'],r['pass_recipient_name']
            if a not in coords or b not in coords: continue
            val=r['obv']; n=int(r['n'])
            color=TEAL if r['obv_n'] and val>0 else (CORAL if r['obv_n'] and val<0 else GOLD)
            _arrow(fig,coords[a],coords[b],color,scale=0.8+3.6*math.sqrt(n/maxn),row=row,col=col,vertical=True,hover=f"{a} → {b}<br>Pases: {n}" + (f"<br>OBV: {val:+.3f}" if r['obv_n'] else ''))
        for pl in sorted(coords):
            x,y=coords[pl]
            n=int(counts[pl]); size=7+13*math.sqrt(n/max(1,counts.max()))
            # observed outgoing pass value using outgoing pass OBV where available
            pv=float(sub.loc[sub['player'].eq(pl),'obv_total_net'].sum(min_count=1)) if 'obv_total_net' in sub else 0.0
            color=NEUTRAL if pd.isna(pv) else CORAL if pv<0 else (GOLD if pv<0.08 else ('#9CCF6A' if pv<0.20 else TEAL))
            fig.add_trace(go.Scatter(x=[y],y=[x],mode='markers',marker=dict(size=size,color=color,line=dict(color=BG,width=1.6)),
                                     hovertemplate=f"{pl}<br>Participaciones: {n}<extra></extra>",showlegend=False),row=row,col=col)
        # footer text inside each panel
        top_link=links.iloc[0] if len(links) else None
        rec=sub['pass_recipient_name'].value_counts().index[0] if len(sub) else 'n/d'
        obv=sub['obv_total_net'].sum(min_count=1) if 'obv_total_net' in sub else float('nan')
        txt=f"Pases: {len(sub)}<br>Valor: {obv:.2f} OBV" if pd.notna(obv) else f"Pases: {len(sub)}<br>Valor: n/d"
        txt += f"<br>Receptor clave: {str(rec).split(' ')[-1]}"
        fig.add_annotation(x=0.02, y=-0.08, xref=f'{xref} domain', yref=f'{yref} domain', text=txt, showarrow=False, align='left', xanchor='left', yanchor='top', font=dict(size=9,color=MUTED))

    for idx,(name,_) in enumerate(panels, start=1):
        row=1 if idx<=3 else 2; col=((idx-1)%3)+1
        _draw_panel(_pattern(name), row, col, idx)

    _style(fig, 'Atlas de redes ofensivas principales', 'Seis patrones observables de ataque organizado · small multiples inspirados en un board editorial', height=980)
    _legends(fig,['Grosor de línea: volumen de pases','Verde: valor positivo de la conexión','Oro/Coral: valor neutro o negativo','Tamaño del nodo: participación'])
    return fig


def build_all_figures(events: pd.DataFrame, team: str, *, open_play: bool=True) -> dict[str,go.Figure]:
    """Returns the offensive figure set, ready for Streamlit or exporting HTML."""
    d=prepare_events(events,team,open_play=open_play)
    return {
        "01_Atlas_Identidad_Ofensiva":figure_identity_atlas(d),
        "08_Atlas_Redes_Ofensivas_Principales":figure_primary_network_atlas(d),
        "02_Red_Conexiones_Dirigidas":figure_pass_network(d),
        "03_Pizarras_Mecanismos":figure_mechanism_board(d),
        "04_Pizarra_Secuencia_Real":figure_tactical_sequence(d),
        "05_Salida_Bajo_Presion":figure_pressure_exits(d),
        "06_Recepciones_Interiores":figure_halfspace_receptions(d),
        "07_Rutas_Llegada_Finalizacion":figure_final_routes(d),
    }
