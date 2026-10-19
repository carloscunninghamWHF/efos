"""EFOS Smart Defensive Tactics · evidence-first Plotly visualizations.
All drawings are grounded in StatsBomb event coordinates or 360 freeze-frame points.
"""
from __future__ import annotations
from itertools import combinations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from intelligence.defensive_open_play import STATES, DEFENSE_TYPES, MINUTE_BANDS, kpis, event_detail, time_summary

NAVY='#152438'; BLUE='#507FAF'; AMBER='#C6994C'; RED='#D56A6A'; GREEN='#377D65'; MUTED='#748499'; LINE='#C5D2D3'; PITCH='#F8FAF8'


def _pitch(fig,row=1,col=1,xref='x',yref='y',horizontal=True):
    # Native StatsBomb 120 x 80 coordinates; opponent attacking to +x.
    xvals=[0,120] if horizontal else [0,80]
    yvals=[0,80] if horizontal else [0,120]
    def ln(x0,y0,x1,y1,width=1):
        fig.add_shape(type='line',x0=x0,y0=y0,x1=x1,y1=y1,
                      line=dict(color=LINE,width=width),row=row,col=col)
    fig.add_shape(type='rect',x0=0,y0=0,x1=xvals[-1],y1=yvals[-1],
                  fillcolor=PITCH,line=dict(color=LINE,width=1),layer='below',row=row,col=col)
    ln(60,0,60,80)
    fig.add_shape(type='circle',x0=50,y0=30,x1=70,y1=50,line=dict(color=LINE,width=1),row=row,col=col)
    for x0,x1 in [(0,18),(102,120)]:
        fig.add_shape(type='rect',x0=x0,y0=18,x1=x1,y1=62,
                     fillcolor='rgba(0,0,0,0)',line=dict(color=LINE,width=1),row=row,col=col)
    for x0,x1 in [(0,6),(114,120)]:
        fig.add_shape(type='rect',x0=x0,y0=30,x1=x1,y1=50,
                     fillcolor='rgba(0,0,0,0)',line=dict(color=LINE,width=1),row=row,col=col)
    fig.update_xaxes(range=[-2,122],visible=False,constrain='domain',row=row,col=col)
    fig.update_yaxes(range=[-2,82],visible=False,scaleanchor=f'x{(col-1) or ""}' if row==1 and col==1 else None,
                     row=row,col=col)


def _layout(fig,h=440):
    fig.update_layout(height=h,template='plotly_white',paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Inter, Arial',color=NAVY,size=12),
        margin=dict(l=20,r=20,t=60,b=24),legend=dict(orientation='h',y=-.12,x=0),
        hoverlabel=dict(bgcolor='white',font_size=12))
    return fig


def _xy(d):
    return d.dropna(subset=['location_x','location_y']).copy()


def _def_actions(e,team):
    d=_xy(e[(e.team==team)& e.event_type.isin(DEFENSE_TYPES)])
    # StatsBomb locations are relative to the event actor's team.
    d['location_x']=120-d['location_x']
    d['location_y']=80-d['location_y']
    return d


def _path_actions(e,team):
    return e[(e.team!=team)&e.event_type.isin(['Pass','Carry'])].dropna(
        subset=['location_x','location_y','end_location_x','end_location_y']).copy()


def _zone_flows(e,team):
    pass_and_carry=_path_actions(e,team)
    if pass_and_carry.empty:return pd.DataFrame()
    # Real flows between discretized 20x20 coordinate bins; never interpolate player positions.
    a=pass_and_carry.copy()
    for ax,xx,name in [('location_x','location_y','from'),('end_location_x','end_location_y','to')]:
        a[name+'_x']=np.clip(np.floor(a[ax]/20),0,5).astype(int)
        a[name+'_y']=np.clip(np.floor(a[xx]/20),0,3).astype(int)
    c=a.groupby(['from_x','from_y','to_x','to_y']).size().reset_index(name='n')
    c=c[~((c.from_x==c.to_x)&(c.from_y==c.to_y))]
    return c.nlargest(3,'n')


