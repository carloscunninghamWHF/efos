"""EFOS v0.4.26 — «Modelo de Juego y DT» por formación, rival y partido.

Filters the CTS radar and the score-state reaction by the starting formation the
team used, the opponent and the match. Every number is recomputed with the SAME
engine functions used for the full season (tactical_summary, compute_cts,
compute_adaptation_score, by_segment), restricted to the selected match ids.
Nothing is estimated for matches or score states without data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from behavior.tactical import tactical_summary
from coach_story.coach_profile import _starters, _formation, by_segment, MIN_TEAM_EVENTS
from intelligence.cts import compute_cts, compute_adaptation_score
from visualization.efos_figures import (CTS_LABELS, REACTION_METRICS, SCORE_LABELS, SCORE_ORDER,
                                        ACCENT, NAVY, GREY, LIGHT)

GOLD = '#C89B3C'
# Adaptación se retiró del radar en v0.4.26 (sigue calculándose en el motor CTS).
RADAR_KEYS = ['construction', 'progression', 'attack', 'defense', 'transition']
ALL_SHAPES = 'Todas las formaciones'
ALL_MATCHES = 'Todos los partidos'
ALL_RIVALS = 'Todos los rivales'
RESULT_ABBR = {'Victoria': 'V', 'Empate': 'E', 'Derrota': 'D'}


# ------------------------------------------------------------------ data
def formation_matches(result: dict) -> pd.DataFrame:
    """One row per match: starting formation, opponent and recorded final score."""
    cached = result.get('_formation_matches')
    if isinstance(cached, pd.DataFrame):
        return cached
    ev = result['events']; team = result['focal_team']
    starters = _starters(ev, team)
    own = ev[ev['team'].eq(team)]
    rows = []
    for mid in own['match_id'].astype(str).drop_duplicates():
        g = ev[ev['match_id'].astype(str).eq(mid)]
        rivals = [str(t) for t in g['team'].dropna().unique() if str(t) != team]
        pos = starters.get(mid)
        shape = _formation(list(pos.values()))[0] if pos and len(pos) >= 10 else 'No identificable'
        gf = pd.to_numeric(g.get('focal_goals'), errors='coerce').max() if 'focal_goals' in g else np.nan
        gc = pd.to_numeric(g.get('opponent_goals'), errors='coerce').max() if 'opponent_goals' in g else np.nan
        if pd.notna(gf) and pd.notna(gc):
            res = 'Victoria' if gf > gc else 'Derrota' if gf < gc else 'Empate'
            score = f'{int(gf)}-{int(gc)}'
        else:
            res, score = 'Sin marcador', '—'
        rival = rivals[0] if len(rivals) == 1 else 'Rival no identificado'
        rows.append({'match_id': mid, 'dibujo': shape, 'rival': rival, 'marcador': score, 'resultado': res})
    d = pd.DataFrame(rows)
    if not d.empty:
        d['_order'] = pd.to_numeric(d['match_id'], errors='coerce')
        d = d.sort_values(['_order', 'match_id']).drop(columns='_order').reset_index(drop=True)
        d['n'] = range(1, len(d) + 1)
        d['etiqueta'] = [f"P{r.n:02d} · vs {r.rival} · {r.marcador}"
                         + (f" ({RESULT_ABBR[r.resultado]})" if r.resultado in RESULT_ABBR else '')
                         for r in d.itertuples()]
    result['_formation_matches'] = d
    return d


def shapes_by_frequency(fm: pd.DataFrame) -> list[str]:
    known = fm[fm['dibujo'].ne('No identificable')]
    return known['dibujo'].value_counts().index.tolist()


def cts_for_matches(result: dict, match_ids) -> dict:
    """The radar dimensions recomputed only with the selected matches."""
    ids = {str(m) for m in match_ids}
    team = result['focal_team']
    ev = result['events']
    sub = ev[ev['match_id'].astype(str).isin(ids)]
    summary = tactical_summary(sub, team)
    tr = result.get('transitions')
    rate = None
    if isinstance(tr, pd.DataFrame) and len(tr):
        t = tr[tr['match_id'].astype(str).isin(ids) & tr['team_lost'].eq(team)]
        if len(t):
            rate = float(t['response_within_5s'].mean())
    states = result.get('dtc_states')
    adaptation = None
    if isinstance(states, pd.DataFrame) and len(states):
        adaptation = compute_adaptation_score(states[states['match_id'].astype(str).isin(ids)])
    cts = compute_cts(summary, rate, adaptation_score=adaptation)
    if rate is None:
        cts['transition'] = None
    cts['_events'] = int(summary.get('events', 0))
    return cts


def score_reaction_for_matches(result: dict, match_ids) -> pd.DataFrame:
    ids = {str(m) for m in match_ids}
    ev = result['events']
    return by_segment(ev[ev['match_id'].astype(str).isin(ids)], result['focal_team'],
                      'score_state', list(SCORE_ORDER))


# ---------------------------------------------------------------- figures
def _vals(cts: dict):
    out = []
    for k in RADAR_KEYS:
        v = cts.get(k)
        out.append(None if v is None or pd.isna(v) else float(v))
    return out


def fig_radar_compare(season: dict, selection: dict | None, team: str, label: str) -> go.Figure:
    sv = _vals(season)
    cv = _vals(selection) if selection is not None else None
    # Axes without data keep their label ("sin dato") but get no point: the polygon joins the
    # neighbouring observed axes instead of drawing a fake 0 or 50.
    def name(i, k):
        missing = sv[i] is None and (cv is None or cv[i] is None)
        return CTS_LABELS[k] + (' (sin dato)' if missing else '')
    labels = [name(i, k) for i, k in enumerate(RADAR_KEYS)]

    def closed(vals):
        pts = [(labels[i], v) for i, v in enumerate(vals) if v is not None]
        if pts: pts.append(pts[0])
        return [p[1] for p in pts], [p[0] for p in pts]
    fig = go.Figure()
    r, th = closed(sv)
    fig.add_trace(go.Scatterpolar(
        r=r, theta=th, name='Temporada completa', fill='toself',
        fillcolor='rgba(29,78,216,.10)', line=dict(color=ACCENT, width=2, dash='dash'),
        marker=dict(size=6, color=ACCENT),
        hovertemplate='Temporada · %{theta}: %{r:.1f}/100<extra></extra>'))
    if cv is not None:
        r, th = closed(cv)
        fig.add_trace(go.Scatterpolar(
            r=r, theta=th, name=label, fill='toself',
            fillcolor='rgba(200,155,60,.22)', line=dict(color=GOLD, width=3),
            marker=dict(size=8, color=GOLD, line=dict(color=NAVY, width=1)),
            hovertemplate=label.replace('%', '%%') + ' · %{theta}: %{r:.1f}/100<extra></extra>'))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 100], tickvals=[20, 40, 60, 80, 100], gridcolor=LIGHT, linecolor=LIGHT),
                   angularaxis=dict(gridcolor=LIGHT, linecolor=LIGHT, categoryorder='array', categoryarray=labels,
                                    type='category')),
        showlegend=True, legend=dict(orientation='h', y=-0.08, x=0.5, xanchor='center'),
        margin=dict(l=45, r=45, t=80, b=50), height=520, paper_bgcolor='white',
        font=dict(family='Inter, Segoe UI, sans-serif', color=NAVY),
        title=dict(text=f'Firma táctica (CTS) · {team}', x=.02, y=.96, font=dict(size=19, color=NAVY)))
    fig.add_annotation(x=.02, y=1.07, xref='paper', yref='paper', showarrow=False, xanchor='left',
                       text='Escala 0–100 · línea discontinua = temporada completa · dorado = selección',
                       font=dict(size=11, color=GREY))
    return fig


def fig_score_compare(season_rows: list[dict], sel: pd.DataFrame | None, team: str, label: str,
                      states: list[str]) -> go.Figure:
    states = [s for s in SCORE_ORDER if s in states] or list(SCORE_ORDER)
    x = [SCORE_LABELS[s] for s in states]
    season = pd.DataFrame(season_rows).set_index('segmento').reindex(states) if season_rows else None
    fig = make_subplots(rows=1, cols=4, subplot_titles=[f'{t} ({u})' for _, t, u in REACTION_METRICS],
                        horizontal_spacing=0.07)
    mode = 'lines+markers' if len(states) > 1 else 'markers'
    for i, (k, t, u) in enumerate(REACTION_METRICS, start=1):
        first = i == 1
        if sel is not None and not sel.empty:
            d = sel.set_index('segmento').reindex(states)
            fig.add_trace(go.Scatter(x=x, y=d[f'rival_{k}'], mode=mode, name='Rivales en la misma situación',
                                     line=dict(color=GREY, width=2, dash='dot'), marker=dict(size=8, color=GREY),
                                     showlegend=first, hovertemplate=f'Rivales · %{{x}}: %{{y:.1f}} {u}<extra></extra>'),
                          row=1, col=i)
        if season is not None and label != 'Temporada completa':
            fig.add_trace(go.Scatter(x=x, y=season[k], mode=mode, name=f'{team} · temporada completa',
                                     line=dict(color=ACCENT, width=2, dash='dash'), marker=dict(size=8, color=ACCENT),
                                     showlegend=first, hovertemplate=f'Temporada · %{{x}}: %{{y:.1f}} {u}<extra></extra>'),
                          row=1, col=i)
        if sel is not None and not sel.empty:
            d = sel.set_index('segmento').reindex(states)
            low = ~d['fiable'].fillna(False).astype(bool)
            events = d['eventos_equipo'].fillna(0).astype(int)
            notes = [f'{n} eventos' + (' · muestra baja' if lo else '') for n, lo in zip(events, low)]
            fig.add_trace(go.Scatter(x=x, y=d[k], mode=mode, name=label,
                                     line=dict(color=GOLD, width=3),
                                     marker=dict(size=12, color=['white' if lo else GOLD for lo in low],
                                                 line=dict(color=GOLD, width=2.5),
                                                 symbol=['circle-open' if lo else 'circle' for lo in low]),
                                     customdata=notes, showlegend=first,
                                     hovertemplate=f'Selección · %{{x}}: %{{y:.1f}} {u}<br>%{{customdata}}<extra></extra>'),
                          row=1, col=i)
        fig.update_yaxes(gridcolor=LIGHT, row=1, col=i)
        fig.update_xaxes(tickfont=dict(size=11), row=1, col=i)
    for a in fig.layout.annotations:
        a.font = dict(size=12, color=NAVY)
    fig.update_layout(height=430, paper_bgcolor='white', plot_bgcolor='white',
                      margin=dict(l=40, r=20, t=90, b=90),
                      legend=dict(orientation='h', y=-0.25, x=0, font=dict(size=12)),
                      title=dict(text=f'Cómo cambia {team} según el marcador · {label}', x=.01, y=.97,
                                 font=dict(size=17, color=NAVY)),
                      font=dict(family='Inter, Segoe UI, sans-serif', color=NAVY))
    return fig


# --------------------------------------------------------------- UI pieces
def _show(fig, key):
    st.plotly_chart(fig, use_container_width=True, key=key,
                    config={'displaylogo': False, 'toImageButtonOptions': {'format': 'png', 'scale': 3}})


def render_formation_matches(result: dict, shape: str) -> None:
    """Match list under the line-up pitch of one formation."""
    fm = formation_matches(result)
    rows = fm[fm['dibujo'].eq(shape)]
    if rows.empty:
        return
    w = int(rows['resultado'].eq('Victoria').sum()); e = int(rows['resultado'].eq('Empate').sum())
    l = int(rows['resultado'].eq('Derrota').sum())
    st.markdown(f"**Partidos en que inició con {shape}** · {len(rows)} partido{'s' if len(rows) != 1 else ''} · "
                f"{w} V · {e} E · {l} D")
    st.dataframe(rows[['n', 'rival', 'marcador', 'resultado']].rename(columns={
        'n': 'Partido', 'rival': 'Rival', 'marcador': 'Marcador registrado', 'resultado': 'Resultado'}),
        hide_index=True, use_container_width=True, height=min(38 * (len(rows) + 1) + 3, 360))
    st.caption('Formación = dibujo inicial (titulares antes del primer cambio). El marcador es el último '
               'registrado en los eventos; si el equipo cambió de dibujo durante el partido, cuenta el inicial.')


def _shape_selector(fm: pd.DataFrame, key: str, label: str) -> str:
    shapes = shapes_by_frequency(fm)
    counts = fm['dibujo'].value_counts()
    options = [ALL_SHAPES] + shapes
    names = {s: (f"{s} · {int(counts.get(s, 0))}" if s != ALL_SHAPES else s) for s in options}
    pick = st.segmented_control(label, options, format_func=lambda s: names[s], default=ALL_SHAPES,
                                key=key, selection_mode='single')
    return pick or ALL_SHAPES


def _delta_story(season: dict, sel: dict, label: str) -> str:
    diffs = []
    for k in RADAR_KEYS:
        a, b = season.get(k), sel.get(k)
        if a is None or b is None or pd.isna(a) or pd.isna(b):
            continue
        diffs.append((float(b) - float(a), CTS_LABELS[k]))
    ups = [f'{n} ({d:+.0f})' for d, n in sorted(diffs, reverse=True) if d >= 5][:2]
    downs = [f'{n} ({d:+.0f})' for d, n in sorted(diffs) if d <= -5][:2]
    if not ups and not downs:
        return f'**{label}:** la firma se mantiene cerca de la temporada completa (ninguna dimensión cambia 5 puntos o más).'
    parts = []
    if ups: parts.append('sube en ' + ' y '.join(ups))
    if downs: parts.append('baja en ' + ' y '.join(downs))
    return f'**{label}:** respecto a su temporada, el equipo ' + '; '.join(parts) + '.'


def render_cts_by_formation(result: dict, team: str) -> None:
    fm = formation_matches(result)
    season = result.get('cts') or {}
    if fm.empty:
        st.plotly_chart(fig_radar_compare(season, None, team, ''), use_container_width=True); return
    shape = _shape_selector(fm, 'cts_shape', 'Formación')
    pool = fm if shape == ALL_SHAPES else fm[fm['dibujo'].eq(shape)]
    opts = [ALL_MATCHES] + pool['match_id'].tolist()
    lab = dict(zip(pool['match_id'], pool['etiqueta']))
    all_name = ('Todos los partidos con ' + shape) if shape != ALL_SHAPES else 'Temporada completa (sin filtro)'
    match = st.selectbox('Partido', opts, format_func=lambda m: all_name if m == ALL_MATCHES else lab[m],
                         key=f'cts_match_{shape}')
    if shape == ALL_SHAPES and match == ALL_MATCHES:
        selection, label = None, ''
    else:
        ids = pool['match_id'].tolist() if match == ALL_MATCHES else [match]
        selection = cts_for_matches(result, ids)
        label = (f'{shape} · {len(ids)} partidos' if match == ALL_MATCHES
                 else (f'{shape} · ' if shape != ALL_SHAPES else '') + lab[match].split(' · ', 1)[1])
        if match != ALL_MATCHES and shape == ALL_SHAPES:
            label = f"{fm.set_index('match_id').loc[match, 'dibujo']} · " + lab[match].split(' · ', 1)[1]
    _show(fig_radar_compare(season, selection, team, label or 'Selección'), 'cts_radar_compare')
    if selection is None:
        st.caption('Elige una formación o un partido para superponer su firma sobre la temporada completa.')
    else:
        st.markdown(_delta_story(season, selection, label))
        rows = []
        for k in RADAR_KEYS:
            a, b = season.get(k), selection.get(k)
            fmt = lambda v: '—' if v is None or pd.isna(v) else f'{float(v):.0f}'
            diff = '—' if a is None or b is None or pd.isna(a) or pd.isna(b) else f'{float(b) - float(a):+.0f}'
            rows.append({'Dimensión': CTS_LABELS[k], 'Temporada': fmt(a), 'Selección': fmt(b), 'Diferencia': diff})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        missing = [CTS_LABELS[k] for k in RADAR_KEYS if selection.get(k) is None or pd.isna(selection.get(k))]
        note = (f"Sin dato en la selección: {', '.join(missing)} (no hay ventanas u oportunidades observables; "
                'no se dibuja ni se toma como cero). ' if missing else '')
        st.caption(note + f"Selección calculada con {selection['_events']:,} eventos del equipo y el mismo motor "
                   'que la temporada. Un solo partido es una muestra corta: compara tendencias, no cifras exactas.')


def render_score_by_formation(result: dict, team: str, season_rows: list[dict]) -> None:
    fm = formation_matches(result)
    if fm.empty:
        st.info('No hay partidos identificables para filtrar.'); return
    shape = _shape_selector(fm, 'score_shape', 'Formación')
    pool = fm if shape == ALL_SHAPES else fm[fm['dibujo'].eq(shape)]
    a, b = st.columns([1.3, 1])
    rivals = sorted(pool['rival'].unique().tolist())
    with a:
        rival = st.selectbox('Rival', [ALL_RIVALS] + rivals, key=f'score_rival_{shape}',
                             format_func=lambda r: r if r == ALL_RIVALS else
                             f"{r} · {int(pool['rival'].eq(r).sum())} partido{'s' if int(pool['rival'].eq(r).sum()) != 1 else ''}")
    with b:
        states = st.pills('Estado del marcador', list(SCORE_ORDER), selection_mode='multi',
                          default=list(SCORE_ORDER), format_func=lambda s: SCORE_LABELS[s], key='score_states')
    states = states or list(SCORE_ORDER)
    rows = pool if rival == ALL_RIVALS else pool[pool['rival'].eq(rival)]
    if shape == ALL_SHAPES and rival == ALL_RIVALS:
        label = 'Temporada completa'
    else:
        label = ' · '.join(x for x in [shape if shape != ALL_SHAPES else '', f'vs {rival}' if rival != ALL_RIVALS else ''] if x)
        label += f" ({len(rows)} partido{'s' if len(rows) != 1 else ''})"
    sel = score_reaction_for_matches(result, rows['match_id'].tolist())
    _show(fig_score_compare(season_rows, sel, team, label, states), 'score_compare')
    if not sel.empty:
        info = sel.set_index('segmento')
        parts = []
        for s in [x for x in SCORE_ORDER if x in states]:
            n = int(info.loc[s, 'eventos_equipo']) if s in info.index and pd.notna(info.loc[s, 'eventos_equipo']) else 0
            parts.append(f"{SCORE_LABELS[s]}: {n:,} eventos" + ('' if n >= MIN_TEAM_EVENTS else (' · sin datos' if n == 0 else ' · muestra baja')))
        st.caption('Muestra de la selección por estado del marcador — ' + ' · '.join(parts) + '. '
                   f'Círculo vacío = menos de {MIN_TEAM_EVENTS} eventos del equipo en ese estado; '
                   'si el equipo nunca estuvo en ese estado, el punto no aparece.')
    with st.expander('Partidos incluidos en esta selección'):
        st.dataframe(rows[['n', 'dibujo', 'rival', 'marcador', 'resultado']].rename(columns={
            'n': 'Partido', 'dibujo': 'Formación', 'rival': 'Rival', 'marcador': 'Marcador registrado',
            'resultado': 'Resultado'}), hide_index=True, use_container_width=True)
