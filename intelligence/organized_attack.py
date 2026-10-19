"""Auditable attack sequences. Descriptive extensions, not a new ESI/OC formula."""
from __future__ import annotations
import numpy as np
import pandas as pd
from visualization.efos_smart_attack_graphs import prepare_events, _find_abc, _after_pressure

ONBALL=['pass','carry','carries','dribble','shot','miscontrol','dispossessed']

def truth(s):
    return s.astype('string').fillna('false').str.lower().isin(['true','1','1.0','yes'])

def prepare_attack(events, team):
    d=prepare_events(events,team)
    d.attrs['restart_known']=bool('play_pattern_name' in events and events.play_pattern_name.notna().any())
    return d

def possession_table(d):
    rows=[]
    for key,g in d.groupby('_poss_key',sort=False):
        a=g[g['_type'].isin(ONBALL)].sort_values('index')
        if a.empty:continue
        p=a[a['_type'].eq('pass')]; shots=a[a['_type'].eq('shot')]
        first=a.iloc[0]; last=a.iloc[-1]
        known_xy=a.location_x.notna() & a.location_y.notna()
        first_xy=a[known_xy].iloc[0] if known_xy.any() else first
        x,y=first_xy.location_x,first_xy.location_y
        lane='Izquierda' if pd.notna(y) and y<80/3 else 'Derecha' if pd.notna(y) and y>160/3 else 'Centro' if pd.notna(y) else 'Sin coordenadas'
        moving=a[a['_pass_done'] | a['_type'].isin(['carry','carries'])]
        box=moving.end_location_x.ge(102)&moving.end_location_y.between(18,62)&~(moving.location_x.ge(102)&moving.location_y.between(18,62))
        third=moving.location_x.lt(80)&moving.end_location_x.ge(80)
        transition=truth(g['is_transition']).any() if 'is_transition' in g else False
        transition=transition or g.play_pattern_name.fillna('').str.lower().eq('from counter').any()
        controlled=truth(g['is_controlled_possession']).any() if 'is_controlled_possession' in g else False
        phase='Transición etiquetada' if transition else 'Posesión controlada etiquetada' if controlled else 'Juego abierto sin clasificación'
        loss=last['_type'] in ['miscontrol','dispossessed'] or (last['_type']=='pass' and not last['_pass_done'] and d.attrs.get('outcome_available',False))
        outcome='Remate' if len(shots) else 'Entrada al área sin remate' if box.any() else 'Pérdida registrada' if loss else 'Sin desenlace concluyente'
        direct=pd.to_numeric(g.get('possession_directness',pd.Series(dtype=float)),errors='coerce').dropna()
        rows.append(dict(key=key,match_id=key[0],period=key[1],possession=key[2],minute=first.minute,
            phase=phase,lane=lane,start_x=x,actions=len(a),passes=len(p),completed=int(p['_pass_done'].sum()),
            pressure_passes=int(p['_under_pressure'].sum()),duration=last['_seconds']-first['_seconds'],
            third_entries=int(third.sum()),box_entries=int(box.sum()),shots=len(shots),outcome=outcome,
            xg=shots.statsbomb_xg.sum(min_count=1),xg_n=int(shots.statsbomb_xg.notna().sum()),
            obv=a.obv_total_net.sum(min_count=1),obv_n=int(a.obv_total_net.notna().sum()),
            directness=direct.median() if len(direct) else np.nan,
            directness_varies=bool(direct.nunique()>1),
            players=' · '.join(a.player.dropna().astype(str).unique()),
            score_state=str(first.get('score_state','Sin marcador'))))
    return pd.DataFrame(rows)

def filter_sample(d, table, matches=None,phase=None,player=None,minutes=None,state=None):
    t=table.copy()
    if matches is not None:t=t[t.match_id.isin(matches)]
    if phase and phase!='Todo el juego abierto':t=t[t.phase.eq(phase)]
    if minutes:t=t[t.minute.between(*minutes)]
    if state and state!='Todos':t=t[t.score_state.eq(state)]
    if player and player!='Colectivo':
        keys=set(d.loc[d.player.eq(player)|d.pass_recipient_name.eq(player),'_poss_key'])
        t=t[t.key.isin(keys)]
    out=d[d['_poss_key'].isin(set(t.key))].copy();out.attrs=d.attrs.copy()
    return out,t

