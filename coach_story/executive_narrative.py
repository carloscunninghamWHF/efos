"""EFOS v0.4.20 | Executive chapter summaries grounded in existing evidence.

Presentation-only transformation: never alters StatsBomb events or EFOS engine metrics.
Every displayed claim is derived from the same canonical samples used by modules.
"""
from __future__ import annotations

import pandas as pd

from intelligence.defensive_open_play import STATES


def _chapter(section: str, question: str, observation: str, implication: str,
             evidence: str, limitation: str, module: str, status: str = 'EXPLORATORY') -> dict:
    return dict(section=section, question=question, observation=observation,
                implication=implication, evidence=evidence, limitation=limitation,
                module=module, status=status)


def build_executive_chapters(result: dict) -> list[dict]:
    """Three clearly differentiated views (with ball, without ball, loss response).

    No fabricated formations, match dates, event counts, or tactical intentions.
    No numerical outputs unless the corresponding data are present.
    """
    chapters = []
    offensive = result.get('offensive_story') or {}
    n = int(offensive.get('n_possessions') or 0)
    nm = int(offensive.get('n_matches') or 0)
    entry = offensive.get('entry')
    conn = offensive.get('connection')
    prod = offensive.get('productivity') or {}
    if n:
        if entry:
            fact = (f"El corredor {str(entry['lane']).lower()} concentra "
                    f"{entry['count']} de {entry['denominator']} inicios de secuencia "
                    f"con coordenadas identificables ({entry['share']:.0%}).")
        elif conn:
            fact = (f"La conexión más frecuente es {conn['from']} → {conn['to']}, "
                    f"con {conn['completed']} pases completos registrados.")
        else:
            fact = f"Se identificaron {n} secuencias de juego abierto; los corredores de inicio no tienen cobertura suficiente."
        shots = prod.get('shots')
        if shots is not None:
            fact += f" La misma muestra contiene {int(shots)} remates registrados."
        chapters.append(_chapter(
            '01 · CON BALÓN', '¿Por dónde empieza y cómo progresa el ataque?', fact,
            'Revisar las secuencias que conectan el inicio con las ocasiones y comprobar si el patrón persiste por rival.',
            f"{n} secuencias de juego abierto · {nm} partidos · StatsBomb events",
            'Inicio = primera acción registrada; no demuestra estructura posicional ni intención del entrenador.',
            'Ataque Organizado', offensive.get('status', 'EXPLORATORY')))
    else:
        chapters.append(_chapter(
            '01 · CON BALÓN', '¿Por dónde empieza y cómo progresa el ataque?',
            'No existen secuencias de juego abierto evaluables con las columnas disponibles.',
            'Completar o revisar la carga de eventos antes de describir un patrón.',
            'Cobertura de secuencias insuficiente',
            'EFOS no completa secuencias con datos sintéticos.', 'Ataque Organizado', 'INSUFFICIENT'))

    defense = result.get('defensive_open_play_possessions')
    if isinstance(defense, pd.DataFrame) and not defense.empty and {'scenario', 'shot', 'match_id'}.issubset(defense.columns):
        classified = defense[defense.scenario.isin(STATES)]
        n_def = len(classified)
        matches = int(classified.match_id.nunique())
        remaining = len(defense)-n_def
        if n_def:
            shotpos = int(classified.shot.fillna(0).astype(bool).sum())
            fact = (f"En las {n_def} posesiones rivales clasificadas como situaciones de juego abierto, "
                    f"{shotpos} de {n_def} terminaron con al menos un remate ({shotpos/n_def:.1%}).")
            status = 'DESCRIPTIVE' if n_def >= 30 and matches >= 5 else 'SMALL_SAMPLE'
            evidence = f"{n_def} posesiones clasificadas · {matches} partidos · {remaining} sin clasificación en esas tres situaciones"
        else:
            fact = 'Las posesiones rivales observadas no cumplen las reglas de las tres situaciones defensivas.'
            status = 'INSUFFICIENT'
            evidence = f"0 posesiones clasificadas · {remaining} otras de juego abierto"
        chapters.append(_chapter(
            '02 · SIN BALÓN', '¿En qué situaciones llega el rival a rematar?', fact,
            'Contrastar los escenarios de reacción tras pérdida, contraataque y ataque posicional antes de señalar una vulnerabilidad.',
            evidence,
            'Las posesiones clasificadas son un subconjunto; frecuencia de remate no identifica espacios libres ni errores individuales.',
            'Defensa Organizada', status))
    else:
        chapters.append(_chapter(
            '02 · SIN BALÓN', '¿En qué situaciones llega el rival a rematar?',
            'No se dispone de una muestra defensiva clasificada verificable.',
            'Revisar presencia de eventos de ambos equipos y propietarios de posesión.',
            'Datos defensivos no evaluables',
            'No se estiman ubicaciones simultáneas ni marcajes a partir de eventos.',
            'Defensa Organizada', 'INSUFFICIENT'))

    verified = result.get('verified_transitions')
    verified_def=(verified.get('defensive') if isinstance(verified,dict) and verified.get('status')=='ok' else None)
    if isinstance(verified_def,pd.DataFrame) and not verified_def.empty and {'pressures_5s','recovered_5s','match_id'}.issubset(verified_def.columns):
        k=int(pd.to_numeric(verified_def.pressures_5s,errors='coerce').gt(0).sum())
        recovered=int(verified_def.recovered_5s.fillna(False).astype(bool).sum())
        nt=len(verified_def);ng=int(verified_def.match_id.nunique())
        chapters.append(_chapter('03 · TRAS PÉRDIDA','¿Cómo responde tras perderla?',
            f'{k} de {nt} pérdidas candidatas seguidas de posesión rival confirmada presentan Pressure ≤5 s; '
            f'{recovered} casos registran recuperación confirmada ≤5 s.',
            'Contrastar presiones que recuperan, presiones sin recuperación y remates rivales dentro de 15 s.',
            f'{nt} pérdidas verificadas · {ng} partidos',
            'No abarca todas las pérdidas ni demuestra intención colectiva; presión y recuperación son desenlaces distintos.',
            'Cómo defiende','DESCRIPTIVE' if nt>=30 and ng>=3 else 'SMALL_SAMPLE'))
        return chapters
    transitions = result.get('transitions')
    team = result.get('focal_team')
    if (isinstance(transitions, pd.DataFrame) and not transitions.empty and team is not None
        and {'team_lost', 'response_within_5s', 'match_id'}.issubset(transitions.columns)):
        losses = transitions[transitions.team_lost.eq(team)]
        nt = len(losses)
        if nt:
            observed = int(losses.response_within_5s.fillna(False).astype(bool).sum())
            ntmatches = int(losses.match_id.nunique())
            fact = (f"En {observed} de {nt} cambios de posesión identificados tras perder el balón "
                    f"({observed/nt:.1%}), se registró una acción de presión, recuperación o intercepción "
                    f"en los siguientes cinco segundos.")
            status = 'DESCRIPTIVE' if nt >= 20 and ntmatches >= 3 else 'SMALL_SAMPLE'
            evidence = f"{nt} cambios observados · {ntmatches} partidos · ventana EFOS de 5 s"
        else:
            fact = 'No se identificaron cambios de posesión elegibles tras pérdida del equipo.'
            status = 'INSUFFICIENT'; evidence = '0 transiciones defensivas elegibles'
    else:
        fact = 'La muestra no permite identificar cambios de posesión y su respuesta temporal.'
        status = 'INSUFFICIENT'; evidence = 'Datos de transiciones no disponibles'
    chapters.append(_chapter(
        '03 · TRANSICIONES', '¿Qué hace el equipo inmediatamente después de perder el balón?', fact,
        'Examinar las secuencias con y sin respuesta temprana para distinguir contextos de pérdida y recuperación.',
        evidence,
        'Una acción etiquetada en cinco segundos no demuestra recuperación, éxito de presión ni intención colectiva.',
        'Transiciones', status))
    return chapters
