"""EFOS v0.4.21 — executive editorial layer built only from canonical engine outputs.

The executive brief is an explanation layer, NOT a tactical scoring model.
It never recomputes ESI, changes possession definitions, fabricates opponents,
or turns observed event labels into conclusions about tactical intent.
"""
from __future__ import annotations

import pandas as pd

from coach_story.executive_narrative import build_executive_chapters
from intelligence.defensive_open_play import STATES


def _signal(section: str, headline: str, value: str, caption: str, insight: str,
            focus: str, evidence: str, limitation: str, module: str, status: str) -> dict:
    return dict(section=section, headline=headline, value=value, caption=caption,
                insight=insight, focus=focus, evidence=evidence, limitation=limitation,
                module=module, status=status)


def _attack(result: dict, chapter: dict) -> dict:
    o = result.get('offensive_story') or {}
    entry = o.get('entry')
    n = int(o.get('n_possessions') or 0)
    nm = int(o.get('n_matches') or 0)
    if n and isinstance(entry, dict) and int(entry.get('denominator') or 0) > 0:
        k = int(entry['count']); denominator = int(entry['denominator'])
        lane = str(entry['lane']).lower()
        share = 100 * k / denominator
        # Do not confuse the largest of three corridors with a majority.
        reading = 'predomina' if share > 50 else 'es el más frecuente'
        return _signal('CON BALÓN', 'Desde dónde empieza', f'{share:.0f}%',
            f'{k} de {denominator} inicios registrados · {lane}',
            f'El corredor {lane} {reading} como origen observado de las secuencias de juego abierto.',
            'Seguir las secuencias y comprobar si esa ruta se mantiene ante otros rivales.',
            chapter['evidence'],
            'El origen es la primera acción con coordenadas; no revela un dibujo simultáneo.',
            'Ataque Organizado', o.get('status', 'EXPLORATORY'))
    if n:
        return _signal('CON BALÓN', 'Cómo inicia el equipo', str(n),
            f'Secuencias de juego abierto · {nm} partidos',
            f'Se identificaron {n} secuencias, pero sus corredores de inicio no son evaluables.',
            'Revisar cobertura espacial antes de señalar una ruta de construcción.',
            chapter['evidence'], chapter['limitation'], 'Ataque Organizado', 'SMALL_SAMPLE')
    return _signal('CON BALÓN', 'Cómo inicia el equipo', '—', 'Sin muestra evaluable',
        'No hay secuencias de juego abierto analizables en los archivos cargados.',
        'Revisar las columnas de posesión y coordenadas.', chapter['evidence'],
        chapter['limitation'], 'Ataque Organizado', 'INSUFFICIENT')


def _defense(result: dict, chapter: dict) -> dict:
    d = result.get('defensive_open_play_possessions')
    if isinstance(d, pd.DataFrame) and not d.empty and {'scenario', 'shot', 'match_id'}.issubset(d.columns):
        g = d[d['scenario'].isin(STATES)]
        if len(g):
            shots = int(g['shot'].fillna(0).astype(bool).sum())
            n = len(g); pct = 100 * shots / n
            matches = int(g['match_id'].nunique())
            status = 'DESCRIPTIVE' if n >= 30 and matches >= 5 else 'SMALL_SAMPLE'
            return _signal('SIN BALÓN', 'Cuándo consigue rematar el rival', f'{pct:.1f}%',
                f'{shots} de {n} posesiones clasificadas con remate',
                'Una parte de las posesiones rivales clasificadas termina en remate. La cifra no identifica por sí sola una debilidad.',
                'Comparar la frecuencia por escenario defensivo y revisar las secuencias con remate.',
                chapter['evidence'],
                'Solo tres escenarios clasificados de juego abierto; no equivale al total de ataques rivales.',
                'Defensa Organizada', status)
    return _signal('SIN BALÓN', 'Cómo protege su portería', '—', 'Sin muestra defensiva clasificada',
        'La muestra no permite resumir los escenarios defensivos con un denominador verificable.',
        'Revisar posesiones rivales y sus etiquetas antes de interpretar espacios.',
        chapter['evidence'], chapter['limitation'], 'Defensa Organizada', 'INSUFFICIENT')


