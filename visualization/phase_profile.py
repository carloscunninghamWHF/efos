"""EFOS v0.4.28 — «Perfil por fase»: equipo vs. media de sus rivales.

Replaces the four score-state line charts in «Modelo de Juego y DT».
Only metrics that are direct StatsBomb fields/counts, fixed pitch zones, or
metrics EFOS already had (possession share and long-pass threshold from
coach_profile) are used. No new metric definition is introduced.

Comparison baseline = the opponents in the SAME selected matches (the CSV only
contains matches of the focal team, so a league average is not available).
"""
from __future__ import annotations

import html
import numpy as np
import pandas as pd
import streamlit as st

from coach_story.coach_profile import LONG_PASS, YARD_TO_M
from visualization.coach_formation_ui import (ALL_RIVALS, ALL_SHAPES, formation_matches, _shape_selector)
from visualization.efos_figures import SCORE_LABELS

BOX_X, BOX_Y = 102.0, (18.0, 62.0)          # StatsBomb 120x80 penalty area (fixed geometry)
FINAL_THIRD_X = 80.0                         # last third of a 120-unit pitch
OPP_HALF_X = 60.0
TOUCH_TYPES = {'Pass', 'Ball Receipt*', 'Carries', 'Carry', 'Shot', 'Dribble'}
ON_TARGET = {'Goal', 'Saved', 'Saved To Post'}
WON_TACKLE = {'Won', 'Success In Play', 'Success Out'}
ALL_STATES = 'Todo el partido'

# key, label, phase, kind, better, decimals, unit
METRICS = [
    ('goals', 'Goles', 'Ofensiva', 'count', 'high', 2, ''),
    ('xg', 'xG', 'Ofensiva', 'count', 'high', 2, ''),
    ('shots', 'Remates', 'Ofensiva', 'count', 'high', 2, ''),
    ('box_touches', 'Toques en área rival', 'Ofensiva', 'count', 'high', 2, ''),
    ('key_passes', 'Pases clave (terminan en remate)', 'Ofensiva', 'count', 'high', 2, ''),
    ('on_target_assists', 'Asistencias de remate al arco', 'Ofensiva', 'count', 'high', 2, ''),
    ('crosses_ok', 'Centros exitosos', 'Ofensiva', 'count', 'high', 2, ''),
    ('corners', 'Córners', 'Ofensiva', 'count', 'high', 2, ''),
    ('possession', 'Proporción de pases (%)', 'Organizativa', 'pct', 'none', 1, '%'),
    ('passes', 'Pases', 'Organizativa', 'count', 'high', 1, ''),
    ('pass_pct', '% pases exitosos', 'Organizativa', 'pct', 'high', 1, '%'),
    ('ft_ok', 'Pases al último tercio exitosos', 'Organizativa', 'count', 'high', 2, ''),
    ('ft_pct', '% pases al último tercio exitosos', 'Organizativa', 'pct', 'high', 1, '%'),
    ('long_ok', 'Pases largos exitosos', 'Organizativa', 'count', 'high', 2, ''),
    ('long_pct', '% pases largos exitosos', 'Organizativa', 'pct', 'high', 1, '%'),
    ('pass_len', 'Longitud media de pase (m)', 'Organizativa', 'mean', 'none', 1, ' m'),
    ('goals_against', 'Goles recibidos', 'Defensiva', 'count', 'low', 2, ''),
    ('xg_against', 'xG en contra', 'Defensiva', 'count', 'low', 2, ''),
    ('shots_against', 'Remates recibidos', 'Defensiva', 'count', 'low', 2, ''),
    ('recov_opp_half', 'Recuperaciones en campo rival', 'Defensiva', 'count', 'high', 2, ''),
    ('interceptions', 'Intercepciones', 'Defensiva', 'count', 'high', 2, ''),
    ('tackles_won', 'Duelos defensivos ganados', 'Defensiva', 'count', 'high', 2, ''),
    ('tackle_pct', '% duelos defensivos ganados', 'Defensiva', 'pct', 'high', 1, '%'),
    ('aerial_pct', '% duelos aéreos ganados', 'Defensiva', 'pct', 'high', 1, '%'),
]
DEFINITIONS = {
    'goals': 'Remates con resultado gol + goles en propia puerta a favor.',
    'xg': 'Suma del xG de StatsBomb de sus remates.',
    'box_touches': 'Pases, recepciones, conducciones, regates y remates dentro del área rival.',
    'key_passes': 'Pases que StatsBomb vincula a un remate.',
    'on_target_assists': 'Pases vinculados a un remate que fue gol o atajado.',
    'crosses_ok': 'Centros (marca StatsBomb) completados.',
    'possession': 'Proporción de pases propios entre los pases de ambos equipos; NO es tiempo de posesión.',
    'ft_ok': 'Pases completados que empiezan fuera y terminan dentro del último tercio.',
    'long_ok': f'Definición EFOS existente: pases de {LONG_PASS:.0f} o más (unidades StatsBomb) completados.',
    'recov_opp_half': 'Recuperaciones de balón registradas en campo rival.',
    'tackles_won': 'Duelos de entrada (tackle) ganados.',
    'aerial_pct': 'Duelos aéreos ganados / (ganados + perdidos).',
}


