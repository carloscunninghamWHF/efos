"""Narrative set-piece dual-map in StatsBomb attacking coordinates (120x80)."""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch

INK="#17243A"; ACCENT="#C69C45"; BLUE="#366DC2"; MUTED="#718096"; PITCH="#FBFCFF"; GRID="#CDD6E5"


def _half_pitch(ax):
    # Transform (x,y) -> (y,x): opponent goal is at top; attackers move up the pitch.
    ax.set_facecolor(PITCH)
    ax.add_patch(Rectangle((0,80),80,40,fill=False,lw=1.4,edgecolor=GRID,zorder=1))
    ax.add_patch(Rectangle((18,102),44,18,fill=False,lw=1.35,edgecolor=GRID,zorder=1))
    ax.add_patch(Rectangle((30,114),20,6,fill=False,lw=1.1,edgecolor=GRID,zorder=1))
    ax.add_patch(Rectangle((36.5,120),7,1.9,fill=False,lw=2.1,edgecolor=INK,zorder=3))
    ax.add_patch(Circle((40,108),.5,facecolor=GRID,zorder=3))
    ax.plot([0,80],[100,100],ls=":",lw=.7,color=GRID,alpha=.6)
    ax.set_xlim(-3,83);ax.set_ylim(79,124)
    ax.set_aspect("equal",adjustable="box")
    ax.set_xticks([]);ax.set_yticks([])
    for s in ax.spines.values():s.set_visible(False)


def dual_destination_map(data:pd.DataFrame, kind:str, side:str, mode:str="zonas"):
    """Two attacking-half maps separated by attacking team's left/right sideline.

    Shows observed target coordinates; does NOT claim actual first touch or aerial arrival.
    For a direct free kick (no pass endpoint) the shot start is the meaningful position,
    so it is not drawn as a fictitious destination.
    """
    d=data[(data["kind"]==kind)&(data["side"]==side)] if len(data) else data
    fig,axes=plt.subplots(1,2,figsize=(11.3,4.35),facecolor="white")
    for ax,flank in zip(axes,("Izquierda","Derecha")):
        _half_pitch(ax)
        s=d[d["flank"]==flank].copy()
        valid=s[pd.to_numeric(s["end_x"],errors="coerce").between(78,120) &
                pd.to_numeric(s["end_y"],errors="coerce").between(0,80)]
        n=len(valid)
        ax.set_title(f"DESDE {flank.upper()}  ·  {n} destinos",fontweight="bold",fontsize=10,color=INK,pad=12)
        if not n:
            ax.text(40,95,"Sin destinos registrados",ha="center",va="center",color=MUTED,fontsize=10)
            continue
        if mode=="trayectorias":
            for _,r in valid.iterrows():
                if pd.notna(r["start_y"]) and pd.notna(r["start_x"]):
                    ax.plot([float(r["start_y"]),float(r["end_y"])],
                            [float(r["start_x"]),float(r["end_x"])],
                            color=BLUE,alpha=max(.025,min(.27,12/max(n,1))),lw=1.15,zorder=3)
            ax.scatter(valid["end_y"].astype(float),valid["end_x"].astype(float),s=18,
                       color=ACCENT,alpha=.72,zorder=5,edgecolors="white",linewidth=.3)
        else:
            valid=valid.copy()
            valid["_zone"]=valid["target_zone"].astype(str)
            counts=valid["_zone"].value_counts()
            for z,count in counts.head(5).items():
                group=valid[valid["_zone"]==z]
                # The centroid of observed *recorded target* coordinates (not a representative invented target).
                dest_y=float(pd.to_numeric(group["end_y"],errors="coerce").mean())
                dest_x=float(pd.to_numeric(group["end_x"],errors="coerce").mean())
                if not (np.isfinite(dest_x) and np.isfinite(dest_y)):continue
                src_y=float(pd.to_numeric(group["start_y"],errors="coerce").mean())
                src_x=float(pd.to_numeric(group["start_x"],errors="coerce").mean())
                color=ACCENT if z==counts.index[0] else BLUE
                if np.isfinite(src_x) and np.isfinite(src_y):
                    ax.add_patch(FancyArrowPatch((src_y,src_x),(dest_y,dest_x),arrowstyle="-|>",
                           mutation_scale=12,connectionstyle="arc3,rad=.1",lw=1.2+2.5*count/n,
                           color=color,alpha=.72,zorder=4))
                ax.scatter([dest_y],[dest_x],s=130+1100*count/n,color=color,
                           alpha=.22,zorder=5,edgecolors=color,linewidth=1.5)
                ax.scatter([dest_y],[dest_x],s=13,color=color,zorder=6)
                ax.text(dest_y,dest_x+3.1,f"{count/n:.0%}",fontsize=9,fontweight="bold",
                        color=INK,ha="center",va="center",zorder=10,
                        bbox=dict(facecolor="white",edgecolor="none",alpha=.88,pad=1))
            ax.scatter(valid["end_y"].astype(float),valid["end_x"].astype(float),
                       s=7,color=BLUE,alpha=.15,zorder=3)
        # Starting point visible in each map (not an arbitrary kick location).
        if s["start_x"].notna().any() and s["start_y"].notna().any():
            x=float(s["start_y"].median());y=float(s["start_x"].median())
            if np.isfinite(x) and np.isfinite(y) and 0<=x<=80 and 78<=y<=120:
                ax.scatter([x],[y],s=55,c=INK,marker="x",linewidth=1.7,zorder=7)
    fig.suptitle(f"{kind} · {side.lower()}  |  Destinos registrados, no contactos confirmados",
                 x=.5,y=1.025,fontweight="bold",fontsize=12,color=INK)
    fig.text(.5,.025,"El porcentaje de cada zona se calcula sobre ejecuciones con coordenadas válidas por banda.",
             ha="center",fontsize=8.4,color=MUTED)
    fig.subplots_adjust(wspace=.08,left=.02,right=.98,top=.88,bottom=.10)
    return fig


def shot_origin_map(data:pd.DataFrame,kind:str,side:str):
    d=data[(data["kind"]==kind)&(data["side"]==side)&data["shot_generated"]]
    fig,ax=plt.subplots(figsize=(7.8,4.7),facecolor="white")
    _half_pitch(ax)
    valid=d[pd.to_numeric(d["shot_x"],errors="coerce").between(80,120)&
            pd.to_numeric(d["shot_y"],errors="coerce").between(0,80)]
    if len(valid):
        ax.scatter(valid["shot_y"].astype(float),valid["shot_x"].astype(float),s=110,
                   c=ACCENT,edgecolor="white",alpha=.8,label="Primer remate registrado",zorder=6)
        ax.legend(loc="lower center",frameon=False,fontsize=9)
    else:
        ax.text(40,94,"No hay remates con posición registrada",fontsize=10,ha="center",color=MUTED)
    ax.set_title(f"Dónde se produce el primer remate  ·  {len(valid)} con posición",
                 fontsize=12,color=INK,fontweight="bold",pad=12)
    fig.tight_layout()
    return fig
