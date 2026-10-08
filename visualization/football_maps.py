"""Mapas de cancha para la interfaz v2.

Usa mplsoccer cuando está instalado (está declarado en requirements.txt) y cae
sobre un campo matplotlib simple si no está disponible. Todas las funciones
trabajan con coordenadas StatsBomb 120x80 y no alteran los cálculos EFOS.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

NAVY = "#0F172A"
BLUE = "#2563EB"
GOLD = "#C89B3C"
RED = "#B91C1C"
GREEN = "#166534"
GREY = "#94A3B8"
BG = "#F8FAFC"


def _pitch(ax=None):
    try:
        from mplsoccer import Pitch
        pitch = Pitch(pitch_type="statsbomb", pitch_color=BG, line_color="#CBD5E1", linewidth=1.1)
        fig, ax = pitch.draw(figsize=(10.5, 6.8), constrained_layout=True) if ax is None else (ax.figure, ax)
        return fig, ax, pitch
    except Exception:
        if ax is None:
            fig, ax = plt.subplots(figsize=(10.5, 6.8), constrained_layout=True)
        else:
            fig = ax.figure
        ax.set_facecolor(BG)
        ax.plot([0,120,120,0,0],[0,0,80,80,0], color="#CBD5E1", lw=1.1)
        ax.plot([60,60],[0,80], color="#CBD5E1", lw=1.0)
        ax.add_patch(plt.Circle((60,40),10, fill=False, ec="#CBD5E1", lw=1.0))
        for x0,x1 in [(0,18),(102,120)]:
            ax.plot([x0,x1,x1,x0],[18,18,62,62], color="#CBD5E1", lw=1.0)
        ax.set_xlim(0,120); ax.set_ylim(80,0); ax.set_aspect("equal"); ax.axis("off")
        return fig, ax, None


def _xy(d: pd.DataFrame, x="location_x", y="location_y") -> pd.DataFrame:
    z=d.copy()
    z[x]=pd.to_numeric(z.get(x),errors="coerce")
    z[y]=pd.to_numeric(z.get(y),errors="coerce")
    return z.dropna(subset=[x,y])


def action_heatmap(events: pd.DataFrame, team: str, event_types: list[str], title: str):
    d=_xy(events[events["team"].eq(team) & events["event_type"].isin(event_types)])
    fig,ax,pitch=_pitch()
    if len(d):
        if pitch is not None:
            bs=pitch.bin_statistic(d.location_x,d.location_y,statistic="count",bins=(6,4),normalize=True)
            pitch.heatmap(bs,ax=ax,cmap="Blues",edgecolors="white",alpha=.88)
            pitch.label_heatmap(bs,ax=ax,str_format="{:.0%}",color=NAVY,fontsize=11)
        else:
            ax.hist2d(d.location_x,d.location_y,bins=(6,4),range=[[0,120],[0,80]],cmap="Blues",alpha=.8)
    ax.set_title(title,loc="left",fontsize=15,fontweight="bold",color=NAVY,pad=12)
    ax.text(0,1.02,f"{len(d):,} acciones · dirección de ataque →",transform=ax.transAxes,fontsize=9,color="#64748B")
    return fig


def effective_pressures(events: pd.DataFrame, team: str, seconds: float=5.0) -> pd.DataFrame:
    """Pressure del equipo seguida de recuperación/intercepción en <= seconds.

    Es una definición observable y conservadora de «presión efectiva»; no
    pretende atribuir causalidad a la presión.
    """
    e=events.copy()
    for c in ["timestamp_seconds","location_x","location_y"]:
        e[c]=pd.to_numeric(e.get(c),errors="coerce")
    p=e[e["team"].eq(team)&e["event_type"].eq("Pressure")].dropna(subset=["timestamp_seconds"])
    rec=e[e["team"].eq(team)&e["event_type"].isin(["Ball Recovery","Interception"])].dropna(subset=["timestamp_seconds"])
    keep=[]
    for idx,r in p.iterrows():
        q=rec[(rec["match_id"].eq(r["match_id"]))&(rec["period"].eq(r["period"]))&
              rec["timestamp_seconds"].between(r["timestamp_seconds"],r["timestamp_seconds"]+seconds)]
        if len(q): keep.append(idx)
    return p.loc[keep].copy() if keep else p.iloc[0:0].copy()


def recoveries(events: pd.DataFrame, team: str) -> pd.DataFrame:
    return _xy(events[events["team"].eq(team)&events["event_type"].isin(["Ball Recovery","Interception"])])


def opponent_positive_obv(events: pd.DataFrame, team: str) -> pd.DataFrame:
    d=events[~events["team"].eq(team)].copy()
    d["obv_total_net"]=pd.to_numeric(d.get("obv_total_net"),errors="coerce")
    return _xy(d[d["obv_total_net"].gt(0)])


def defensive_heatmap(events: pd.DataFrame, team: str, mode: str):
    if mode=="pressure":
        d=_xy(effective_pressures(events,team)); title="Zonas de presión seguida de recuperación ≤5 s"; cmap="Blues"; weights=None
    elif mode=="recovery":
        d=recoveries(events,team); title="Zonas de recuperación"; cmap="Greens"; weights=None
    else:
        d=opponent_positive_obv(events,team); title="Dónde genera valor ofensivo el rival (OBV positivo)"; cmap="Reds"; weights=d.get("obv_total_net")
    fig,ax,pitch=_pitch()
    if len(d):
        if pitch is not None:
            stat="sum" if weights is not None else "count"
            bs=pitch.bin_statistic(d.location_x,d.location_y,values=weights,statistic=stat,bins=(6,4),normalize=weights is None)
            pitch.heatmap(bs,ax=ax,cmap=cmap,edgecolors="white",alpha=.9)
            fmt="{:.0%}" if weights is None else "{:.2f}"
            pitch.label_heatmap(bs,ax=ax,str_format=fmt,color=NAVY,fontsize=10)
        else:
            ax.hist2d(d.location_x,d.location_y,bins=(6,4),range=[[0,120],[0,80]],weights=weights,cmap=cmap,alpha=.8)
    ax.set_title(title,loc="left",fontsize=15,fontweight="bold",color=NAVY,pad=12)
    subtitle=("Proxy observable: presión + recuperación posterior; no atribuye causalidad." if mode=="pressure" else
              "Recuperaciones e intercepciones del equipo." if mode=="recovery" else
              "Suma de OBV positivo de acciones rivales por zona; mayor rojo = mayor valor creado.")
    ax.text(0,1.02,subtitle,transform=ax.transAxes,fontsize=9,color="#64748B")
    return fig


def counterpress_map(events: pd.DataFrame, team: str):
    e=events.copy(); cp=e.get("counterpress",False)
    if not isinstance(cp,pd.Series): cp=pd.Series(False,index=e.index)
    flag=cp.fillna(False).astype(str).str.lower().isin(["true","1"])
    d=_xy(e[e["team"].eq(team)&flag])
    fig,ax,pitch=_pitch()
    if len(d):
        if pitch is not None:
            pitch.scatter(d.location_x,d.location_y,ax=ax,s=30,color=BLUE,alpha=.45,edgecolors="white",linewidth=.3)
        else: ax.scatter(d.location_x,d.location_y,s=24,c=BLUE,alpha=.45)
    ax.set_title("Dónde activa la presión inmediata tras pérdida",loc="left",fontsize=15,fontweight="bold",color=NAVY,pad=12)
    ax.text(0,1.02,f"{len(d):,} acciones etiquetadas counterpress por StatsBomb",transform=ax.transAxes,fontsize=9,color="#64748B")
    return fig


def recoveries_leading_to_shot(events: pd.DataFrame, team: str, seconds: float=15.0) -> pd.DataFrame:
    e=events.copy()
    e["timestamp_seconds"]=pd.to_numeric(e.get("timestamp_seconds"),errors="coerce")
    rec=e[e["team"].eq(team)&e["event_type"].isin(["Ball Recovery","Interception"])].dropna(subset=["timestamp_seconds"])
    sh=e[e["team"].eq(team)&e["event_type"].eq("Shot")].dropna(subset=["timestamp_seconds"])
    keep=[]
    for idx,r in rec.iterrows():
        q=sh[(sh["match_id"].eq(r["match_id"]))&(sh["period"].eq(r["period"]))&
             (sh.get("possession",pd.Series(index=sh.index,dtype=float)).eq(r.get("possession")))&
             sh["timestamp_seconds"].between(r["timestamp_seconds"],r["timestamp_seconds"]+seconds)]
        if len(q): keep.append(idx)
    return _xy(rec.loc[keep]) if keep else _xy(rec.iloc[0:0])


def offensive_transition_map(events: pd.DataFrame, team: str):
    d=recoveries_leading_to_shot(events,team)
    fig,ax,pitch=_pitch()
    if len(d):
        if pitch is not None: pitch.scatter(d.location_x,d.location_y,ax=ax,s=42,color=GOLD,alpha=.65,edgecolors="white",linewidth=.5)
        else: ax.scatter(d.location_x,d.location_y,s=34,c=GOLD,alpha=.65)
    ax.set_title("Recuperaciones que terminan en tiro en ≤15 s",loc="left",fontsize=15,fontweight="bold",color=NAVY,pad=12)
    ax.text(0,1.02,f"{len(d):,} recuperaciones observadas que desembocan en tiro",transform=ax.transAxes,fontsize=9,color="#64748B")
    return fig


def set_piece_summary(events: pd.DataFrame, team: str) -> dict:
    e=events.copy()
    patt=e.get("play_pattern_name",pd.Series(index=e.index,dtype=object))
    passes=e[e["event_type"].eq("Pass") & patt.isin(["From Corner","From Free Kick"])].copy()
    team_p=passes[passes["team"].eq(team)]
    opp_p=passes[~passes["team"].eq(team)]
    def _tech(d):
        s=d.get("technique_name",pd.Series(index=d.index,dtype=object)).fillna("Sin etiqueta")
        return {str(k):int(v) for k,v in s.value_counts().items()}
    def _shots(tm):
        s=e[e["team"].eq(tm)&e["event_type"].eq("Shot")&patt.isin(["From Corner","From Free Kick","From Throw In"])].copy()
        s["statsbomb_xg"]=pd.to_numeric(s.get("statsbomb_xg"),errors="coerce").fillna(0)
        return {"shots":int(len(s)),"xg":float(s["statsbomb_xg"].sum())}
    opp_teams=[x for x in e["team"].dropna().unique() if x!=team]
    opp_shots=e[(~e["team"].eq(team))&e["event_type"].eq("Shot")&patt.isin(["From Corner","From Free Kick","From Throw In"])].copy()
    opp_shots["statsbomb_xg"]=pd.to_numeric(opp_shots.get("statsbomb_xg"),errors="coerce").fillna(0)
    return {"for_techniques":_tech(team_p),"against_techniques":_tech(opp_p),"for":_shots(team),
            "against":{"shots":int(len(opp_shots)),"xg":float(opp_shots["statsbomb_xg"].sum())}}


def set_piece_trajectories(events: pd.DataFrame, team: str, against: bool=False):
    e=events.copy(); patt=e.get("play_pattern_name",pd.Series(index=e.index,dtype=object))
    d=e[e["event_type"].eq("Pass")&patt.isin(["From Corner","From Free Kick"])].copy()
    d=d[~d["team"].eq(team)] if against else d[d["team"].eq(team)]
    for c in ["location_x","location_y","end_location_x","end_location_y"]: d[c]=pd.to_numeric(d.get(c),errors="coerce")
    d=d.dropna(subset=["location_x","location_y","end_location_x","end_location_y"])
    fig,ax,pitch=_pitch()
    if len(d):
        colors=d.get("technique_name",pd.Series(index=d.index,dtype=object)).map({"Inswinging":GOLD,"Outswinging":BLUE,"Straight":GREY}).fillna("#64748B")
        if pitch is not None:
            pitch.lines(d.location_x,d.location_y,d.end_location_x,d.end_location_y,ax=ax,color=colors.tolist(),alpha=.28,lw=1.2,comet=False)
            pitch.scatter(d.end_location_x,d.end_location_y,ax=ax,s=15,color=colors.tolist(),alpha=.45)
        else:
            for (_,r),c in zip(d.iterrows(),colors): ax.plot([r.location_x,r.end_location_x],[r.location_y,r.end_location_y],color=c,alpha=.28,lw=1.2)
    title="Balón parado en contra: trayectorias de entrega" if against else "Balón parado a favor: trayectorias de entrega"
    ax.set_title(title,loc="left",fontsize=15,fontweight="bold",color=NAVY,pad=12)
    ax.text(0,1.02,"Dorado = comba hacia dentro · Azul = comba hacia fuera · Gris = otra/sin etiqueta",transform=ax.transAxes,fontsize=9,color="#64748B")
    return fig


def set_piece_shot_map(events: pd.DataFrame, team: str, against: bool=False):
    e=events.copy(); patt=e.get("play_pattern_name",pd.Series(index=e.index,dtype=object))
    d=e[e["event_type"].eq("Shot")&patt.isin(["From Corner","From Free Kick","From Throw In"])].copy()
    d=d[~d["team"].eq(team)] if against else d[d["team"].eq(team)]
    d=_xy(d); d["statsbomb_xg"]=pd.to_numeric(d.get("statsbomb_xg"),errors="coerce").fillna(0)
    fig,ax,pitch=_pitch()
    if len(d):
        size=40+600*d["statsbomb_xg"].clip(0,.6)
        if pitch is not None: pitch.scatter(d.location_x,d.location_y,ax=ax,s=size,color=RED if against else GREEN,alpha=.58,edgecolors="white",linewidth=.5)
        else: ax.scatter(d.location_x,d.location_y,s=size,c=RED if against else GREEN,alpha=.58)
    ax.set_title("Zonas de remate a balón parado " + ("del rival" if against else "del equipo"),loc="left",fontsize=15,fontweight="bold",color=NAVY,pad=12)
    ax.text(0,1.02,"Tamaño del punto = xG del remate. Event data no permite clasificar zona vs. marca personal sin 360/tracking.",transform=ax.transAxes,fontsize=9,color="#64748B")
    return fig