# ------------------------------------------------------------------ stats
def _col(df: pd.DataFrame, c: str) -> pd.Series:
    """Numeric column, or an all-NaN series when the provider did not export it."""
    return pd.to_numeric(df[c], errors='coerce') if c in df else pd.Series(np.nan, index=df.index, dtype=float)


def _side_stats(s: pd.DataFrame, shots_all: pd.DataFrame) -> dict:
    """Raw totals for one side (events of one team) within the selection."""
    et = s['event_type']
    num = lambda c: _col(s, c)
    x, y = num('location_x'), num('location_y')
    ex = num('end_location_x')
    shots = s[et.eq('Shot')]
    passes = s[et.eq('Pass')]
    complete = passes['outcome_name'].isna() if 'outcome_name' in passes else pd.Series(True, index=passes.index)
    px, pex = x.loc[passes.index], ex.loc[passes.index]
    plen = _col(passes, 'pass_length')
    ft = (px < FINAL_THIRD_X) & (pex >= FINAL_THIRD_X)
    long_ = plen >= LONG_PASS
    linked = passes[passes['assisted_shot_id'].notna()] if 'assisted_shot_id' in passes else passes.iloc[0:0]
    on_target_ids = set(shots_all.loc[shots_all['shot_outcome'].isin(ON_TARGET), 'event_id'].astype(str)) \
        if {'event_id', 'shot_outcome'} <= set(shots_all.columns) else set()
    tackles = s[et.eq('Duel') & s['type_name'].eq('Tackle')] if 'type_name' in s else s.iloc[0:0]
    aerial_won = int(s['aerial_won'].fillna(False).astype(bool).sum()) if 'aerial_won' in s else None
    aerial_lost = int((et.eq('Duel') & s['type_name'].eq('Aerial Lost')).sum()) if 'type_name' in s else 0
    in_box = (x >= BOX_X) & y.between(*BOX_Y)
    return {
        'goals': (int(shots['shot_outcome'].eq('Goal').sum()) if 'shot_outcome' in shots else 0) + int(et.eq('Own Goal For').sum()),
        'xg': float(_col(shots, 'statsbomb_xg').sum()),
        'shots': int(len(shots)),
        'box_touches': int((et.isin(TOUCH_TYPES) & in_box).sum()),
        'key_passes': int(len(linked)),
        'on_target_assists': int(linked['assisted_shot_id'].astype(str).isin(on_target_ids).sum()) if len(linked) else 0,
        'crosses_ok': int((passes['pass_cross'].fillna(False).astype(bool) & complete).sum()) if 'pass_cross' in passes else 0,
        'corners': int(passes['type_name'].eq('Corner').sum()) if 'type_name' in passes else 0,
        'passes': int(len(passes)), 'passes_ok': int(complete.sum()),
        'ft_att': int(ft.sum()), 'ft_ok': int((ft & complete).sum()),
        'long_att': int(long_.sum()), 'long_ok': int((long_ & complete).sum()),
        'pass_len_m': float(plen.mean() * YARD_TO_M) if plen.notna().any() else np.nan,
        'recov_opp_half': int((et.eq('Ball Recovery') & (x >= OPP_HALF_X)).sum()),
        'interceptions': int(et.eq('Interception').sum()),
        'tackles': int(len(tackles)), 'tackles_won': int(tackles['outcome_name'].isin(WON_TACKLE).sum()) if len(tackles) else 0,
        'aerial_won': aerial_won, 'aerial_lost': aerial_lost,
    }


