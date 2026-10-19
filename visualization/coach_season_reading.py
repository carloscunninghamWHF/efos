"""EFOS v0.4.27 — Lectura de temporada para el cuerpo técnico.

Plain-language readings under the CTS radar and under the score-state charts of
«Modelo de Juego y DT». Every sentence is generated from the season numbers
already computed by EFOS (CTS, tactical summary, score segmentation, formation
table); nothing is hard-coded for a specific team. The text describes what
happened and what to review; it never claims a cause or a coach's intention.
"""
from __future__ import annotations

import html
import pandas as pd
import streamlit as st

from coach_story.coach_profile import MIN_TEAM_EVENTS
from visualization.coach_formation_ui import RADAR_KEYS, cts_for_matches, formation_matches
from visualization.efos_figures import CTS_LABELS

POINTS = {'Victoria': 3, 'Empate': 1, 'Derrota': 0}
MIN_SHAPE_MATCHES = 3


def _level(v: float) -> str:
    return 'alto' if v >= 70 else 'medio' if v >= 40 else 'bajo'


def _n(x: float, d: int = 1) -> str:
    return f'{x:,.{d}f}'.replace(',', ' ')


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


# ------------------------------------------------------------------ radar
def _dimension_sentence(k: str, v: float, s: dict, matches: int) -> str:
    m = max(matches, 1)
    ev = max(int(s.get('events') or 0), 1)
    if k == 'attack':
        share = 100 * s.get('final_third_events', 0) / ev
        return (f"**Ataque ({v:.0f}, {_level(v)}):** el {share:.0f} % de sus acciones ocurre en el último tercio. "
                'El equipo pasa mucho tiempo cerca del área rival.' if v >= 70 else
                f"**Ataque ({v:.0f}, {_level(v)}):** el {share:.0f} % de sus acciones ocurre en el último tercio.")
    if k == 'defense':
        x = s.get('mean_pressure_x')
        where = ''
        if x is not None and pd.notna(x):
            where = (' y la mayoría en campo rival' if x >= 60 else ' alrededor del medio campo' if x >= 50
                     else ' sobre todo en su propio campo')
        return (f"**Defensa ({v:.0f}, {_level(v)}):** registra {_n(s.get('pressures', 0) / m, 0)} presiones por partido"
                f"{where}.")
    if k == 'transition':
        return (f"**Transición ({v:.0f}, {_level(v)}):** tras perder el balón, reacciona con una acción defensiva "
                f"en menos de 5 segundos en el {v:.0f} % de las pérdidas.")
    if k == 'construction':
        share = 100 * s.get('build_up_passes', 0) / ev
        return (f"**Construcción ({v:.0f}, {_level(v)}):** los pases en su primer tercio (salida desde atrás) son el "
                f"{share:.0f} % de sus acciones ({_n(s.get('build_up_passes', 0) / m, 0)} por partido).")
    if k == 'progression':
        return (f"**Progresión ({v:.0f}, {_level(v)}):** {_n(s.get('deep_progressions', 0) / m, 1)} pases por partido "
                'que viajan desde su campo hasta el último tercio.')
    return f"**{CTS_LABELS[k]} ({v:.0f})**"


