"""EFOS | Diagnóstico táctico conectado, v0.4.24.

Presentation/decision-support layer built from precomputed StatsBomb evidence.
Never edits underlying events, ESI, CTS or possession rules. Concepts structure the
questions; only observed actions and explicit denominators establish claims.
The user-facing payload deliberately contains no external conceptual bibliography.
"""
from __future__ import annotations

import pandas as pd
from interpretation.claim_contract import build_reasoning_claim
from intelligence.defensive_open_play import STATES


def _frame(data):
    return data if isinstance(data, pd.DataFrame) else pd.DataFrame()


def _int(value):
    try:
        return int(value) if pd.notna(value) else 0
    except (ValueError, TypeError):
        return 0


def _pct(num, den):
    return f'{100*num/den:.1f}%' if den else '—'


def _status(n, games):
    if n < 1 or games < 1:
        return 'INSUFFICIENT'
    if n < 30 or games < 3:
        return 'EXPLORATORIO'
    return 'DESCRIPTIVO'


def _finding(*, ident, module, question, observation, context, interpretation,
             alternative, action, limitation, evidence, scope, status, cases=None):
    """All strings are user-facing; evidence must cite OBSERVATIONS, not articles."""
    return dict(id=ident, module=module, question=question, observation=observation,
                context=context, interpretation=interpretation, alternative=alternative,
                action=action, limitation=limitation, evidence=evidence,
                scope=scope, status=status, cases=(cases or [])[:12])