def atlas(summary,events,team='América'):
    fig=make_subplots(rows=1,cols=3,horizontal_spacing=.048,
        subplot_titles=[s.replace('Defensa ante ','') for s in STATES])
    for j,scenario in enumerate(STATES,1):
        _pitch(fig,col=j)
        subset=summary[summary.scenario.eq(scenario)]
        if subset.empty:
            fig.add_annotation(x=60,y=40,text='Sin datos',showarrow=False,
                               font=dict(color=MUTED),row=1,col=j)
            continue
        ids=pd.MultiIndex.from_frame(subset[['match_id','possession']])
        ev=events[events.set_index(['match_id','possession']).index.isin(ids)]
        ds=_def_actions(ev,team)
        if len(ds):
            fig.add_trace(go.Histogram2d(x=ds.location_x,y=ds.location_y,nbinsx=12,nbinsy=8,
                xbins=dict(start=0,end=120,size=10),ybins=dict(start=0,end=80,size=10),
                coloraxis='coloraxis',opacity=.55,hovertemplate='Intervenciones en zona: %{z}<extra></extra>'),1,j)
        starts=subset.dropna(subset=['first_contact_x','first_contact_y']).copy()
        starts['first_contact_x']=120-starts['first_contact_x']
        starts['first_contact_y']=80-starts['first_contact_y']
        if len(starts):
            fig.add_trace(go.Scatter(x=starts.first_contact_x,y=starts.first_contact_y,mode='markers',
                marker=dict(size=5.5,color=AMBER,opacity=.6),name='Primer contacto',
                showlegend=(j==1),hovertemplate='Primer contacto observado<br>x=%{x:.1f} y=%{y:.1f}<extra></extra>'),1,j)
        flows=_zone_flows(ev,team)
        if len(flows):
            for r in flows.itertuples(index=False):
                x0,y0=r.from_x*20+10,r.from_y*20+10
                x1,y1=r.to_x*20+10,r.to_y*20+10
                fig.add_annotation(x=x1,y=y1,ax=x0,ay=y0,axref='x'+(str(j) if j>1 else ''),
                    ayref='y'+(str(j) if j>1 else ''),xref='x'+(str(j) if j>1 else ''),
                    yref='y'+(str(j) if j>1 else ''),showarrow=True,arrowhead=2,
                    arrowwidth=min(3,1+.25*r.n),arrowsize=.9,arrowcolor=BLUE,opacity=.85)
        k=kpis(subset)
        fig.add_annotation(x=60,y=-7,text=(f'{k["posesiones"]} posesiones · {k["partidos"]} partidos · '
            f'{k["pct_remate"]:.1f}% con remate'),showarrow=False,font=dict(size=10,color=MUTED),row=1,col=j)
    fig=_layout(fig,360)
    fig.update_layout(margin=dict(l=8,r=8,t=55,b=55),showlegend=True,
        coloraxis=dict(cmin=0,colorscale=[[0,'rgba(255,255,255,0)'],[1,'rgba(198,153,76,.74)']],
                       showscale=False))
    return fig