def radar_season_reading(result: dict) -> dict | None:
    cts = result.get('cts') or {}
    s = result.get('tactical_summary') or {}
    fm = formation_matches(result)
    vals = {k: float(cts[k]) for k in RADAR_KEYS if cts.get(k) is not None and pd.notna(cts.get(k))}
    if not vals or fm.empty:
        return None
    team = result.get('focal_team', 'El equipo')
    matches = int(len(fm))
    order = sorted(vals.items(), key=lambda kv: -kv[1])
    top = [k for k, v in order if v >= 60][:2] or [order[0][0]]
    low = [k for k, v in reversed(order) if v < 40][:2]

    # 1. What happened
    known = fm[fm['resultado'].isin(POINTS)]
    w, d, l = (int(known['resultado'].eq(x).sum()) for x in ('Victoria', 'Empate', 'Derrota'))
    ppg = known['resultado'].map(POINTS).mean() if len(known) else None
    record = (f"En {_plural(matches, 'partido')} sumó {w} victorias, {d} empates y {l} derrotas"
              + (f" ({ppg:.2f} puntos por partido)." if ppg is not None else '.'))
    identity = (f"{record} Su firma está marcada por **{' y '.join(CTS_LABELS[k].lower() for k in top)}**"
                + (f", y lo que menos aparece es **{' y '.join(CTS_LABELS[k].lower() for k in low)}**." if low else '.'))
    lines = [_dimension_sentence(k, vals[k], s, matches) for k, _ in order]

    # 2. Why it matters (interpretation rules, always conditional)
    why = []
    if 'attack' in vals and vals['attack'] >= 70 and vals.get('progression', 100) < 30:
        why.append('Llega mucho al último tercio pero con pocos pases largos desde su campo: el equipo avanza '
                   'circulando y se instala arriba, no saltando líneas en un pase. La baja progresión describe '
                   'su forma de avanzar, no necesariamente una carencia.')
    if 'attack' in vals and vals['attack'] >= 70 and vals.get('construction', 100) < 35:
        why.append('La salida desde atrás pesa poco en el total de su juego porque pasa gran parte del tiempo lejos de '
                   'su portería. Hay menos situaciones de ese tipo para evaluar cómo sale cuando el rival presiona alto.')
    if 'transition' in vals and vals['transition'] < 50:
        side = ('Como juega mucho en campo rival, cada pérdida sin reacción deja espacio a la espalda.'
                if vals.get('attack', 0) >= 70 else 'Más de la mitad de sus pérdidas no tienen una reacción inmediata.')
        why.append(f"Reacciona rápido en menos de la mitad de sus pérdidas ({vals['transition']:.0f} %). {side}")
    if 'defense' in vals and vals['defense'] >= 60:
        why.append('Presiona con frecuencia: el equipo busca recuperar el balón pronto. Volumen no es eficacia; '
                   'conviene cruzarlo con las recuperaciones de «Cómo defiende».')

    # 3. Formations with enough matches
    shapes = []
    for shape, g in fm[fm['dibujo'].ne('No identificable')].groupby('dibujo'):
        g = g[g['resultado'].isin(POINTS)]
        if len(g) < MIN_SHAPE_MATCHES:
            continue
        c = cts_for_matches(result, g['match_id'])
        diffs = []
        for k in RADAR_KEYS:
            if k in vals and c.get(k) is not None and pd.notna(c.get(k)) and abs(float(c[k]) - vals[k]) >= 8:
                diffs.append(f"{CTS_LABELS[k].lower()} {float(c[k]) - vals[k]:+.0f}")
        shapes.append({'shape': shape, 'n': len(g), 'ppg': g['resultado'].map(POINTS).mean(),
                       'w': int(g['resultado'].eq('Victoria').sum()), 'd': int(g['resultado'].eq('Empate').sum()),
                       'l': int(g['resultado'].eq('Derrota').sum()), 'diffs': diffs, 'cts': c})
    shapes.sort(key=lambda x: -x['n'])
    shape_lines = []
    for x in shapes:
        tail = (' · respecto a su temporada: ' + ', '.join(x['diffs'])) if x['diffs'] else ' · firma muy parecida a la de la temporada'
        shape_lines.append(f"**{x['shape']}** · {x['n']} partidos · {x['w']}V {x['d']}E {x['l']}D · "
                           f"{x['ppg']:.2f} pts/partido{tail}.")

    # 4. Decisions
    decide = []
    if 'transition' in vals and vals['transition'] < 50:
        decide.append(f"**Prioridad 1 · reacción tras pérdida.** Hoy responde en menos de la mitad de las pérdidas "
                      f"({vals['transition']:.0f} %): para un equipo que ataca tanto, es la primera protección ante el contraataque. "
                      'Revisar en vídeo las pérdidas sin reacción en campo rival y quién está cerca del balón; '
                      'definir quién presiona primero y quién cierra el pase hacia dentro.')
    if shapes:
        base = shapes[0]
        best = max(shapes, key=lambda x: (x['ppg'], x['n']))
        if best['shape'] == base['shape']:
            decide.append(f"**Dibujo base · {base['shape']}.** Es el más usado y el que más puntos por partido da entre los "
                          f"dibujos con {MIN_SHAPE_MATCHES} o más partidos: hay respaldo para mantenerlo como plan A.")
        else:
            decide.append(f"**Dibujo base · {base['shape']}** ({base['ppg']:.2f} pts/partido) frente a **{best['shape']}** "
                          f"({best['ppg']:.2f} en {best['n']} partidos). La diferencia merece revisión, pero con tan pocos "
                          'partidos el rival puede explicar más que el dibujo.')
        press = [x for x in shapes if x['cts'].get('defense') is not None]
        if len(press) >= 2:
            hp = max(press, key=lambda x: x['cts']['defense'])
            if hp['shape'] != best['shape'] and hp['ppg'] < best['ppg']:
                decide.append(f"**Presionar más no dio más puntos.** Con **{hp['shape']}** presionó más "
                              f"(defensa {hp['cts']['defense']:.0f}) pero sumó {hp['ppg']:.2f} pts/partido. "
                              'Antes de subir la presión, comprobar si esos partidos fueron contra rivales distintos o si la '
                              'presión dejó espacios.')
    if 'attack' in vals and vals['attack'] >= 70:
        shots = s.get('shots') or 0; goals = s.get('goals') or 0
        if shots:
            decide.append(f"**Llegar no es el problema.** Registra {_n(shots / max(matches, 1), 1)} remates y "
                          f"{_n(goals / max(matches, 1), 2)} goles por partido. Si faltan goles, el trabajo está en la "
                          'última decisión y la calidad del remate, no en el plan para llegar.')
    caveat = ('Escala 0–100 propia de EFOS: compara al equipo consigo mismo, no lo ordena frente a la liga. '
              f'Puntos por dibujo sólo con {MIN_SHAPE_MATCHES} o más partidos; el rival y el contexto también influyen. '
              'Las lecturas describen lo registrado, no las intenciones del entrenador.')
    return {'team': team, 'identity': identity, 'lines': lines, 'why': why, 'shapes': shape_lines,
            'decide': decide, 'caveat': caveat}


