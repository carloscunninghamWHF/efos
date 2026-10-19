"""EFOS · Defensive open play atlas, editorial storytelling UX.

Works with a precomputed result or direct normalized StatsBomb events.
Does not replace the separate defensive set-piece analysis.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from intelligence.defensive_open_play import (STATES, OTHER, MINUTE_BANDS, analyze,
    filter_scenarios, kpis, time_summary, event_detail, DEFENSE_TYPES)
from intelligence.defensive_insights import enrich
from intelligence.defense_scope import opponent_match_scope
from visualization.defensive_insights_app import render_insights, render_insight_summary
from visualization.defensive_open_play_maps import atlas, sequence, defensive_network, timeline, freeze_frame, scenario_pitch


@st.cache_data(show_spinner="Analizando defensa en juego abierto…", max_entries=3)
def _compute(events:pd.DataFrame, team:str):
    return analyze(events, team)


@st.cache_data(show_spinner="Relacionando presión, control y entradas rivales…", max_entries=3)
def _insights(summary, events, team):
    return enrich(summary, events, team)


def _story(s:pd.DataFrame,e:pd.DataFrame,team:str,scenario:str) -> str:
    k=kpis(s)
    n=k['posesiones']; matches=k['partidos']
    label=scenario.lower().replace('defensa ante ','')
    if not n:
        return f'No hay posesiones suficientes ante {label} para describir una respuesta defensiva.'
    opening=(f'**Ante {label}**, {team} enfrentó una muestra '
             f'de **{n} posesiones** distribuidas en **{matches} partidos**. '
             f'El rival remató en **{k["pct_remate"]:.1f}%** de esas posesiones. ')
    eligible=e[(e.team.eq(team)) & (e.event_type.isin(DEFENSE_TYPES))]
    if not eligible.empty and eligible['player'].notna().any():
        leaders=eligible['player'].dropna().value_counts()
        # The label means volume, not player defensive effectiveness.
        opening+=(f'Los jugadores con más intervenciones registradas fueron '
                  f'**{", ".join(str(x) for x in leaders.index[:2])}** '
                  f'(ranking por volumen de eventos, no por éxito individual). ')
    located=s.dropna(subset=['first_contact_x'])
    if not located.empty:
        x=120-float(located['first_contact_x'].median())
        zone=('cerca de la portería que defiende' if x>=80 else
              'tercio intermedio' if x>=40 else 'campo lejano de su portería')
        opening+=(f'La primera intervención defensiva registrada se concentró en el '
                  f'**{zone}** (mediana x={x:.1f} en coordenadas del ataque rival). ')
    if n<30 or matches<5:
        opening+='**Lectura exploratoria:** la muestra no permite afirmar que sea una pauta recurrente del entrenador.'
    else:
        opening+='La regularidad observada describe eventos, no posiciones simultáneas ni un marcaje específico.'
    return opening




def _load(events,team,precomputed):
    if precomputed is not None:
        return precomputed
    try:
        return _compute(events,team)
    except (ValueError, KeyError, TypeError) as exc:
        st.warning(f'Atlas de juego abierto no disponible: {exc}')
        return None,None


def _rival_filters(events,team,all_s,all_e,key_prefix):
    rivales=events.loc[events.team.ne(team), ['match_id', 'team']].dropna() if 'team' in events else pd.DataFrame()
    opponents=sorted(set(rivales.team.astype(str))) if not rivales.empty else []
    op_col, match_col=st.columns([1,1.4])
    with op_col:
        opponent=st.selectbox('Equipo rival', ['Todos los rivales']+opponents, key=f'{key_prefix}_opponent')
    limited, limited_events, mapping=opponent_match_scope(all_s,all_e,team,opponent)
    from intelligence.offensive_story import readable_match_labels
    mids=limited.match_id.astype(str).drop_duplicates().tolist() if not limited.empty else []
    labels=readable_match_labels(events,team,mids)
    with match_col:
        selected_match=st.selectbox('Partido del rival seleccionado', ['Todos los partidos']+mids,
            format_func=lambda m: m if m=='Todos los partidos' else labels.get(m,'Partido sin identificar'),
            key=f'{key_prefix}_match')
    all_s,all_e,_=opponent_match_scope(all_s,all_e,team,opponent,selected_match)
    return all_s,all_e,opponent,selected_match


def _context_filters(all_s,key_prefix):
    other=int(all_s.scenario.eq(OTHER).sum())
    a,b,c=st.columns([1.5,1,1])
    with a:
        scenario=st.selectbox('¿Qué situación enfrenta la defensa?',list(STATES)+([OTHER] if other else []),
                              index=1,key=f'{key_prefix}_situation')
    with b:
        band=st.selectbox('Momento del partido',['Todos']+list(MINUTE_BANDS),
                          key=f'{key_prefix}_time')
    with c:
        state=st.selectbox('Marcador',['Todos','Gana','Empata','Pierde'],
                           key=f'{key_prefix}_score')
    return scenario,band,state,other


def _situation_summary(s,e,team,scenario):
    st.markdown(_story(s,e,team,scenario))
    k=kpis(s)
    cc=st.columns(3)
    cc[0].metric('Posesiones observadas',str(k['posesiones']),f"{k['partidos']} partidos")
    cc[1].metric('Finalizan en remate rival',f"{k['pct_remate']:.1f}%")
    xg=k.get('xg_pos')
    cc[2].metric('xG rival / posesión cubierta',f"{xg:.3f}" if xg is not None else 'Sin dato',
                 f"{k.get('xg_coverage_pct',0):.0f}% de cobertura")
    if k['posesiones']<30 or k['partidos']<5:
        st.caption('Muestra exploratoria: no se infiere una identidad estable a partir de este filtro.')


def _overview_body(contexts,context_events,team,key_prefix,insight_selected,all_e,heading=True):
    """One illustrated defensive scenario at a time, alongside comparable bases."""
    if heading:st.markdown('### ¿Cómo responde la defensa según la situación?')
    st.write('El rival no ataca igual en todas las posesiones. Compara las situaciones y selecciona '
             'una para ver las acciones reales de la defensa y su desenlace.')
    comparison=comparison_table(contexts)
    if len(comparison):
        st.dataframe(comparison[['Situación','Posesiones','Partidos','Con remate (%)']],
                     hide_index=True,use_container_width=True)
    choices=[q for q in STATES if len(contexts[contexts.scenario.eq(q)])]
    if not choices:
        st.info('No hay posesiones clasificadas en este filtro.');return
    scene=st.selectbox('Situación defensiva para interpretar',choices,key=key_prefix+'_scene_choice')
    gs,ge=filter_scenarios(contexts,context_events,scene)
    st.markdown(_story(gs,ge,team,scene))
    primary=ge[(ge.team.eq(team))&ge.event_type.isin(DEFENSE_TYPES)]
    if not primary.empty:
        main=primary.event_type.value_counts()
        st.write(f"**Respuesta observada:** {main.index[0]} fue la intervención más frecuente "
                 f"({int(main.iloc[0])} de {len(primary)} eventos defensivos clasificados). "
                 f"El rival remató en {int(gs.shot.sum())} de {len(gs)} posesiones de esta situación.")
    st.plotly_chart(scenario_pitch(gs,ge,team,scene),use_container_width=True,
                    config={'displaylogo':False},key=f'{key_prefix}_single_scene')
    st.caption('Cómo leer el campo: el sombreado registra zonas de intervención, los puntos la primera acción '
               'defensiva y las flechas las acciones rivales registradas. No muestra una formación simultánea.')
    if len(gs)<30 or gs.match_id.nunique()<5:
        st.caption('Muestra exploratoria. No es una identidad definitiva del entrenador.')
    with st.expander('Profundizar · evidencia por situaciones'):
        render_insights(insight_selected,key_prefix,all_e,team)


def _timeline_body(all_s,all_e,scenario,state,key_prefix):
    temporal_s,_=filter_scenarios(all_s,all_e,scenario,None,state)
    metric=st.selectbox('¿Qué quieres observar a lo largo del partido?',
        ['Posesiones con remate (%)','Presiones por 100 posesiones','xG rival por posesión cubierta'],
        key=f'{key_prefix}_time_metric')
    metric_key={'Posesiones con remate (%)':'pct_remate',
                'Presiones por 100 posesiones':'presiones_100',
                'xG rival por posesión cubierta':'xg_pos'}[metric]
    st.plotly_chart(timeline(temporal_s,metric_key),use_container_width=True,
                    config={'displaylogo':False},key=f'{key_prefix}_timeline_chart')
    st.caption('La línea conserva todos los tramos para dar contexto, aunque el filtro superior seleccione uno. '
               'Agrupa posesiones por su minuto de inicio; no mide cada minuto por separado. '
               'Con varios partidos combina muestras distintas: no representa un único encuentro.')
    explanation={
        'pct_remate':'Una subida indica que una mayor proporción de posesiones acaba en tiro; no identifica por sí sola su calidad.',
        'presiones_100':'Cuenta eventos de presión por cada 100 posesiones. Puede superar 100 porque una posesión admite varias presiones; más presión no implica más eficacia.',
        'xg_pos':'Una subida indica más peligro de remate por posesión con datos completos. Revisa la cobertura antes de comparar.'}
    st.write(explanation[metric_key])
    st.dataframe(time_summary(temporal_s)[['minute_band','posesiones','partidos','xg_coverage_pct']].rename(columns={
        'minute_band':'Tramo','posesiones':'Posesiones','partidos':'Partidos','xg_coverage_pct':'Cobertura xG (%)'}),
        hide_index=True,use_container_width=True)


def _drill(s,e,band,key_prefix):
    available=['Todos']+[b for b in MINUTE_BANDS if b in set(s.minute_band)]
    a,b=st.columns(2)
    drill_band=a.selectbox('Tramo que quieres investigar',available,key=f'{key_prefix}_drill_band')
    ds,de=filter_scenarios(s,e,None,drill_band,None)
    match=b.selectbox('Partido que quieres investigar',['Todos']+sorted(ds.match_id.unique().tolist()),
                      key=f'{key_prefix}_drill_match')
    if match!='Todos':
        ds=ds[ds.match_id.eq(match)]
        de=de[de.match_id.eq(match)]
    st.caption(f'Base común de la red y el selector de jugadas: {len(ds)} posesiones en '
               f'{ds.match_id.nunique()} partidos · tramo superior: {band} · detalle: {drill_band}.')
    return ds,de


def _network_body(de,team,key_prefix):
    st.markdown('#### ¿Quién interviene en estas posesiones?')
    st.plotly_chart(defensive_network(de,team),use_container_width=True,config={'displaylogo':False},
                    key=f'{key_prefix}_def_network')
    st.write('**Círculo mayor:** más intervenciones registradas. **Ubicación:** mediana de los lugares '
             'donde intervino ese jugador, no su posición habitual. **Línea más gruesa:** ambos jugadores '
             'intervinieron en más posesiones compartidas, aunque en momentos diferentes.')
    st.caption('Se muestran hasta 7 jugadores por volumen y hasta 15 conexiones con al menos 2 posesiones compartidas. '
               'Una línea no demuestra cobertura, comunicación o coordinación; su ausencia tampoco demuestra falta de cooperación. '
               'El volumen no está ajustado por minutos disputados.')


def _possession_body(ds,de,team,insight_selected,frames_360,key_prefix):
    if ds.empty:
        st.info('No hay posesiones para este tramo y partido.')
        return
    # Most informative cases first: rival shot, then more registered defensive interventions.
    options=ds.assign(_shot=ds.shot.astype(int)).sort_values(
        ['_shot','n_defensive_actions','match_id','minute'],ascending=[False,False,True,True]).drop(columns='_shot')
    lookup={r.sample_id:r for r in options.itertuples(index=False)}
    picked=st.selectbox('Posesión observada (primero las que acaban en remate rival)',list(lookup),key=f'{key_prefix}_possession',
        format_func=lambda t: (f'Partido {lookup[t].match_id} · {lookup[t].minute:.1f} min · '
                              f'posesión {lookup[t].possession:g} · '
                              + ('con remate' if lookup[t].shot else 'sin remate')))
    if picked is None:
        return
    row=lookup[picked]
    mid,poss=row.match_id,row.possession
    det=event_detail(de,mid,poss)
    xg_text=f'{row.xg:.3f}' if row.xg_complete else 'no disponible'
    st.write(f'**Inicio:** {row.minute:.1f} min · **Marcador al inicio:** {row.match_state} · '
             f'**Duración registrada:** {row.duration_sec:.0f} s · '
             f'**Intervenciones:** {row.n_defensive_actions} · **Tiros rivales:** {row.shots} · **xG:** {xg_text}.')
    insight_row=insight_selected[insight_selected.sample_id.eq(picked)]
    if not insight_row.empty:
        ir=insight_row.iloc[0]
        if ir.control_confirmed:
            st.write(f'**Control posterior confirmado:** {ir.control_player} · {ir.control_zone} · '
                     f'{ir.control_seconds:.1f} s desde la primera contrapresión. '
                     'La acción de control pertenece a la siguiente posesión propia; no al recorrido rival dibujado abajo.')
        if ir.entry_event_id:
            st.write(f'**Primera entrada al último tercio:** {ir.entry_zone}. '
                     + ('Hubo remate posterior en la posesión.' if ir.shot_after_entry else 'Sin remate posterior registrado en la posesión.'))
    st.plotly_chart(sequence(de,team,mid,poss),use_container_width=True,config={'displaylogo':False},
                    key=f'{key_prefix}_possession_chart')
    st.write('Azul continuo = pase rival; azul punteado = conducción rival. '
             'Los números dorados ordenan únicamente las intervenciones defensivas; la cruz roja marca un tiro. '
             'Usa la cronología para comprobar qué acción ocurrió antes y después.')
    st.caption('Esta jugada es un caso observable de la muestra, no prueba que todas las posesiones se desarrollen igual. '
               'No conceder un tiro no demuestra recuperación ni éxito defensivo por sí solo.')
    with st.expander('Ver cronología completa de esta posesión'):
        cols=['minute','second','team','event_type','player','location_x','location_y']
        st.dataframe(det[[t for t in cols if t in det]].rename(columns={
            'minute':'Minuto','second':'Segundo','team':'Equipo','event_type':'Acción',
            'player':'Jugador','location_x':'X','location_y':'Y'}),hide_index=True,use_container_width=True)
    if frames_360 and 'event_id' in det:
        mapped=det[det.event_id.astype(str).isin(frames_360)]
        if not mapped.empty:
            row_index=st.selectbox('Instantánea 360 observada',mapped.index.tolist(),
                format_func=lambda i:f'{mapped.loc[i,"event_type"]} · {mapped.loc[i,"event_id"]}',
                key=f'{key_prefix}_360index')
            r=mapped.loc[row_index]
            st.plotly_chart(freeze_frame(frames_360[str(r.event_id)],
                actor_is_america=(r.team==team),team_name=team),use_container_width=True,
                key=f'{key_prefix}_360_chart')
            st.caption('Solo jugadores visibles en ese fotograma; no es tracking continuo.')
        else:
            st.info('No hay instantánea 360 vinculada a esta posesión.')
    else:
        st.caption('Sin datos 360 vinculados: no se muestran posiciones simultáneas.')


def _evidence_table(s):
    with st.expander('Evidencia verificable · cada posesión rival'):
        cols=['match_id','possession','scenario','minute','minute_band','match_state',
              'n_defensive_actions','n_pressures','shot','xg','xg_complete','first_contact_player','first_contact_type']
        st.dataframe(s[[col for col in cols if col in s]],hide_index=True,use_container_width=True)


def render_defensive_module(events:pd.DataFrame,team:str,frames_360:dict|None=None,
                            key_prefix:str='open_play',precomputed:tuple|None=None):
    """Compact open-play story + atlas with evidence/drill downs, fully separated from ABP."""
    all_s,all_e=_load(events,team,precomputed)
    if not isinstance(all_s,pd.DataFrame) or all_s.empty:
        st.info('No hay posesiones rivales de juego abierto suficientes para este atlas.')
        return
    st.markdown('### ¿Cómo atacan los rivales al equipo seleccionado?')
    st.write('Selecciona primero al rival y después uno de sus partidos. La situación defensiva, '
             'los porcentajes y todas las canchas se calcularán exclusivamente con esa misma muestra.')
    all_s,all_e,_,_=_rival_filters(events,team,all_s,all_e,key_prefix)
    if all_s.empty:
        st.info('No hay posesiones rivales clasificadas para esta combinación. Selecciona otra muestra.')
        return
    insight_all=_insights(all_s,events,team)
    s_main=all_s[all_s.scenario.isin(STATES)]
    other=int(all_s.scenario.eq(OTHER).sum())
    st.caption(f'Muestra activa: {int(all_s.match_id.nunique())} partidos · '
               f'{len(s_main)} posesiones en tres escenarios · {other} situaciones sin clasificar. '
               'Balón parado se analiza por separado.')
    scenario,band,state,_=_context_filters(all_s,key_prefix)
    contexts,context_events=filter_scenarios(s_main,all_e,None,band,state)
    s,e=filter_scenarios(all_s,all_e,scenario,band,state)
    if s.empty:
        st.info('No hay posesiones registradas para este escenario y contexto.')
        return
    insight_selected=insight_all[insight_all.sample_id.isin(set(s.sample_id))]
    from visualization.tactical_context_ui import render_context
    render_context('defense')
    st.markdown('### Lo que revela la situación defensiva seleccionada')
    _situation_summary(s,e,team,scenario)
    overview, investigation, integral = st.tabs([
        '1 · Situaciones y respuesta defensiva', '2 · Cómo progresa el rival y quién interviene',
        '3 · Análisis integral'])
    with overview:
        _overview_body(contexts,context_events,team,key_prefix,insight_selected,all_e)
    with investigation:
        st.markdown('### ¿Cómo llegan los rivales y cómo responde la defensa?')
        st.write(f'**Situación: {scenario} · marcador: {state}.** '
                 'Primero compara los tramos del partido; después elige un tramo y un partido para '
                 'ver sus participantes y contrastar una jugada concreta.')
        _timeline_body(all_s,all_e,scenario,state,key_prefix)
        ds,de=_drill(s,e,band,key_prefix)
        _network_body(de,team,key_prefix)
        st.markdown('#### ¿Cómo se ve eso en una posesión concreta?')
        _possession_body(ds,de,team,insight_selected,frames_360,key_prefix)
    with integral:
        render_integral(contexts,context_events,s,e,team,scenario,band,state,insight_selected)
    _evidence_table(s)
    st.caption('EFOS · Lectura defensiva integrada v0.4.16 · Heurísticas descriptivas de juego abierto.')


# ---------------------------------------------------------------------------
# v0.4.25 — «Cómo defiende» por preguntas (one button per football question)
# ---------------------------------------------------------------------------
DEFENSE_QUESTIONS=[
    ('perdida','01','Tras la pérdida','¿Qué hace al perder el balón?','reaccion_tras_perdida'),
    ('situaciones','02','Situaciones rivales','¿Cómo le atacan y cuándo le rematan?','situaciones_de_amenaza'),
    ('momentos','03','Momentos y protagonistas','¿Cuándo sufre y quién interviene?',None),
    ('jugada','04','Jugada a jugada','¿Cómo se ve en una posesión concreta?',None),
    ('conclusiones','05','Para el cuerpo técnico','¿Qué debe revisar y entrenar?',None),
]


def render_defense_questions(events:pd.DataFrame,team:str,result:dict|None=None,
                             frames_360:dict|None=None,precomputed:tuple|None=None,
                             key_prefix:str='open_play'):
    from visualization.question_nav import question_nav, question_header, question_pager, question_answer
    st.markdown('## Cómo defiende · de la pérdida al remate rival')
    st.caption('Cinco preguntas futbolísticas. Toca una para ver su respuesta, sus mapas y su evidencia.')
    # The team base is the selected EFOS identity. Switching perspective inside a
    # submodule would break all cross-phase comparisons; change team in Data.
    base=team
    with st.expander('Profundizar · situación, tramo y marcador',expanded=False):
        st.caption('Equipo base: '+str(team)+'. Para cambiarlo, vuelve a «Equipo y datos».')
        all_s,all_e=_load(events,base,precomputed if base==team else None)
        ready=isinstance(all_s,pd.DataFrame) and not all_s.empty
        if ready:
            all_s,all_e,opponent,match=_rival_filters(events,base,all_s,all_e,key_prefix)
            ready=not all_s.empty
        if ready:
            scenario,band,state,other=_context_filters(all_s,key_prefix)
        st.caption('Rival y partido afectan a las preguntas 02 a 05. La situación, el tramo y el marcador '
                   'afectan a las preguntas 03 a 05. La pregunta 01 usa todos los partidos del equipo base.')
    s=e=contexts=context_events=insight_selected=None
    if ready:
        s_main=all_s[all_s.scenario.isin(STATES)]
        contexts,context_events=filter_scenarios(s_main,all_e,None,band,state)
        s,e=filter_scenarios(all_s,all_e,scenario,band,state)
        insight_all=_insights(all_s,events,base)
        insight_selected=insight_all[insight_all.sample_id.isin(set(s.sample_id))]
        st.caption(f'Muestra activa: {base} · {int(all_s.match_id.nunique())} partidos · '
                   f'{len(s_main)} posesiones rivales en tres escenarios · {other} sin clasificar · '
                   f'situación filtrada: {scenario} · tramo: {band} · marcador: {state}. Balón parado se analiza por separado.')
    else:
        st.caption('No hay posesiones rivales de juego abierto clasificadas para esta muestra; '
                   'sólo está disponible la pregunta 01.')

    with st.container(key="efos_sticky_questions_defense"):
        qid=question_nav(DEFENSE_QUESTIONS,key_prefix)
    question_header(DEFENSE_QUESTIONS,qid)
    question_answer(DEFENSE_QUESTIONS,qid,result if base==team else None,key_prefix)
    if qid=='perdida':
        from visualization.transition_story_app import render_transition_chapter
        render_transition_chapter(events,base,'defensive',frames_360=frames_360,key_prefix='def_transition')
    elif not ready:
        st.info('No hay posesiones rivales clasificadas para esta combinación. Selecciona otra muestra en «Muestra y filtros».')
    elif qid=='situaciones':
        if result is not None and base==team:
            from visualization.reasoning_ui import render_defense_chart
            render_defense_chart(result,key_prefix+'_def_chart')
        from visualization.tactical_context_ui import render_context
        render_context('defense')
        _overview_body(contexts,context_events,base,key_prefix,insight_selected,all_e,heading=False)
    elif s.empty:
        st.info('No hay posesiones registradas para esta situación, tramo y marcador. Cambia la situación en «Muestra y filtros».')
    elif qid=='momentos':
        st.markdown(f'### Situación filtrada: {scenario}')
        _situation_summary(s,e,base,scenario)
        st.markdown('#### ¿En qué tramo del partido sufre más?')
        _timeline_body(all_s,all_e,scenario,state,key_prefix)
        ds,de=_drill(s,e,band,key_prefix)
        _network_body(de,base,key_prefix)
    elif qid=='jugada':
        st.write(f'**Situación: {scenario} · marcador: {state}.** Elige un tramo, un partido y una posesión '
                 'real para revisar la respuesta defensiva acción por acción.')
        ds,de=_drill(s,e,band,key_prefix)
        _possession_body(ds,de,base,insight_selected,frames_360,key_prefix)
    elif qid=='conclusiones':
        render_integral(contexts,context_events,s,e,base,scenario,band,state,insight_selected)
    question_pager(DEFENSE_QUESTIONS,qid,key_prefix)
    st.divider()
    if ready and s is not None:
        with st.expander('Ver eventos fuente de la muestra · para analistas'):
            _evidence_table(s)


def comparison_table(summary):
    rows=[]
    for scenario in STATES:
        k=kpis(summary[summary.scenario.eq(scenario)])
        rows.append({'Situación':scenario,'Posesiones':k['posesiones'],'Partidos':k['partidos'],
                     'Con remate (%)':round(k['pct_remate'],1) if k['posesiones'] else None,
                     'Presiones / 100 posesiones':round(k['presiones_100'],1) if k['posesiones'] else None,
                     'xG / posesión cubierta':k['xg_pos'],'Cobertura xG (%)':k['xg_coverage_pct']})
    return pd.DataFrame(rows)


def render_integral(contexts,context_events,s,e,team,scenario,band,state,insights=None):
    st.markdown('### Informe de situaciones · acciones y desenlace')
    st.caption(f'Filtros de esta síntesis: {scenario} · tramo {band} · marcador {state}. '
               'Los filtros de exploración de una jugada no alteran este resumen. '
               'Balón parado queda excluido. La tabla compara las tres situaciones clasificadas; '
               '«Otro juego abierto» se puede seleccionar para estudiar los casos restantes.')
    st.markdown('#### 1. Qué ocurrió y con qué frecuencia')
    st.markdown(_story(s,e,team,scenario))
    st.dataframe(comparison_table(contexts),hide_index=True,use_container_width=True)
    st.write('La tabla compara las tres situaciones bajo el mismo tramo y marcador. '
             'Un porcentaje con remate mayor señala una exposición observada mayor, '
             'pero no demuestra peor defensa: cambian el rival, la muestra y las condiciones de cada posesión.')
    st.markdown('#### 2. Cuándo y con quién aparece')
    t=time_summary(s)
    observed=t[t.posesiones.gt(0)]
    if not observed.empty:
        peak=observed.sort_values(['pct_remate','posesiones'],ascending=False).iloc[0]
        st.write(f'El tramo con mayor proporción de posesiones con remate dentro del filtro es '
                 f'**{peak.minute_band}**: **{int(peak.remates)} de {int(peak.posesiones)} posesiones '
                 f'({peak.pct_remate:.1f}%)**, en {int(peak.partidos)} partidos. '
                 + ('Solo hay un tramo disponible; no permite comparar la evolución. '
                    if len(observed)==1 else '')
                 + 'Es una prioridad para revisar, no evidencia de fatiga o de un efecto de los cambios.')
    from itertools import combinations
    from collections import Counter
    actions=e[e.team.eq(team)&e.event_type.isin(DEFENSE_TYPES)&e.player.notna()&e.player.ne('')]
    pairs=Counter()
    for _,g in actions.groupby(['match_id','possession']):
        pairs.update(combinations(sorted(set(g.player)),2))
    if pairs:
        pair,count=pairs.most_common(1)[0]
        st.write(f'**{pair[0]} y {pair[1]}** aparecen juntos en **{count} de las {len(s)} posesiones** '
                 'del filtro. Esto identifica casos donde revisar intervenciones encadenadas; '
                 'no confirma que uno cubriera al otro.')
    else:
        st.write('No hay pares de jugadores con intervenciones registradas en una misma posesión dentro del filtro.')
    if insights is not None:
        from visualization.defensive_storytelling import priorities
        priorities(insights,e,team,'integral_story')
    st.markdown('#### 3. Qué contrastar en las jugadas')
    questions={
        STATES[0]:'¿La primera intervención dificulta el avance rival o el rival la supera y continúa hacia portería?',
        STATES[1]:'¿Dónde aparece la primera oposición y qué ruta utiliza el rival para llegar al remate?',
        STATES[2]:'¿Las rutas rivales más frecuentes coinciden con zonas donde se registran pocas intervenciones?'}
    st.write(questions.get(scenario,'¿Qué secuencia de intervenciones y avances aparece en estas posesiones que no encajan en las tres categorías principales?'))
    st.write('En la pestaña de exploración, revisa una posesión con remate y otra sin remate '
             'del mismo tramo y partido, si existen. Contrasta la secuencia de eventos y, si hay vídeo o 360, '
             'comprueba las posiciones que los eventos por sí solos no muestran.')
    st.markdown('#### 4. Qué puede llevar el cuerpo técnico al entrenamiento')
    st.write('Usa las secuencias revisadas para elegir una situación de entrenamiento: '
             'reproduce el origen del ataque rival y observa la primera intervención y la siguiente ayuda. '
             'La tarea es una propuesta para validar con el entrenador; estos datos no prescriben una formación ni un marcaje.')
    st.markdown('#### 5. Qué falta para sostener una conclusión')
    k=kpis(s)
    st.write(f'La síntesis se apoya en **{k["posesiones"]} posesiones y {k["partidos"]} partidos**, '
             f'con **{k["xg_coverage_pct"]:.1f}% de cobertura de xG**. '
             'Las posesiones sin xG completo se excluyen del promedio de peligro, no del porcentaje con remate. '
             'Para atribuir una mejora a una decisión técnica hacen falta muestras comparables, contexto del rival '
             'y contraste con vídeo o posiciones observadas.')
