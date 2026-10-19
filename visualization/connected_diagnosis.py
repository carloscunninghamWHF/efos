"""EFOS · editorial diagnosis of a *single explicit match sample*.

This module turns observed possessions into linked football questions. It does
not infer intention, formations or causal relations from counts. No Streamlit
required, so the logic can be regression-tested independently of the UI.
"""
from __future__ import annotations

import pandas as pd


def choose_events(events: pd.DataFrame, match_ids: list[str] | None) -> pd.DataFrame:
    if not isinstance(events, pd.DataFrame) or events.empty:
        return pd.DataFrame() if not isinstance(events, pd.DataFrame) else events.iloc[:0].copy()
    if match_ids is None:
        return events
    if 'match_id' not in events:
        return events.iloc[:0].copy()
    return events.loc[events.match_id.astype(str).isin(set(map(str, match_ids)))].copy()


def coherent_observations(result: dict, attack_data=None, defense_data=None) -> dict:
    """Return <=3 evidence-bound statements, each with a denominator.

    attack_data = tuple (event detail, possession table) with StatsBomb columns;
    defense_data = opponent-possession table. Statements are not causal claims.
    """
    attack_data = attack_data if attack_data is not None else result.get('organized_attack_data')
    defense_data = defense_data if defense_data is not None else result.get('defensive_open_play_possessions')
    team = str(result.get('focal_team') or 'El equipo')
    findings = []
    if isinstance(attack_data, (tuple, list)) and len(attack_data) == 2:
        pos = attack_data[1]
        if isinstance(pos, pd.DataFrame) and not pos.empty and 'shots' in pos:
            shots = pd.to_numeric(pos.shots, errors='coerce').fillna(0).gt(0)
            n, k = len(pos), int(shots.sum())
            entry = pd.to_numeric(pos.get('box_entries', pd.Series(0,index=pos.index)), errors='coerce').fillna(0).gt(0)
            e = int(entry.sum())
            both = int((entry & shots).sum())
            conn = (result.get('offensive_story') or {}).get('connection') or {}
            pair=''
            if isinstance(conn, dict):
                src=conn.get('from') or conn.get('from_player')
                dst=conn.get('to') or conn.get('to_player')
                count=conn.get('completed') or conn.get('count') or conn.get('passes')
                if src and dst and count is not None:
                    pair=f' Conexión frecuente registrada: {src} → {dst} ({count} pases).'
            findings.append({
                'id':'ataque' , 'title':'Cómo transforma las posesiones en ocasiones',
                'text':f'{k} de {n} posesiones abiertas terminaron con remate; {e} tuvieron una entrada al área registrada, y {both} reunieron ambas condiciones.' + pair,
                'meaning':'Contrastar las secuencias que entran al área y rematan con aquellas que no consiguen finalizar.',
                'scope':f'{n} posesiones de juego abierto', 'target':'Con balón', 'n':n,
            })
    if isinstance(defense_data, pd.DataFrame) and not defense_data.empty and {'scenario','shot'}.issubset(defense_data.columns):
        d = defense_data.copy()
        d['_shot'] = pd.to_numeric(d.shot, errors='coerce').fillna(0).gt(0)
        group = d.groupby('scenario',dropna=True).agg(n=('shot','size'), remates=('_shot','sum')).reset_index()
        valid = group[group.n.ge(10)]
        if len(valid):
            top = valid.sort_values(['remates','n'],ascending=False).iloc[0]
            n, k = int(top.n), int(top.remates)
            findings.append({
                'id':'defensa','title':'En qué situación acaba rematando el rival',
                'text':f'En «{top.scenario}», el rival remató en {k} de {n} posesiones clasificadas ({100*k/n:.1f}%). Es la categoría con más posesiones que terminan en remate dentro de las situaciones con al menos 10 casos.',
                'meaning':'Examinar la respuesta defensiva específica y sus partidos; la frecuencia de remates no prueba por sí sola una vulnerabilidad estructural.',
                'scope':f'{n} posesiones en «{top.scenario}»', 'target':'Sin balón','n':n,
            })
    # Only own-ball losses in THIS sample; intervention != successful regain.
    tr = result.get('transitions')
    if isinstance(tr,pd.DataFrame) and not tr.empty and {'team_lost','response_within_5s'}.issubset(tr.columns):
        owned = tr.loc[tr.team_lost.eq(team)]
        if len(owned):
            n = len(owned)
            k = int(owned.response_within_5s.fillna(False).astype(bool).sum())
            findings.append({
                'id':'perdida', 'title':'Qué hace inmediatamente al perder el balón',
                'text':f'En {k} de {n} pérdidas de posesión de {team} ({100*k/n:.1f}%) se registró una intervención defensiva dentro de 5 segundos.',
                'meaning':'La intervención no implica recuperación. Comparar la ubicación de la pérdida y el desenlace de la posesión rival, cuando la muestra lo permita.',
                'scope':f'{n} pérdidas de posesión identificadas de {team}', 'target':'Sin balón', 'n':n,
            })
    nmatch = None
    events = result.get('events')
    if isinstance(events,pd.DataFrame) and {'match_id','team'}.issubset(events.columns):
        nmatch = int(events.loc[events.team.eq(team),'match_id'].nunique())
    lead = ('Este informe conecta las secuencias ofensivas con la exposición defensiva observada en la misma selección. '
            'Los datos permiten contrastar qué se produce con balón y en qué escenarios alcanza el rival el remate; '
            'no demuestran que un comportamiento cause el otro.')
    return {'lead':lead,'findings':findings[:3],'matches':nmatch,'team':team,
            'limit':'Métricas calculadas sobre eventos StatsBomb disponibles; no equivalen a tracking, intención o causalidad.'}
