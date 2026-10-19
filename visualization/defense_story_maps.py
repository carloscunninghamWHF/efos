"""Quiet, editorial organized-defense action maps (StatsBomb coordinates 120x80)."""
from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle, Circle
from intelligence.organized_defense_story import action_samples, RECOVERIES

INK="#172438"; GOLD="#C89B3C"; GREY="#94A3B8"; BG="#FBFBFC"

def _pitch(ax):
    ax.set_facecolor(BG)
    ax.add_patch(Rectangle((0,0),120,80,fill=False,ec=GREY,lw=1.15))
    ax.plot([60,60],[0,80],color=GREY,lw=.8)
    ax.add_patch(Circle((60,40),10,fill=False,ec=GREY,lw=.8))
    for x in (0,102):
        ax.add_patch(Rectangle((x,18),18,44,fill=False,ec=GREY,lw=.8))
    for x in (0,114):
        ax.add_patch(Rectangle((x,30),6,20,fill=False,ec=GREY,lw=.8))
    for x in (40,80): ax.axvline(x,color=GREY,ls="--",lw=.6,alpha=.3)
    ax.set_xlim(-1,121);ax.set_ylim(81,-1);ax.set_aspect("equal");ax.axis("off")

def defensive_map(events:pd.DataFrame,team:str,kind:str="Todas las intervenciones"):
    d=action_samples(events,team)
    if kind=="Presiones":d=d[d["event_type"].eq("Pressure")]
    elif kind=="Recuperaciones":d=d[d["event_type"].isin(RECOVERIES)]
    fig,ax=plt.subplots(figsize=(11.5,5.2),facecolor="white")
    _pitch(ax)
    if len(d):
        grid,xedges,yedges=np.histogram2d(d["location_x"],d["location_y"],bins=(24,16),range=[[0,120],[0,80]])
        ax.imshow(grid.T,extent=[0,120,80,0],origin="upper",cmap="YlOrBr",alpha=.68,
                  interpolation="bilinear",aspect="auto",vmin=0)
        ax.set_aspect("equal")
    ax.set_title(f"Dónde registra sus {kind.lower()} · {len(d)} eventos",color=INK,
                 fontsize=12,fontweight="semibold",loc="left",pad=15)
    fig.text(.5,.02,"Campo 120×80: posiciones de eventos; no reconstrucción de la estructura sin balón.",
             ha="center",color="#64748B",fontsize=8)
    fig.tight_layout(rect=[0,.05,1,.95])
    return fig