def sequence(events,team,match_id,poss):
    d=event_detail(events,match_id,poss)
    fig=make_subplots(rows=1,cols=1); _pitch(fig)
    if d.empty:return _layout(fig)
    opp=_path_actions(d,team)
    legend_done=False
    for r in opp.itertuples(index=False):
        fig.add_trace(go.Scatter(x=[r.location_x,r.end_location_x],
            y=[r.location_y,r.end_location_y],mode='lines+markers',
            line=dict(color=BLUE,width=2,dash='solid' if r.event_type=='Pass' else 'dot'),
            marker=dict(size=[5,7],color=BLUE),showlegend=not legend_done,
            name='Pase/conducción rival',hovertemplate=f'{r.event_type} rival · minuto {r.minute:.0f}<extra></extra>'))
        fig.add_annotation(x=r.end_location_x,y=r.end_location_y,ax=r.location_x,ay=r.location_y,
                           xref='x',yref='y',axref='x',ayref='y',showarrow=True,arrowhead=2,
                           arrowcolor=BLUE,arrowwidth=1.4,text='')
        legend_done=True
    ds=_def_actions(d,team)
    if len(ds):
        fig.add_trace(go.Scatter(x=ds.location_x,y=ds.location_y,mode='markers+text',
            text=[str(i+1) for i in range(len(ds))],textposition='top center',
            textfont=dict(color=NAVY,size=12),marker=dict(size=12,color=AMBER,line=dict(color='white',width=2)),
            customdata=ds[['player','event_type','minute']].fillna('').astype(str).to_numpy(),
            hovertemplate='Jugador: %{customdata[0]}<br>Acción: %{customdata[1]}<br>Minuto: %{customdata[2]}<extra></extra>',
            name=f'Defensa {team}'))
    shots=d[(d.team!=team)&(d.event_type=='Shot')].dropna(subset=['location_x','location_y'])
    if len(shots):
        fig.add_trace(go.Scatter(x=shots.location_x,y=shots.location_y,mode='markers',
            marker=dict(symbol='x',size=14,color=RED,line=dict(width=2,color=RED)),
            name='Remate rival',hovertemplate='Remate rival<extra></extra>'))
    fig=_layout(fig,445)
    fig.update_layout(title=dict(text=f'Secuencia observada · Partido {match_id} · Posesión {poss}',font=dict(size=15)),
        xaxis=dict(range=[-2,122],visible=False),yaxis=dict(range=[-2,82],visible=False,scaleanchor='x'))
    return fig


def defensive_network(events,team,top=7):
    d=_def_actions(events,team)
    fig=make_subplots(rows=1,cols=1);_pitch(fig)
    d=d[d.player.notna() & d.player.ne('')]
    if d.empty:return _layout(fig)
    nodes=d.groupby('player').agg(n=('event_type','size'),x=('location_x','median'),
        y=('location_y','median')).sort_values('n',ascending=False).head(top)
    d=d[d.player.isin(nodes.index)]
    keys=d.groupby(['match_id','possession'])['player'].apply(lambda x:set(x.dropna())).tolist()
    from collections import Counter
    co=Counter()
    for players in keys:
        for a,b in combinations(sorted(players),2):co[(a,b)]+=1
    for (a,b),n in co.most_common(15):
        if n<2:continue
        na,nb=nodes.loc[a],nodes.loc[b]
        fig.add_trace(go.Scatter(x=[na.x,nb.x],y=[na.y,nb.y],mode='lines',
            line=dict(color='rgba(80,127,175,.55)',width=min(7,1+n**.5)),showlegend=False,
            hoverinfo='text',text=[f'{a} ↔ {b}: {n} posesiones compartidas']*2))
    sizes=14+26*np.sqrt(nodes.n/nodes.n.max())
    fig.add_trace(go.Scatter(x=nodes.x,y=nodes.y,mode='markers+text',text=nodes.index,
        textposition='top center',textfont=dict(size=10,color=NAVY),
        customdata=nodes.n.to_numpy(),marker=dict(size=sizes,color=AMBER,line=dict(color='white',width=2)),
        hovertemplate='%{text}<br>%{customdata} intervenciones<extra></extra>',name='Jugadores'))
    return _layout(fig,440)


def timeline(summary,metric='pct_remate'):
    t=time_summary(summary)
    fig=go.Figure()
    if t.empty:return _layout(fig,300)
    desc={'pct_remate':'Posesiones con remate (%)','presiones_100':'Presiones por 100 posesiones',
          'xg_pos':'xG rival por posesión cubierta'}
    fig.add_trace(go.Scatter(x=t.minute_band,y=t[metric],mode='lines+markers',
        line=dict(color=AMBER,width=3),marker=dict(size=10,color=AMBER,line=dict(color='white',width=2)),
        connectgaps=False,customdata=t[['posesiones','partidos','xg_coverage_pct']],
        hovertemplate='%{x}<br>'+desc[metric]+': %{y:.2f}<br>%{customdata[0]} posesiones · %{customdata[1]} partidos<br>Cobertura xG: %{customdata[2]:.1f}%<extra></extra>'))
    fig=_layout(fig,305)
    fig.update_layout(yaxis=dict(title=desc[metric],rangemode='tozero',gridcolor='#EBEFF1'),
                      xaxis=dict(title='Tramo del partido (según inicio de posesión)'),showlegend=False)
    return fig