def _pct(a, b):
    return 100.0 * a / b if b else np.nan


def phase_profile(result: dict, match_ids, state: str | None = None) -> dict:
    """Per-match averages (counts) and pooled ratios for team and opponents."""
    team = result['focal_team']
    ev = result['events']
    ids = {str(m) for m in match_ids}
    sel = ev[ev['match_id'].astype(str).isin(ids)]
    if state and 'score_state' in sel:
        sel = sel[sel['score_state'].eq(state)]
    own = sel[sel['team'].eq(team)]
    opp = sel[sel['team'].notna() & ~sel['team'].eq(team)]
    n = int(own['match_id'].nunique())
    shots_all = sel[sel['event_type'].eq('Shot')]
    a, b = _side_stats(own, shots_all), _side_stats(opp, shots_all)

    def build(me, other):
        per = lambda v: v / n if n else np.nan
        aw, al = me['aerial_won'], me['aerial_lost']
        return {
            'goals': per(me['goals']), 'xg': per(me['xg']), 'shots': per(me['shots']),
            'box_touches': per(me['box_touches']), 'key_passes': per(me['key_passes']),
            'on_target_assists': per(me['on_target_assists']), 'crosses_ok': per(me['crosses_ok']),
            'corners': per(me['corners']),
            'possession': _pct(me['passes'], me['passes'] + other['passes']),
            'passes': per(me['passes']), 'pass_pct': _pct(me['passes_ok'], me['passes']),
            'ft_ok': per(me['ft_ok']), 'ft_pct': _pct(me['ft_ok'], me['ft_att']),
            'long_ok': per(me['long_ok']), 'long_pct': _pct(me['long_ok'], me['long_att']),
            'pass_len': me['pass_len_m'],
            'goals_against': per(other['goals']), 'xg_against': per(other['xg']),
            'shots_against': per(other['shots']),
            'recov_opp_half': per(me['recov_opp_half']), 'interceptions': per(me['interceptions']),
            'tackles_won': per(me['tackles_won']), 'tackle_pct': _pct(me['tackles_won'], me['tackles']),
            'aerial_pct': np.nan if aw is None else _pct(aw, aw + al),
        }
    return {'team': build(a, b), 'rivals': build(b, a), 'n_matches': n,
            'match_ids': sorted(own['match_id'].astype(str).unique().tolist()),
            'n_events': int(len(own)), 'state': state}


def classify(key: str, t: float, r: float) -> str:
    """'up' = clearly better than rivals, 'down' = clearly worse, 'mid' = similar or not comparable."""
    meta = next(m for m in METRICS if m[0] == key)
    kind, better = meta[3], meta[4]
    if key not in {'goals','goals_against','xg','xg_against','shots_against','pass_pct','ft_pct','long_pct','tackle_pct','aerial_pct'} or better == 'none' or pd.isna(t) or pd.isna(r):
        return 'mid'
    diff = t - r
    big = abs(diff) >= 3.0 if kind == 'pct' else (abs(diff) >= 0.10 * abs(r) if r else abs(diff) > 0)
    if not big:
        return 'mid'
    good = diff > 0 if better == 'high' else diff < 0
    return 'up' if good else 'down'