def _attack(result):
    data = result.get('organized_attack_data')
    if not isinstance(data, (tuple, list)) or len(data) != 2:
        return [], pd.DataFrame()
    possessions = _frame(data[1])
    if possessions.empty or not {'match_id','lane','shots','box_entries'}.issubset(possessions.columns):
        return [], pd.DataFrame()
    t = possessions.copy()
    valid = t[t.lane.isin(['Izquierda', 'Centro', 'Derecha'])]
    matches = _int(t.match_id.nunique())
    findings = []
    chart = pd.DataFrame()
    if len(valid):
        # Origin = first observed ball action, not first entry into final third.
        chart = valid.groupby('lane', sort=False).agg(
            posesiones=('match_id','size'), con_remate=('shots', lambda s: _int(pd.to_numeric(s,errors='coerce').gt(0).sum())),
            con_entrada_al_area=('box_entries', lambda s: _int(pd.to_numeric(s, errors='coerce').gt(0).sum())),
            partidos=('match_id','nunique')).reset_index()
        chart['tasa_remate_pct'] = (chart['con_remate']/chart['posesiones']*100).round(1)
        chart['porcentaje_inicios'] = (chart['posesiones']/len(valid)*100).round(1)
        chart = chart.sort_values('posesiones', ascending=False).reset_index(drop=True)
        main = chart.iloc[0]
        lane = str(main.lane)
        k, den = _int(main.posesiones), len(valid)
        rate = _pct(k,den)
        nshot = _int(main.con_remate)
        scope = f'{den} secuencias con origen conocido en {matches} partidos; {len(t)-den} sin corredor identificable'
        # Keep comparisons descriptive; small per-lane counts do not justify a ranking of quality.
        if (chart.posesiones >= 20).sum() >= 2 and matches >= 3:
            quality = chart.loc[chart.posesiones>=20].sort_values('tasa_remate_pct',ascending=False).iloc[0]
            if str(quality.lane) != lane:
                implication = (f'El corredor de inicio más frecuente ({lane.lower()}) no coincide con el que presenta '
                               f'la mayor proporción de secuencias con remate entre corredores con ≥20 casos '
                               f'({str(quality.lane).lower()}, {_pct(_int(quality.con_remate),_int(quality.posesiones))}).')
            else:
                implication = (f'El corredor {lane.lower()} reúne el mayor volumen de inicios y la mayor '
                               'proporción de posesiones con remate entre corredores con ≥20 casos.')
        else:
            implication = 'No hay suficiente cobertura comparable por corredor para afirmar cuál es más productivo.'
        cases = [str(x) for x in valid.loc[valid.lane.eq(lane),'key'].head(12)] if 'key' in valid else []
        findings.append(_finding(
            ident='origen_y_productividad', module='Cómo ataca',
            question='¿Desde dónde empieza y qué produce después?',
            observation=(f'{k} de {den} secuencias comienzan con su primera acción registrada en el '
                         f'corredor {lane.lower()} ({rate}); {nshot} de esas {k} secuencias incluyen remate.'),
            context='El origen corresponde a la primera acción con coordenadas, no a una entrada al último tercio.',
            interpretation=implication,
            alternative='La distribución también depende del rival, del estado del partido y de las posesiones no observadas por completo.',
            action='Contrastar una secuencia con remate y otra sin remate del mismo corredor; después comparar rivales.',
            limitation='No identifica una formación, rutas sin balón ni la causa del remate.',
            evidence={'observed':k,'denominator':den,'outcome':nshot,'matches':matches,
                      'metric':'Primera acción registrada por corredor; remate en la misma posesión'},
            scope=scope,status=_status(den,matches),cases=cases))
    # Second complementary question: entry into area and continuation.
    entries = t[pd.to_numeric(t.box_entries,errors='coerce').gt(0)]
    shots = t[pd.to_numeric(t.shots,errors='coerce').gt(0)]
    if len(t):
        both = _int(pd.to_numeric(entries.shots,errors='coerce').gt(0).sum())
        only = len(entries)-both
        findings.append(_finding(
            ident='llegada_y_des_enlace', module='Cómo ataca',
            question='¿Qué sucede después de llegar al área?',
            observation=(f'{len(entries)} de {len(t)} posesiones contienen una entrada al área mediante pase '
                         f'o conducción; {both} de esas {len(entries)} también contienen un remate. '
                         f'En la muestra completa hay {len(shots)} posesiones con remate.'),
            context='Las llegadas se cuentan por posesión, no por la cantidad de veces que un jugador ingresa.',
            interpretation=(f'{only} posesiones con entrada al área no contienen remate registrado. '
                            'Son casos concretos para revisar la continuidad ofensiva.'),
            alternative='Un remate puede producirse antes de la entrada registrada; compartir posesión no demuestra que la entrada causara el tiro.',
            action='Revisar dos posesiones con entrada y sin remate para detectar dónde termina la continuación observada.',
            limitation='No hay atribución causal de xG al pase de entrada ni se inventan desmarques.',
            evidence={'observed':len(entries),'denominator':len(t),'outcome':both,'matches':matches,
                      'metric':'Entrada al área y remate en la misma posesión'},
            scope=f'{len(t)} posesiones de juego abierto; {matches} partidos',
            status=_status(len(t),matches),
            cases=[str(x) for x in entries.loc[pd.to_numeric(entries.shots,errors='coerce').eq(0),'key'].head(12)] if 'key' in t else []))
    # Relational mechanism from observed passes: a frequent link is evidence of
    # interaction, never evidence of unobserved support runs or coaching intent.
    connection=(result.get('offensive_story') or {}).get('connection')
    if isinstance(connection,dict) and connection.get('completed') and connection.get('attempts'):
        k=_int(connection['completed']);den=_int(connection['attempts']);games=_int(connection.get('matches'))
        if den>=k>0 and games:
            pair=f"{connection.get('from','Pasador')} → {connection.get('to','Receptor')}"
            findings.append(_finding(
                ident='conexiones_principales',module='Cómo ataca',
                question='¿Quiénes sostienen las principales conexiones?',
                observation=(f'{pair} registra {k} pases completos de {den} registros del vínculo con destinatario '
                             f'identificado en {games} partidos; no es una tasa de acierto general.'),
                context='La conexión se elige por cantidad de pases completos; algunos pases errados carecen de destinatario y no integran este denominador.',
                interpretation='Es una relación frecuente que merece revisión junto a sus rutas de progresión y desenlaces.',
                alternative='La frecuencia puede reflejar minutos compartidos, posición, iniciativa rival o circulación lateral.',
                action='Comparar las posesiones en que esta conexión precede una progresión con aquellas que no avanzan.',
                limitation='No mide coordinación psicológica, rendimiento relativo por 90 o juego sin balón.',
                evidence={'observed':k,'denominator':den,'outcome':None,'matches':games,
                          'metric':'Pases completados / intentos registrados entre el mismo par'},
                scope=f'{den} pases del vínculo, {games} partidos',status=_status(den,games)))
    return findings, chart