def freeze_frame(record,actor_is_america:bool,team_name:str="Equipo"):
    """One actual spatial snapshot; teammate is relative to event actor, not to focal team."""
    fig=make_subplots(rows=1,cols=1);_pitch(fig)
    frames=record.get('freeze_frame',[])
    ours=[];opp=[]
    for p in frames:
        xy=p.get('location',[])
        if len(xy)<2:continue
        is_ours=(bool(p.get('teammate'))==bool(actor_is_america))
        # Position points are intentionally anonymous: 360 usually lacks identity IDs.
        (ours if is_ours else opp).append((120-xy[0],80-xy[1]) if actor_is_america else (xy[0],xy[1]))
    for label,coords,color in [(team_name,ours,AMBER),('Rival',opp,BLUE)]:
        if coords:
            fig.add_trace(go.Scatter(x=[p[0] for p in coords],y=[p[1] for p in coords],
                mode='markers',marker=dict(size=12,color=color,line=dict(width=2,color='white')),
                name=label,hovertemplate=label+' · jugador visible<extra></extra>'))
    v=record.get('visible_area',[])
    if len(v)>=6 and len(v)%2==0:
        xx=v[0::2];yy=v[1::2]
        if actor_is_america: xx=[120-x for x in xx]; yy=[80-y for y in yy]
        fig.add_trace(go.Scatter(x=xx+[xx[0]],y=yy+[yy[0]],mode='lines',
           fill='toself',fillcolor='rgba(80,127,175,.07)',line=dict(color=BLUE,dash='dot',width=1),
           name='Cobertura visible'))
    fig=_layout(fig,440)
    fig.update_layout(title=dict(text=f'Freeze frame real · {len(ours)} jugadores {team_name} · {len(opp)} rivales visibles',font=dict(size=15)))
    return fig


def scenario_pitch(summary, events, team, scenario):
    """Single generous pitch. All observations are filtered to the selected defensive scenario."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fig=make_subplots(rows=1,cols=1)
    _pitch(fig)
    if summary.empty:
        fig.add_annotation(x=60,y=40,text='Sin eventos',showarrow=False)
        return _layout(fig,445)
    keys=pd.MultiIndex.from_frame(summary[['match_id','possession']])
    e=events[events.set_index(['match_id','possession']).index.isin(keys)]
    a=_def_actions(e,team)
    if len(a):
        fig.add_trace(go.Histogram2d(x=a.location_x,y=a.location_y,
            xbins=dict(start=0,end=120,size=10),ybins=dict(start=0,end=80,size=10),
            colorscale=[[0,'rgba(255,255,255,0)'],[1,'rgba(198,153,76,.80)']],
            showscale=False,opacity=.58,name='Densidad de acciones defensivas',
            hovertemplate='Intervenciones en zona: %{z}<extra></extra>'))
    starts=summary.dropna(subset=['first_contact_x','first_contact_y'])
    if len(starts):
        fig.add_trace(go.Scatter(x=120-starts.first_contact_x,y=80-starts.first_contact_y,
            mode='markers',marker=dict(color=AMBER,size=7,opacity=.7),
            name='Primer contacto defensivo',hovertemplate='Primer contacto registrado<extra></extra>'))
    for r in _zone_flows(e,team).itertuples(index=False):
        fig.add_annotation(x=r.to_x*20+10,y=r.to_y*20+10,ax=r.from_x*20+10,ay=r.from_y*20+10,
            xref='x',yref='y',axref='x',ayref='y',text='',showarrow=True,arrowhead=2,
            arrowwidth=min(3,1+.25*r.n),arrowcolor=BLUE,opacity=.9)
    fig=_layout(fig,465)
    fig.update_layout(title=dict(text=scenario,font=dict(size=16)),
        margin=dict(l=24,r=24,t=50,b=40),legend=dict(orientation='h',y=-.08))
    return fig