# ------------------------------------------------------------ score state
METRIC_TEXT = {
    'posesion': ('Posesión', 'puntos de posesión', 1),
    'presion_alta': ('Presión en campo rival', 'puntos de presión arriba', 1),
    'altura_bloque': ('Altura de su defensa', 'm', 0),
    'pase_largo': ('Pase largo', 'puntos de pase largo', 1),
}


def _lead_record(result: dict, fm: pd.DataFrame):
    ev = result['events']
    if 'score_state' not in ev:
        return None
    states = ev.groupby(ev['match_id'].astype(str))['score_state'].agg(lambda x: set(x.dropna()))
    f = fm[fm['resultado'].isin(POINTS)].set_index('match_id')
    led = [m for m in f.index if 'winning' in states.get(m, set())]
    trailed = [m for m in f.index if 'losing' in states.get(m, set())]
    lost = f.loc[[m for m in led if f.loc[m, 'resultado'] != 'Victoria']]
    saved = f.loc[[m for m in trailed if f.loc[m, 'resultado'] != 'Derrota']]
    return {'led': len(led), 'lost': lost, 'trailed': len(trailed), 'saved': saved}


def score_season_reading(result: dict, rows: list[dict]) -> dict | None:
    d = pd.DataFrame(rows)
    if d.empty or not {'losing', 'winning'} <= set(d['segmento']):
        return None
    d = d.set_index('segmento')
    if not (bool(d.loc['losing', 'fiable']) and bool(d.loc['winning', 'fiable'])):
        return None
    team = result.get('focal_team', 'El equipo')
    fm = formation_matches(result)
    ev = result['events']
    own = ev[ev['team'].eq(team)]
    share = own['score_state'].value_counts(normalize=True) if 'score_state' in own else pd.Series(dtype=float)
    time_line = ''
    if len(share):
        time_line = (f"Del total de sus acciones, el {100 * share.get('drawing', 0):.0f} % fue con empate, el "
                     f"{100 * share.get('winning', 0):.0f} % ganando y el {100 * share.get('losing', 0):.0f} % perdiendo.")

    changes = []
    similar = 0
    for k, (label, unit, dec) in METRIC_TEXT.items():
        a, b = float(d.loc['losing', k]), float(d.loc['winning', k])
        ra, rb = float(d.loc['losing', f'rival_{k}']), float(d.loc['winning', f'rival_{k}'])
        delta, rdelta = b - a, rb - ra
        verb = 'sube' if delta > 0 else 'baja'
        tol = 2.0
        if abs(delta - rdelta) <= tol:
            comp = 'como cualquier rival en la misma situación'; similar += 1
        elif abs(delta) > abs(rdelta):
            comp = f'más que sus rivales en la misma situación ({rdelta:+.{dec}f})'
        else:
            comp = f'menos que sus rivales en la misma situación ({rdelta:+.{dec}f})'
        unit_txt = ' m' if unit == 'm' else ' puntos'
        changes.append(f"**{label}:** {a:.{dec}f} perdiendo → {b:.{dec}f} ganando "
                       f"({verb} {abs(delta):.{dec}f}{unit_txt}), {comp}.")
    pos_gap = float(d.loc['winning', 'posesion']) - float(d.loc['winning', 'rival_posesion'])
    height_gap = float(d.loc['winning', 'altura_bloque']) - float(d.loc['winning', 'rival_altura_bloque'])
    drop_h = float(d.loc['losing', 'altura_bloque']) - float(d.loc['winning', 'altura_bloque'])
    drop_p = float(d.loc['losing', 'presion_alta']) - float(d.loc['winning', 'presion_alta'])

    summary = ('Con el marcador a favor el equipo **se repliega**: tiene menos el balón, presiona menos arriba y '
               'defiende más cerca de su portería. ' if drop_h > 3 and drop_p > 3 else
               'El equipo cambia poco su forma de jugar con el marcador. ')
    if similar >= 3:
        summary += 'Ese cambio es del mismo tamaño que el de un rival típico: es la reacción normal al marcador, no un rasgo propio. '
    if pos_gap > 5 and height_gap > 3:
        summary += (f'Aun replegado sigue siendo más dominante que un rival que va ganando: '
                    f'{pos_gap:.0f} puntos más de posesión y defensa {height_gap:.0f} m más adelantada.')

    lead = _lead_record(result, fm)
    lead_lines, decide = [], []
    if lead and lead['led']:
        lost = lead['lost']
        names = ', '.join(f"{r.rival} ({r.marcador})" for r in lost.itertuples()) if len(lost) else ''
        lead_lines.append(f"Se puso por delante en **{lead['led']} partidos** y no ganó **{len(lost)}**"
                          + (f": {names}." if names else '.'))
    if lead and lead['trailed']:
        saved = lead['saved']
        lead_lines.append(f"Fue por detrás en **{lead['trailed']} partidos** y evitó la derrota en **{len(saved)}**"
                          + (f" ({int(saved['resultado'].eq('Victoria').sum())} remontadas ganadas)." if len(saved) else '.'))
    if lead and lead['led'] and len(lead['lost']) >= max(2, round(0.2 * lead['led'])):
        decide.append(f"**Gestión de la ventaja.** {len(lead['lost'])} de {lead['led']} ventajas no terminaron en victoria. "
                      f"Al ponerse por delante la defensa baja {drop_h:.0f} m y la presión arriba cae {drop_p:.0f} puntos. "
                      'Revisar en vídeo qué pasó después del gol a favor en esos partidos: si el repliegue fue una decisión '
                      'o una consecuencia del empuje rival, y si hacen falta cambios o un plan para seguir con el balón.')
    if lead and lead['trailed']:
        k_saved, k_tr = len(lead['saved']), lead['trailed']
        base = (f"Con el marcador en contra sube a {float(d.loc['losing', 'posesion']):.0f} % de posesión y presiona más "
                f"arriba, y evitó la derrota en {k_saved} de {k_tr} partidos. ")
        if k_saved >= 0.5 * k_tr:
            decide.append('**Reacción cuando pierde.** ' + base + 'Más de la mitad de las veces le alcanzó: identificar qué '
                          'ajustes (cambios, dibujo) acompañan esas remontadas para repetirlos.')
        else:
            decide.append('**Reacción cuando pierde.** ' + base + f'Perdió {k_tr - k_saved} de esos {k_tr}: tener más el '
                          'balón no bastó. Revisar qué remates genera con el marcador en contra y si los cambios llegan a tiempo.')
    if 'drawing' in d.index and bool(d.loc['drawing', 'fiable']) and len(share) and share.get('drawing', 0) >= 0.45:
        decide.append(f"**El partido se juega empatado.** Más de la mitad de sus acciones ocurren con el marcador igualado "
                      f"({100 * share.get('drawing', 0):.0f} %): ahí se decide la temporada. Con empate tiene "
                      f"{float(d.loc['drawing', 'posesion']):.0f} % de posesión; el foco es convertir ese control en la "
                      'primera ventaja.')
    caveat = (f'Cada estado se compara con lo que hicieron sus rivales en esa misma situación. Mínimo {MIN_TEAM_EVENTS} '
              'acciones del equipo por estado. Que el equipo se repliegue al ir ganando y luego empate no demuestra que '
              'el repliegue cause el empate: es la pista para revisar en vídeo.')
    return {'team': team, 'summary': summary, 'time': time_line, 'changes': changes, 'lead': lead_lines,
            'decide': decide, 'caveat': caveat}