def _defense(result):
    d=_frame(result.get('defensive_open_play_possessions'))
    need={'match_id','scenario','shot'}
    if d.empty or not need.issubset(d.columns):
        return [],pd.DataFrame()
    g=d[d.scenario.isin(STATES)].copy()
    if g.empty:
        return [],pd.DataFrame()
    g['_has_shot']=g.shot.fillna(0).astype(bool)
    table=g.groupby('scenario', sort=False).agg(posesiones=('match_id','size'),
        con_remate=('_has_shot','sum'),partidos=('match_id','nunique')).reset_index()
    table['tasa_remate_pct']=(100*table.con_remate/table.posesiones).round(1)
    valid=table[(table.posesiones>=20)&(table.partidos>=3)].sort_values('tasa_remate_pct',ascending=False)
    n=len(g); shots=_int(g._has_shot.sum()); games=_int(g.match_id.nunique())
    if valid.empty:
        interpretation='La muestra por situación es demasiado pequeña para comparar tasas entre escenarios.'
    else:
        lead=valid.iloc[0]
        interpretation=(f'Entre los escenarios con al menos 20 posesiones en 3 partidos, «{lead.scenario}» registra '
                        f'{_int(lead.con_remate)} de {_int(lead.posesiones)} posesiones con remate '
                        f'({_pct(_int(lead.con_remate),_int(lead.posesiones))}). '
                        'Conviene revisar si esta diferencia se mantiene partido por partido.')
    f=_finding(
        ident='situaciones_de_amenaza',module='Cómo defiende',
        question='¿En qué situaciones consigue rematar el rival?',
        observation=(f'{shots} de {n} posesiones rivales de juego abierto clasificadas contienen remate '
                     f'({_pct(shots,n)}) en {games} partidos.'),
        context=f'Se comparan exclusivamente las tres situaciones definidas por EFOS; {len(d)-n} posesiones quedan fuera de estas categorías.',
        interpretation=interpretation,
        alternative='Una mayor frecuencia de remate puede reflejar mayor calidad del rival, contexto de marcador o selección de posesiones.',
        action='Abrir las posesiones con remate del escenario de mayor frecuencia y compararlas con casos sin remate.',
        limitation='La tasa no identifica por sí sola una zona vulnerable, altura de línea ni error individual.',
        evidence={'observed':shots,'denominator':n,'outcome':shots,'matches':games,
                  'metric':'Posesión rival clasificada con al menos un remate'},
        scope=f'{n} posesiones rivales clasificadas · {games} partidos', status=_status(n,games))
    return [f],table