# ---------------------------------------------------------------- render
_CSS = """
<style>
.efos-pp {background:#FFFFFF; border:1px solid rgba(15,23,42,.08); border-radius:16px; padding:18px 22px 10px;}
.efos-pp h4 {margin:0 0 4px; font-size:1.15rem; color:#0B1220;}
.efos-pp .sub {font-size:.82rem; color:#64748B; margin-bottom:10px;}
.efos-pp .phase {font-weight:760; font-size:.95rem; color:#0B1220; margin:14px 0 4px; padding-top:6px;
  border-top:1px solid rgba(15,23,42,.08);}
.efos-pp .row {display:grid; grid-template-columns:minmax(150px,1.5fr) minmax(120px,2fr) 70px 70px 64px;
  gap:12px; align-items:center; padding:5px 0; border-bottom:1px solid rgba(15,23,42,.05); font-size:.88rem;}
.efos-pp .head {font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:#94A3B8; border-bottom:none;}
.efos-pp .lab {color:#1E293B;}
.efos-pp .track {position:relative; height:12px; background:#EEF2F6; border-radius:3px;}
.efos-pp .fill {position:absolute; left:0; top:0; bottom:0; border-radius:3px;}
.efos-pp .fill.up {background:#1F7A4D;} .efos-pp .fill.mid {background:#B8BEC6;} .efos-pp .fill.down {background:#C0262D;}
.efos-pp .tick {position:absolute; top:-4px; bottom:-4px; width:2px; background:#0B1220;}
.efos-pp .num {text-align:right; font-variant-numeric:tabular-nums; color:#0B1220;}
.efos-pp .riv {text-align:right; font-variant-numeric:tabular-nums; color:#64748B;}
.efos-pp .dif {text-align:right; font-variant-numeric:tabular-nums; font-size:.8rem;}
.efos-pp .dif.up {color:#1F7A4D;} .efos-pp .dif.down {color:#C0262D;} .efos-pp .dif.mid {color:#94A3B8;}
.efos-pp .legend {font-size:.78rem; color:#64748B; margin-top:10px; display:flex; gap:16px; flex-wrap:wrap;}
.efos-pp .sw {display:inline-block; width:12px; height:10px; border-radius:2px; margin-right:5px; vertical-align:middle;}
@media (max-width: 760px) {.efos-pp .row {grid-template-columns:1fr 1fr 56px 56px; } .efos-pp .dif {display:none;}}
</style>
"""


def _fmt(v, dec, unit):
    if v is None or pd.isna(v):
        return '—'
    return f'{v:,.{dec}f}{unit}'.replace(',', ' ')


CORE_METRICS = ('xg','shots','pass_pct','ft_pct','xg_against','shots_against','recov_opp_half','possession')

def profile_html(prof: dict, team: str, title: str, metric_keys=None) -> str:
    t, r = prof['team'], prof['rivals']
    rows = [f"<div class='efos-pp'><h4>{html.escape(title)}</h4>"
            f"<div class='sub'>{html.escape(team)} frente a la media de sus rivales en los mismos partidos · "
            f"valores por partido salvo porcentajes y medias · {prof['n_matches']} partido{'s' if prof['n_matches'] != 1 else ''}</div>",
            "<div class='row head'><div>Métrica</div><div></div><div class='num'>"
            f"{html.escape(team[:10])}</div><div class='riv'>Rivales</div><div class='dif'>Dif.</div></div>"]
    phase = None
    selected_keys = set(metric_keys) if metric_keys is not None else set(CORE_METRICS)
    for key, label, ph, kind, better, dec, unit in METRICS:
        if key not in selected_keys:
            continue
        if ph != phase:
            rows.append(f"<div class='phase'>{ph}</div>"); phase = ph
        tv, rv = t[key], r[key]
        cls = classify(key, tv, rv)
        top = 100.0 if kind == 'pct' else max(v for v in [tv, rv, 1e-9] if not pd.isna(v)) * 1.25
        w = 0 if pd.isna(tv) else max(0.0, min(100.0, 100 * tv / top))
        tick = '' if pd.isna(rv) else f"<div class='tick' style='left:calc({max(0.0, min(100.0, 100 * rv / top)):.1f}% - 1px)'></div>"
        if pd.isna(tv) or pd.isna(rv):
            dif = '—'
        else:
            d = tv - rv
            dif = f'{d:+.{1 if kind == "pct" else dec}f}' + (' pp' if kind == 'pct' else '')
        tip = html.escape(DEFINITIONS.get(key, label))
        rows.append(f"<div class='row' title='{tip}'><div class='lab'>{html.escape(label)}</div>"
                    f"<div class='track'><div class='fill {cls}' style='width:{w:.1f}%'></div>{tick}</div>"
                    f"<div class='num'>{_fmt(tv, dec, '')}</div>"
                    f"<div class='riv'>{_fmt(rv, dec, '')}</div><div class='dif {cls}'>{dif}</div></div>")
    rows.append("<div class='legend'><span><span class='sw' style='background:#1F7A4D'></span>Indicador favorable, según definición</span>"
                "<span><span class='sw' style='background:#B8BEC6'></span>Sin dirección automática / diferencia pequeña</span>"
                "<span><span class='sw' style='background:#C0262D'></span>Indicador desfavorable, según definición</span>"
                "<span><span class='sw' style='background:#0B1220;width:2px'></span>Media de los rivales</span></div></div>")
    return _CSS + ''.join(rows)