# --------------------------------------------------------------- rendering
_CSS = """
<style>
.efos-reading {background:#FFFFFF; border:1px solid rgba(15,23,42,.08); border-left:5px solid #C89B3C;
  border-radius:16px; padding:18px 22px 6px; margin:14px 0 6px;}
.efos-reading .kick {font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; color:#9A7426; font-weight:700;}
.efos-reading .ttl {font-size:1.18rem; font-weight:760; color:#0B1220; margin:2px 0 6px; letter-spacing:-.02em;}
.efos-reading .lede {font-size:.98rem; color:#1E293B; line-height:1.6; margin-bottom:6px;}
</style>
"""


def _box(kicker: str, title: str, lede: str) -> None:
    st.markdown(_CSS + f"<div class='efos-reading'><div class='kick'>{html.escape(kicker)}</div>"
                f"<div class='ttl'>{html.escape(title)}</div></div>", unsafe_allow_html=True)
    st.markdown(lede)


def render_radar_reading(result: dict) -> None:
    r = radar_season_reading(result)
    if not r:
        return
    _box('Lectura para el cuerpo técnico · toda la temporada', f"¿Qué tipo de equipo fue {r['team']}?", r['identity'])
    st.markdown('**Lo que pasó**')
    st.markdown('\n'.join(f'- {x}' for x in r['lines']))
    if r['why']:
        st.markdown('**Por qué importa**')
        st.markdown('\n'.join(f'- {x}' for x in r['why']))
    if r['shapes']:
        st.markdown(f'**Según el dibujo** (sólo dibujos con {MIN_SHAPE_MATCHES} o más partidos)')
        st.markdown('\n'.join(f'- {x}' for x in r['shapes']))
    if r['decide']:
        st.markdown('**Qué decidir**')
        st.markdown('\n'.join(f'{i}. {x}' for i, x in enumerate(r['decide'], 1)))
    st.caption(r['caveat'])


def render_score_reading(result: dict, rows: list[dict]) -> None:
    r = score_season_reading(result, rows)
    if not r:
        return
    _box('Lectura para el cuerpo técnico · toda la temporada', f"¿Cómo reacciona {r['team']} al marcador?", r['summary'])
    if r['time']:
        st.markdown(r['time'])
    st.markdown('**Lo que cambia de ir perdiendo a ir ganando**')
    st.markdown('\n'.join(f'- {x}' for x in r['changes']))
    if r['lead']:
        st.markdown('**Ventajas y remontadas**')
        st.markdown('\n'.join(f'- {x}' for x in r['lead']))
    if r['decide']:
        st.markdown('**Qué decidir**')
        st.markdown('\n'.join(f'{i}. {x}' for i, x in enumerate(r['decide'], 1)))
    st.caption(r['caveat'])