def _transitions(result):
    """Use the verified possession-change engine wherever complete events exist."""
    checked=result.get('verified_transitions')
    if isinstance(checked,dict) and checked.get('status')=='ok':
        v=_frame(checked.get('defensive'))
        if v.empty:
            return []
        fields={'pressures_5s','recovered_5s','rival_shots_15s','match_id'}
        if not fields.issubset(v.columns):
            return []
        n=len(v);k=_int(pd.to_numeric(v.pressures_5s,errors='coerce').gt(0).sum())
        regain=_int(v.recovered_5s.fillna(False).astype(bool).sum())
        danger=_int(pd.to_numeric(v.rival_shots_15s,errors='coerce').gt(0).sum())
        games=_int(v.match_id.nunique())
        return [_finding(
            ident='reaccion_tras_perdida',module='Cómo defiende',
            question='¿Qué hace el equipo inmediatamente después de perderla?',
            observation=(f'En {k} de {n} pérdidas seguidas por una posesión rival confirmada ({_pct(k,n)}) '
                         f'se registra presión propia antes de 5 s. Se recupera en 5 s en {regain} casos '
                         f'y el rival remata antes de 15 s en {danger}.'),
            context='Los casos se anclan en una acción de pérdida candidata seguida de una posesión rival confirmada; no son todas las pérdidas posibles.',
            interpretation='La presión temprana, las recuperaciones y los remates rivales representan desenlaces distintos; deben compararse por partido.',
            alternative='Una defensa puede replegarse sin evento Pressure, y un evento Pressure no confirma un intento coordinado.',
            action='Comparar recuperaciones rápidas, presiones sin recuperación y pérdidas seguidas de remate rival.',
            limitation='Presión registrada no equivale a éxito ni a forma defensiva simultánea; ventanas de 5 y 15 s.',
            evidence={'observed':k,'denominator':n,'outcome':regain,'rival_shot_cases':danger,
                      'matches':games,'metric':'Presión ≤5 s tras posesión rival verificada; recuperación ≤5 s y remate rival ≤15 s'},
            scope=f'{n} pérdidas verificadas · {games} partidos',status=_status(n,games),
            cases=v.event_id.astype(str).head(12).tolist() if 'event_id' in v else [] )]
    # Legacy compatibility when clients send summary-only input without event data.
    t=_frame(result.get('transitions'))
    team=result.get('focal_team')
    if not team or t.empty or not {'team_lost','response_within_5s','match_id'}.issubset(t.columns):
        return []
    v=t[t.team_lost.eq(team)]
    if v.empty:
        return []
    n=len(v); k=_int(v.response_within_5s.fillna(False).astype(bool).sum()); games=_int(v.match_id.nunique())
    return [_finding(
        ident='reaccion_tras_perdida',module='Cómo defiende',
        question='¿Qué hace el equipo inmediatamente después de perderla?',
        observation=(f'En {k} de {n} cambios elegibles ({_pct(k,n)}) aparece presión, recuperación '
                     'o intercepción registrada en cinco segundos.'),
        context='Estimación del motor histórico: solo cambios de posesión elegibles, no pérdidas verificadas por el motor actual.',
        interpretation='Es una señal temporal preliminar para investigar y no es comparable directamente con el capítulo de transiciones.',
        alternative='La ausencia de etiqueta no demuestra falta de reacción defensiva.',
        action='Cargar los eventos completos para contrastar cambios verificables y desenlaces.',
        limitation='Esta lectura provisional no se utiliza cuando existe el motor verificado de transiciones.',
        evidence={'observed':k,'denominator':n,'outcome':None,'matches':games,
                  'metric':'Acción defensiva etiquetada ≤5 s en motor histórico'},
        scope=f'{n} cambios elegibles · {games} partidos', status=_status(n,games))]


def build_tactical_reasoning(result: dict) -> dict:
    """Compute connected observations using existing canonical engine outputs.

    Readers can audit each denominator and scope; reasoning never changes data.
    Neither theoretical sources nor bibliography are emitted in this display API.
    """
    attacking, lanes = _attack(result)
    defending, scenarios = _defense(result)
    responding = _transitions(result)
    findings = attacking + defending + responding
    usable = [f for f in findings if f['status']!='INSUFFICIENT']
    if not usable:
        identity='No hay muestra suficiente para diagnosticar el comportamiento táctico del equipo.'
        priority='Completar la carga de eventos y verificar la muestra de partidos, posesiones y desenlaces.'
    else:
        # Synthesis linked across phases without pretending denominators are additive.
        identity=' '.join(f['observation'] for f in (attacking[:1]+defending[:1]+responding[:1]))
        if len(attacking) and len(defending):
            priority=('Comparar los corredores ofensivos que terminan con remate y las situaciones '
                      'defensivas en que remata el rival, sin sumar sus muestras independientes.')
        elif attacking:
            priority='Relacionar los corredores de origen con los desenlaces por rival y partido.'
        else:
            priority='Contrastar los escenarios defensivos con ejemplos de posesiones observadas.'
    claims = [build_reasoning_claim(result, f) for f in findings]
    return {'schema':'EFOS_REASONING_0424','identity':identity,'priority':priority,
            'claims_v1':claims,
            'findings':findings,'coverage':len(usable),
            'lane_table':lanes,'defense_table':scenarios,
            'rule':'Observación → contexto → patrón → interpretación → alternativa → pregunta táctica.',
            'disclaimer':'Las muestras de ataque, defensa y pérdidas tienen definiciones y denominadores distintos. '
                         'Las conclusiones no demuestran intencionalidad táctica, movimiento sin balón ni causalidad.'}