def _summary(prof: dict) -> tuple[list[str], list[str]]:
    ups, downs = [], []
    for key, label, *_ in METRICS:
        c = classify(key, prof['team'][key], prof['rivals'][key])
        if c == 'up': ups.append(label)
        elif c == 'down': downs.append(label)
    return ups, downs


def render_phase_profile(result: dict, team: str, match_ids=None) -> None:
    """The staff sees eight interpretable indicators; no misleading score-state rates.

    Advanced data remains accessible on demand. One denominator throughout:
    averages per whole match, versus the opponents faced IN those matches.
    """
    fm = formation_matches(result)
    if fm.empty:
        st.info('No hay partidos identificables para comparar.'); return
    if match_ids is not None:
        fm = fm[fm.match_id.astype(str).isin(set(map(str,match_ids)))]
    if fm.empty:
        st.info('No hay partidos con un perfil de formación para esta selección.'); return
    prof = phase_profile(result, fm.match_id, None)
    if not prof['n_matches']:
        st.info('No hay eventos comparables en la selección.'); return
    st.markdown(profile_html(prof, team, 'Rendimiento frente a los rivales enfrentados'), unsafe_allow_html=True)
    t, r = prof['team'], prof['rivals']
    if pd.notna(t['xg']) and pd.notna(r['xg']):
        relation = ('mayor' if t['xg'] > r['xg'] else 'menor' if t['xg'] < r['xg'] else 'igual')
        st.markdown(f"**Lectura del contraste.** En {prof['n_matches']} partidos, {team} produjo "
                    f"{t['xg']:.2f} xG por partido, frente a {r['xg']:.2f} del conjunto de rivales "
                    f"en esos encuentros ({relation} peligro esperado). "
                    f"Completó el {t['pass_pct']:.1f}% de sus pases y permitió "
                    f"{t['shots_against']:.1f} remates por partido. Son observaciones, no un juicio "
                    'sobre la intención del entrenador ni una posición en el ranking de liga.')
    st.caption('Unidad: valores por partido completo, salvo porcentajes; comparación con los rivales enfrentados, NO con la media de Liga MX. '
               'La proporción de pases no equivale a tiempo con balón. Sin filtros de marcador: dividir eventos parciales por partidos produce tasas engañosas.')
    with st.expander('Ver todas las métricas y definiciones · análisis técnico', expanded=False):
        st.markdown(profile_html(prof, team, 'Detalle de indicadores', metric_keys=[m[0] for m in METRICS]),unsafe_allow_html=True)
        st.caption('Solo ciertos indicadores poseen dirección contextual estable; más acciones defensivas o más pases no significan por sí solos mejor rendimiento.')