def pressure_comparison(d):
    p=d[d['_type'].eq('pass')]
    if 'under_pressure' not in d.attrs.get('source_columns',[]): return pd.DataFrame()
    rows=[]
    for label,mask in [('Bajo presión',p['_under_pressure']),('Sin presión marcada',~p['_under_pressure'])]:
        g=p[mask]; valid=g.location_x.notna()&g.end_location_x.notna()
        rows.append({'Contexto':label,'Pases':len(g),'Completados':int(g['_pass_done'].sum()),
            '% completados':100*g['_pass_done'].mean() if len(g) and d.attrs.get('outcome_available') else np.nan,
            'Avance X medio':(g.loc[valid,'end_location_x']-g.loc[valid,'location_x']).mean(),
            'OBV observado':g.obv_total_net.sum(min_count=1),'Pases con OBV':g.obv_total_net.count()})
    return pd.DataFrame(rows)

def connections(d):
    p=d[d['_type'].eq('pass') & d.player.notna() & d.pass_recipient_name.notna()]
    if p.empty:return pd.DataFrame()
    return p.groupby(['player','pass_recipient_name']).agg(
        intentos=('index','size'),completados=('_pass_done','sum'),
        obv=('obv_total_net',lambda s:s.sum(min_count=1)),cobertura_obv=('obv_total_net','count'),
        partidos=('match_id','nunique')).reset_index().sort_values('completados',ascending=False)

def findings(d,t):
    if t.empty:return []
    n=len(t); out=[]
    lane=t[t.lane.ne('Sin coordenadas')].lane.value_counts()
    if len(lane):
        name=lane.index[0]; k=int(lane.iloc[0]); denom=int(lane.sum())
        out.append(dict(title=f'El inicio observado se concentra en {name.lower()}',
            text=f'{k} de {denom} secuencias con coordenadas comienzan en ese corredor ({k/denom:.0%}). Se refiere a la primera acción disponible, no a la posición del equipo completo.',
            keys=t.loc[t.lane.eq(name),'key'].tolist(),focus='Revisar si las rutas alternativas ofrecen continuidad frente a distintos rivales.'))
    entered=t[t.box_entries.gt(0)]; shot=int(entered.shots.gt(0).sum())
    if len(entered):out.append(dict(title='De la entrada al área al remate',
        text=f'{len(entered)} de {n} secuencias entran al área mediante pase o conducción; {shot} también contienen un remate. Esta asociación no atribuye el tiro a una entrada concreta.',
        keys=entered.key.tolist(),focus='Comparar las secuencias con remate y sin remate para revisar la continuidad de la llegada.'))
    pairs=_after_pressure(d); known=[(a,b) for a,b in pairs if b is not None]
    forward=sum(pd.notna(b.end_location_x) and pd.notna(b.location_x) and b.end_location_x>b.location_x for a,b in known)
    if pairs:out.append(dict(title='Qué ocurre después del pase bajo presión',
        text=f'{len(pairs)} pases completos bajo presión tienen destinatario; en {len(known)} se observa su siguiente acción inmediata dentro de 8 segundos. {forward} de esas continuaciones avanzan en X. No demuestra atracción deliberada.',
        keys=list(dict.fromkeys(a['_poss_key'] for a,b in pairs)),focus='Revisar apoyos y continuidad en los ejemplos observados, sin atribuir posiciones no registradas.'))
    return out

def mechanisms(d):
    p=d[d['_pass_done']]
    half=p.end_location_x.between(70,95)&(p.end_location_y.between(18,30)|p.end_location_y.between(50,62))
    abc=_find_abc(d)
    return {'Recepción interior':list(dict.fromkeys(p.loc[half,'_poss_key'])),
        'Cambio de orientación':list(dict.fromkeys(p.loc[p['_pass_switch']&(p.end_location_y-p.location_y).abs().ge(20),'_poss_key'])),
        'Combinación A→B→C progresiva':list(dict.fromkeys(k for a,b,k in abc)),
        'Centro completado':list(dict.fromkeys(p.loc[p['_pass_cross'],'_poss_key']))}
