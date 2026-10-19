"""EFOS editorial tactical maps: rival-possession situational comparison (not tracking)."""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Arc
from intelligence.smart_defense_tactics import DEFENSIVE_ACTIONS

INK="#172438"; GOLD="#C89B3C"; BG="#F7F8FA"; GRID="#CBD5E1"; BLUE="#45728F"; RED="#CB7358"


def _pitch(ax):
    ax.set_facecolor(BG)
    ax.add_patch(Rectangle((0,0),120,80,fill=False,ec=GRID,lw=1.3,zorder=3))
    ax.plot([60,60],[0,80],color=GRID,lw=.9,zorder=3)
    ax.add_patch(Circle((60,40),10,fill=False,ec=GRID,lw=.9,zorder=3))
    for x in (0,102):ax.add_patch(Rectangle((x,18),18,44,fill=False,ec=GRID,lw=.9,zorder=3))
    for x in (0,114):ax.add_patch(Rectangle((x,30),6,20,fill=False,ec=GRID,lw=.9,zorder=3))
    for x in (40,80):ax.plot([x,x],[0,80],lw=.6,alpha=.5,ls=':',color=GRID,zorder=3)
    ax.set_xlim(-2,122);ax.set_ylim(82,-2);ax.set_aspect('equal');ax.axis('off')


def scenario_events(events:pd.DataFrame,possessions:pd.DataFrame,team:str) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Get actual defensive events and rival shots in the selected opponent possessions."""
    if possessions is None or possessions.empty:
        return pd.DataFrame(),pd.DataFrame()
    keys=['match_id','period','possession']
    e=events.merge(possessions[keys].drop_duplicates(),on=keys,how='inner')
    d=e[e['team'].eq(team) & e['event_type'].isin(DEFENSIVE_ACTIONS)].copy()
    r=e[~e['team'].eq(team) & e['event_type'].eq('Shot')].copy()
    for x in (d,r):
        for c in ('location_x','location_y','statsbomb_xg'):
            x[c]=pd.to_numeric(x[c],errors='coerce') if c in x else np.nan
        x.dropna(subset=['location_x','location_y'],inplace=True)
        x.drop(x.index[~x['location_x'].between(0,120) | ~x['location_y'].between(0,80)],inplace=True)
    return d,r


def scenario_map(events:pd.DataFrame,possessions:pd.DataFrame,team:str):
    """Two views, consistent coordinates: left defense is own-team x, right opponent shot mirrored into same frame."""
    d,r=scenario_events(events,possessions,team)
    fig,axes=plt.subplots(1,2,figsize=(13,4.7),facecolor='white')
    for ax in axes:_pitch(ax)
    pressure=d[d['event_type'].eq('Pressure')]
    other=d[~d['event_type'].eq('Pressure')]
    if len(d):
        # Observed event concentration, not player coverage or compactness.
        hist=np.histogram2d(d['location_x'],d['location_y'],bins=(20,12),range=((0,120),(0,80)))[0]
        axes[0].imshow(hist.T,extent=[0,120,80,0],origin='upper',cmap='YlOrBr',alpha=.59,
                       interpolation='bilinear',vmin=0,zorder=1)
    for group,color,txt in ((pressure,BLUE,'Presión'),(other,GOLD,'Otras acciones')):
        if len(group):
            points=group.iloc[:1000]
            axes[0].scatter(points['location_x'],points['location_y'],s=10,c=color,alpha=.26,
                            lw=0,zorder=2,label=f'{txt} · {len(group)}')
    if len(r):
        sample=r.iloc[:1000]
        x=120-sample['location_x'];y=80-sample['location_y']
        xg=sample['statsbomb_xg'].fillna(0).clip(0,1)
        axes[1].scatter(x,y,c=RED,s=18+250*xg,edgecolor='white',linewidth=.45,alpha=.67,zorder=2)
    axes[0].set_title(f'INTERVENCIONES DE {team.upper()} · {len(d)}',loc='left',color=INK,fontsize=10,fontweight='bold',pad=10)
    axes[1].set_title(f'REMATES RIVALES · {len(r)}',loc='left',color=INK,fontsize=10,fontweight='bold',pad=10)
    for ax in axes:
        ax.annotate('Portería propia',xy=(0,82),xycoords='data',color='#64748B',fontsize=8,ha='left',va='top')
        ax.annotate('Campo rival →',xy=(120,82),xycoords='data',color='#64748B',fontsize=8,ha='right',va='top')
    fig.text(.5,.028,'Izquierda: ubicaciones de eventos defensivos. Derecha: remates rivales reflejados a coordenadas del equipo focal.',
             fontsize=8,color='#64748B',ha='center')
    fig.tight_layout(rect=[0,.06,1,.98],w_pad=2)
    return fig