def _transition(result: dict, chapter: dict) -> dict:
    verified = result.get('verified_transitions')
    if isinstance(verified,dict) and verified.get('status')=='ok':
        v=verified.get('defensive')
        if isinstance(v,pd.DataFrame) and not v.empty and {'pressures_5s','recovered_5s','match_id'}.issubset(v.columns):
            n=len(v)
            k=int(pd.to_numeric(v.pressures_5s,errors='coerce').gt(0).sum())
            regained=int(v.recovered_5s.fillna(False).astype(bool).sum())
            games=int(v.match_id.nunique())
            status='DESCRIPTIVE' if n>=30 and games>=3 else 'SMALL_SAMPLE'
            return _signal('TRAS PÉRDIDA', 'Presión registrada en 5 segundos', f'{k/n:.1%}',
                f'{k} de {n} pérdidas verificadas · {regained} recuperaciones ≤5 s',
                'Solo pérdidas candidatas seguidas por una posesión rival verificada; la presión no demuestra éxito colectivo.',
                'Comparar casos con presión, recuperación y remate del rival.',
                f'{n} posesiones rivales confirmadas tras pérdida · {games} partidos',
                'No engloba todas las pérdidas; los eventos de presión no son trayectorias ni coordinación demostrada.',
                'Cómo defiende',status)
    t = result.get('transitions')
    team = result.get('focal_team')
    if (isinstance(t, pd.DataFrame) and not t.empty and team is not None and
            {'team_lost', 'response_within_5s', 'match_id'}.issubset(t.columns)):
        losses = t[t.team_lost.eq(team)]
        if len(losses):
            positive = int(losses.response_within_5s.fillna(False).astype(bool).sum())
            n = len(losses); pct = 100 * positive / n
            matches = int(losses.match_id.nunique())
            status = 'DESCRIPTIVE' if n >= 20 and matches >= 3 else 'SMALL_SAMPLE'
            return _signal('TRAS PÉRDIDA', 'Reacción en los primeros 5 segundos', f'{pct:.1f}%',
                f'{positive} de {n} cambios con una acción registrada',
                'En esta proporción de pérdidas se observa presión, recuperación o intercepción etiquetada durante los cinco segundos posteriores.',
                'Distinguir cuándo hubo recuperación efectiva y qué hizo el rival a continuación.',
                chapter['evidence'],
                'Acción temprana no equivale a recuperación, éxito de presión ni plan del entrenador.',
                'Transiciones', status)
    return _signal('TRAS PÉRDIDA', 'Reacción después de perderla', '—',
        'Sin transiciones elegibles',
        'Los eventos cargados no permiten estimar la reacción tras pérdida.',
        'Verificar equipo propietario y marcas temporales.',
        chapter['evidence'], chapter['limitation'], 'Transiciones', 'INSUFFICIENT')


def build_executive_brief(result: dict) -> dict:
    """Build a short editorial story and three non-overlapping *questions*.

    The underlying event sets CAN overlap (e.g. loss response and defensive
    scenarios). Values are never added across the three sections.
    """
    chapters = build_executive_chapters(result)
    signals = [_attack(result, chapters[0]), _defense(result, chapters[1]),
               _transition(result, chapters[2])]
    a, d, t = signals
    count_valid = sum(s['status'] != 'INSUFFICIENT' for s in signals)
    if count_valid:
        observations = []
        if a['status'] != 'INSUFFICIENT':
            entry = (result.get('offensive_story') or {}).get('entry')
            if isinstance(entry, dict) and int(entry.get('denominator') or 0) > 0:
                lane = str(entry['lane']).lower()
                observations.append(f"Con balón, el {a['value']} de las secuencias con inicio registrado "
                                    f"comienza en el corredor {lane}; es la ruta de origen más frecuente en la muestra.")
            else:
                observations.append('Con balón, se reconocen secuencias de juego abierto, aunque no puede establecerse su corredor de inicio.')
        if d['status'] != 'INSUFFICIENT':
            observations.append(f"Sin balón, el {d['value']} de las posesiones rivales clasificadas "
                                'termina con al menos un remate.')
        if t['status'] != 'INSUFFICIENT':
            observations.append(f"Tras perderla, en el {t['value']} de los cambios observados "
                                'aparece una acción defensiva registrada dentro de cinco segundos, sin que ello confirme recuperaciones reales.')
        story = ' '.join(observations)
        if a['status'] != 'INSUFFICIENT' and d['status'] != 'INSUFFICIENT':
            conflict = ('¿Cómo se conectan las rutas de inicio con las ocasiones propias y '
                        'en cuáles de los escenarios defensivos se originan los remates rivales?')
        elif a['status'] != 'INSUFFICIENT':
            conflict = '¿Esos inicios se convierten en progresiones y ocasiones en distintos partidos?'
        elif d['status'] != 'INSUFFICIENT':
            conflict = '¿En cuáles de los escenarios defensivos se originan los remates rivales?'
        else:
            conflict = '¿Qué situaciones explican la presencia o ausencia de una acción en los cinco segundos tras pérdida?'
        next_step = ('Abrir las secuencias por partido y situación, contrastar los patrones con vídeo '
                     'y comprobar si la señal persiste antes de utilizarla en una decisión táctica.')
    else:
        story = 'La selección no ofrece cobertura suficiente para construir una lectura táctica fiable.'
        conflict = 'No sería riguroso describir una identidad o una vulnerabilidad con estos datos.'
        next_step = 'Completar o corregir la carga de eventos y volver a ejecutar el análisis.'
    # Lane distribution is the first preferred visual, from the exact same
    # sample as the attacking signal, not a generic or independently filtered view.
    attack_data = result.get('organized_attack_data')
    possessions = (attack_data[1] if isinstance(attack_data, (tuple, list)) and len(attack_data) == 2
                   and isinstance(attack_data[1], pd.DataFrame) else None)
    can_plot_lanes = (a['status'] != 'INSUFFICIENT' and isinstance(possessions, pd.DataFrame)
                      and not possessions.empty and 'lane' in possessions.columns
                      and possessions['lane'].isin(('Izquierda', 'Centro', 'Derecha')).any())
    return {'schema': 'EFOS_EXECUTIVE_BRIEF_0421',
            'title': '¿Cómo juega el equipo y qué debemos mirar?',
            'story': story, 'conflict': conflict, 'next_step': next_step,
            'signals': signals, 'chapters': chapters, 'coverage': count_valid,
            'main_visual': 'lane_origins' if can_plot_lanes else 'none',
            'disclaimer': ('Los momentos responden a preguntas distintas y sus muestras pueden solaparse. '
                           'Eventos ≠ posiciones continuas, intención táctica o causalidad.')}
