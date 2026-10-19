"""EFOS v0.4.25 — Ataque: one button per football question (answer, maps, evidence).

All existing analytic figures and raw events remain available in a secondary
research layer. No synthetic movement, no tactic inferred from average nodes.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from intelligence import organized_attack as A
from intelligence.offensive_story import build_offensive_story, readable_match_labels
from visualization import efos_smart_attack_graphs as G
from visualization import attack_story_figures as V
from knowledge.tactical_context import context_for


@st.cache_data(show_spinner=False, max_entries=5)
def analyze(events:pd.DataFrame, team:str):
    d=A.prepare_attack(events,team)
    return d,A.possession_table(d)


def _chart(fig,key):
    st.plotly_chart(fig,use_container_width=True,key=key,config={"displaylogo":False,"toImageButtonOptions":{"format":"png","scale":2}})


def _integer(v):
    return f'{int(v):,}'


def _select_scope(events,team,d,t,key):
    """One compact context control, no 38 visible tags or raw numeric match IDs."""
    matchids=t.match_id.drop_duplicates().astype(str).tolist()
    labels=readable_match_labels(events,team,matchids)
    selected=matchids
    with st.expander('Muestra y filtros · personalizar el análisis',expanded=False):
        mode=st.radio('Partidos',['Temporada completa','Un partido','Comparar partidos'],horizontal=True,key=key+'_mode')
        if mode=='Un partido':
            mid=st.selectbox('Partido y rival',matchids,format_func=lambda x:labels[x],key=key+'_single')
            selected=[mid]
        elif mode=='Comparar partidos':
            chosen=st.multiselect('Seleccionar partidos',matchids,format_func=lambda x:labels[x],key=key+'_compare')
            if chosen:selected=chosen
            else:st.caption('Sin partidos marcados: permanece la muestra completa.')
        phases=['Todo el juego abierto','Posesión controlada etiquetada']
        phases += [x for x in sorted(t.phase.dropna().unique()) if x not in phases]
        phases=[x for x in phases if x=='Todo el juego abierto' or x in set(t.phase)]
        phase=st.selectbox('Tipo de posesión',phases,key=key+'_phase')
        a,b=st.columns(2)
        players=sorted(set(d.player.dropna().astype(str))|set(d.pass_recipient_name.dropna().astype(str)))
        player=a.selectbox('Perspectiva',['Colectivo']+players,key=key+'_player')
        states=['Todos']+[str(v) for v in t.score_state.dropna().unique() if str(v).lower() not in ('nan','sin marcador')]
        state=b.selectbox('Situación del marcador',states,key=key+'_score') if len(states)>1 else 'Todos'
        if t.minute.notna().any():
            hi=max(1,int(t.minute.max())+1)
            minutes=st.slider('Minuto en que inicia la secuencia',0,hi,(0,hi),key=key+'_minute')
        else:minutes=None
        st.caption('Filtros aplicados a secuencias completas; la perspectiva individual incluye las jugadas en las que participa el jugador.')
    # When the expander is collapsed, Streamlit still executes its contents.
    return selected,phase,player,minutes,state,labels


def _insight_cards(story):
    s=story
    fields=[
        ('Dónde comienza',f"{s['entry']['lane']} · {s['entry']['share']:.0%} de inicios válidos" if s.get('entry') else 'Origen no identificable'),
        ('Quién conecta',f"{s['connection']['from']} → {s['connection']['to']}" if s.get('connection') else 'Conexión no verificable'),
        ('Qué genera',f"{s['productivity']['shots']} remates en {s['n_possessions']} secuencias" if s.get('productivity') else 'Sin desenlace evaluable')]
    cols=st.columns(3)
    for col,(title,value) in zip(cols,fields):
        with col:
            with st.container(border=True):
                st.caption(title.upper())
                st.markdown(f'**{value}**')


def _representatives(t:pd.DataFrame,limit:int=12):
    """Choose observed clips with clear outcomes, never fabricated averages."""
    usable=t[t.actions.ge(3)].copy()
    if usable.empty:return t.head(1)
    usable['_has_shot']=usable.shots.gt(0).astype(int)
    usable['_entered']=usable.box_entries.gt(0).astype(int)
    return usable.sort_values(['_has_shot','_entered','actions','match_id'],ascending=[False,False,False,True]).head(limit)


def _sequence_label(r,labels):
    m=labels.get(str(r.match_id),'Partido sin rival identificado')
    minute=f'{float(r.minute):.0f}′' if pd.notna(r.minute) else 'minuto no disponible'
    return f"{m} · {minute} · {r.outcome}"


# v0.4.25 — question navigation. Each button opens one football question with its
# answer, maps and content; the analytic content of every section is unchanged.
QUESTIONS=[
    ('transicion','01','Defensa → ataque','¿Qué hace al recuperar el balón?',None),
    ('construccion','02','Origen y construcción','¿Cómo construye sus posesiones?','origen_y_productividad'),
    ('conexiones','03','Conexiones','¿Quiénes sostienen su juego?','conexiones_principales'),
    ('progresion','04','Progresión','¿Cómo progresa el ataque?',None),
    ('resultado','05','Desenlace','¿Dónde termina y qué consigue?','llegada_y_des_enlace'),
]
_QIDS=[q[0] for q in QUESTIONS]

from visualization.question_nav import question_nav, question_header, question_pager, question_answer


def _q_transition(events,team,selected,frames_360,key_prefix,**_):
    from visualization.transition_story_app import render_transition_chapter
    render_transition_chapter(events,team,'offensive',match_ids=selected,frames_360=frames_360,key_prefix=key_prefix+'_transition')


def _q_construction(d,t,story,result,key_prefix,**_):
    st.write(story['overview'])
    _insight_cards(story)
    # Distinguish stage/origin from mechanism: an origin lane is not a transition.
    phase_count=t.phase.fillna('Sin clasificación').astype(str).value_counts()
    if len(phase_count):
        main_phase=str(phase_count.index[0]); main_n=int(phase_count.iloc[0]); total=len(t)
        st.markdown(f"**Tipo de secuencia registrado con más frecuencia:** {main_phase} "
                    f"({main_n} de {total} secuencias de la selección).")
        if len(phase_count)>1:
            st.caption('Otras clasificaciones observadas: ' + ' · '.join(
                f'{p}: {n}' for p,n in phase_count.iloc[1:4].items()))
    if result is not None:
        from visualization.reasoning_ui import render_lane_chart
        render_lane_chart(result,key_prefix+'_lane_chart')
    st.caption('La primera coordenada registrada revela una zona de inicio, no cómo se recuperó la posesión. '
               'La pregunta 01 evalúa por separado las recuperaciones etiquetadas y sus primeros 15 segundos.')


def _q_connections(d,t,story,labels,key_prefix,**_):
    connection=story.get('connection')
    if connection:
        st.markdown(f"**{connection['from']} → {connection['to']}** es el enlace con más pases completos "
                    f"({connection['completed']} de {connection['attempts']} intentos con receptor registrado, "
                    f"en {connection['matches']} partidos).")
    else:
        st.write('No hay resultados y destinatarios suficientes para establecer una conexión principal.')
    st.write('El armado de juego se examina mediante las asociaciones de pase y las zonas donde aparecen '
             'sus protagonistas. Una conexión repetida indica circulación observada; por sí sola no demuestra '
             'una estructura fija (3-2-5, 4-3-3), un tercer hombre ni una intención del entrenador.')
    links_overview=A.connections(d) if d.attrs.get('outcome_available') else pd.DataFrame()
    left,right=st.columns([1,2.2])
    with left:
        if not links_overview.empty:
            ranked=links_overview[links_overview.completados.gt(0)].head(5)
            if not ranked.empty:
                st.markdown('**Principales conexiones del equipo**')
                for rank,r in enumerate(ranked.itertuples(index=False), 1):
                    st.write(f"{rank}. **{r.player} → {r.pass_recipient_name}**: "
                             f"{int(r.completados)} pases completos en {int(r.partidos)} partidos.")
    with right:
        _chart(G.figure_pass_network(d,max_players=11,max_links=22),key_prefix+'_main_network')
    st.caption('Nodos = mediana de las ubicaciones de intervención. Enlaces = pases completos con receptor; '
               'no son posiciones simultáneas, movimientos sin balón ni una formación reconstruida.')
    with st.expander('Explorar una conexión y sus eventos'):
        links=links_overview
        if links.empty:st.info('No hay conexiones con destinatario disponibles.')
        else:
            links=links[links.completados.gt(0)].head(40)
            if links.empty:st.info('No hay enlaces completados confirmados.')
            else:
                pairs=[(str(r.player),str(r.pass_recipient_name)) for _,r in links.iterrows()]
                chosen=st.selectbox('Jugadores conectados',pairs,format_func=lambda p:' → '.join(p),key=key_prefix+'_link_choice')
                link=d[d['_type'].eq('pass')&d.player.eq(chosen[0])&d.pass_recipient_name.eq(chosen[1])&d['_pass_done']]
                pt=t[t.key.isin(set(link['_poss_key']))]
                st.caption(f'{len(link)} pases completos · {len(pt)} secuencias · {pt.match_id.nunique()} partidos')
                if len(pt) and st.checkbox('Abrir una secuencia de esta conexión',value=False,key=key_prefix+'_pair_enable'):
                    _evidence(d,pt,key_prefix+'_pair',labels)


def _q_progression(d,t,labels,key_prefix,**_):
    st.write('Selecciona una posesión real para reconstruir su recorrido. No representa carreras o movimientos sin balón.')
    candidates=_representatives(t)
    keys=candidates.key.tolist()
    label_map={r.key:_sequence_label(r,labels) for _,r in candidates.iterrows()}
    selected_key=st.selectbox('Secuencia representativa',keys,format_func=lambda k:label_map.get(k,'Secuencia observada'),key=key_prefix+'_sequence')
    row=t[t.key.isin([selected_key])].iloc[0]
    _chart(V.figure_sequence_board(d,selected_key),key_prefix+'_sequence_board')
    st.markdown(f"**Resultado observado:** {row.outcome} · {int(row.actions)} acciones registradas · "
                f"{int(row.box_entries)} entradas al área · {int(row.shots)} remates.")
    summary=V.sequence_script(d,selected_key)
    if summary:st.caption(' → '.join(summary))
    st.caption('Las secuencias se seleccionan por desenlace y cantidad de acciones para ilustrar el proceso; un ejemplo no demuestra por sí solo que sea recurrente.')
    with st.expander('Profundizar · rutas colectivas registradas'):
        stage=st.radio('Sector de origen',['Construcción','Progresión','Creación'],horizontal=True,key=key_prefix+'_stage')
        _chart(V.figure_attack_route(d,stage),key_prefix+'_route_map')


def _q_outcome(d,t,story,key_prefix,**_):
    p=story.get('productivity',{})
    st.write(f"De {p.get('n_possessions',len(t))} secuencias, {p.get('box_entry_possessions',0)} registran entrada al área "
             f"y {p.get('shot_possessions',0)} incluyen al menos un remate. "
             f"El xG tiene cobertura en {p.get('shots_with_xg',0)} de {p.get('shots',0)} remates.")
    st.write('El mapa ubica los remates registrados o las entradas al área mediante pase y conducción. '
             'La zona de finalización y la cantidad de llegadas son hechos observables; no equivalen por sí solas '
             'a la calidad colectiva de una jugada ni a una eficacia táctica demostrada.')
    outcome=st.radio('Mostrar en la cancha',['Remates','Entradas al área'],horizontal=True,key=key_prefix+'_outcome_view')
    _chart(V.figure_attack_outcomes(d,outcome),key_prefix+'_outcome_pitch')
    route=story.get('route')
    if route:
        st.caption(f"En las secuencias con xG de remates completamente disponible, el corredor de inicio con mayor "
                   f"xG observado por secuencia elegible es {route['lane'].lower()} "
                   f"({route['xg_per_eligible_possession']:.3f}; n={route['eligible_possessions']}, "
                   f"{route['matches']} partidos). Asociación descriptiva, no causa demostrada.")


_RENDERERS={'transicion':_q_transition,'construccion':_q_construction,'conexiones':_q_connections,
            'progresion':_q_progression,'resultado':_q_outcome}


def render_attack_module(events,team,key_prefix='attack',precomputed=None,frames_360=None,result=None):
    st.markdown('## Cómo ataca · del balón recuperado a la oportunidad')
    st.caption('Cinco preguntas futbolísticas. Toca una para ver su respuesta, sus mapas y su evidencia.')
    try:
        if precomputed and isinstance(precomputed[0],pd.DataFrame) and isinstance(precomputed[1],pd.DataFrame):
            d,t=precomputed
        else:
            d,t=analyze(events,team)
    except (ValueError,KeyError,TypeError) as exc:
        st.info(f'No es posible reconstruir las secuencias ofensivas con esta muestra: {exc}')
        return
    if t.empty:
        st.info('No hay secuencias de juego abierto para el equipo seleccionado.')
        return
    selected,phase,player,minutes,state,labels=_select_scope(events,team,d,t,key_prefix)
    d,t=A.filter_sample(d,t,selected,phase,player,minutes,state)
    if t.empty:
        st.info('No hay secuencias para esta combinación de filtros. Amplía la muestra.')
        return
    story=build_offensive_story(d,t)
    st.caption(f"Muestra activa: {t.match_id.nunique()} {'partido' if t.match_id.nunique()==1 else 'partidos'} · {len(t):,} secuencias · {phase}"
               + (f' · Perspectiva: {player}' if player!='Colectivo' else ''))
    if story['status']=='SMALL_SAMPLE':
        st.caption('Muestra limitada: los resultados describen esta selección, no una identidad consolidada del entrenador.')
    if phase=='Todo el juego abierto':
        st.caption('Alcance: todas las secuencias de juego abierto observadas, incluidas transiciones y posesiones sin clasificación. Para estudiar sólo posesión controlada etiquetada, modifica el filtro.')
    if not d.attrs.get('restart_known'):
        st.warning('No hay etiquetas suficientes para excluir todas las reanudaciones: el juego abierto puede estar incompleto.')

    with st.container(key="efos_sticky_questions_attack"):
        qid=question_nav(QUESTIONS,key_prefix)
    question_header(QUESTIONS,qid)
    question_answer(QUESTIONS,qid,result,key_prefix)
    _RENDERERS[qid](events=events,team=team,selected=selected,frames_360=frames_360,d=d,t=t,
                    story=story,labels=labels,result=result,key_prefix=key_prefix)
    question_pager(QUESTIONS,qid,key_prefix)
    candidates=_representatives(t)
    st.divider()

    with st.expander('Análisis avanzado · para analistas',expanded=False):
        if st.checkbox('Activar investigación avanzada',value=False,key=key_prefix+'_advanced_enable'):
            option=st.selectbox('Tipo de investigación',['Respuesta a la presión','Mecanismos observables','Recepciones interiores','Comparativo de redes','Rutas de inicio'],key=key_prefix+'_advanced_choice')
            if option=='Respuesta a la presión':
                pc=A.pressure_comparison(d)
                if not pc.empty:st.dataframe(pc,hide_index=True,use_container_width=True)
                _chart(G.figure_pressure_exits(d),key_prefix+'_pressure_advanced')
                st.caption('Pases bajo presión y continuación observada; no demuestra atracción deliberada.')
            elif option=='Mecanismos observables':
                counts=A.mechanisms(d)
                for k,keys in counts.items():st.caption(f'{k}: {len(keys)} secuencias observadas')
                _chart(G.figure_mechanism_board(d),key_prefix+'_mechanisms_advanced')
            elif option=='Recepciones interiores':
                _chart(G.figure_halfspace_receptions(d),key_prefix+'_halfspace_advanced')
                st.caption('Recepciones en corredores definidos; sin localización de líneas rivales no se afirma recepción entre líneas.')
            elif option=='Comparativo de redes':_chart(G.figure_primary_network_atlas(d),key_prefix+'_atlas_advanced')
            else:_chart(G.figure_identity_atlas(d),key_prefix+'_identity_advanced')
            if st.checkbox('Ver interpretación conceptual',value=False,key=key_prefix+'_concept_enable'):
                context=context_for({'Respuesta a la presión':'pressure','Mecanismos observables':'interior',
                                     'Recepciones interiores':'interior','Comparativo de redes':'connections',
                                     'Rutas de inicio':'arrival'}[option])
                st.markdown('**Lectura táctica · '+context['title']+'**')
                st.write(context['reading'])
                st.markdown('**Explicación alternativa**')
                st.write(context['alternative'])
                st.markdown('**Pregunta para el entrenador**')
                st.write(context['question'])
                st.caption(context['limit'])
        else:
            st.caption('Esta capa conserva los atlas comparativos, los mecanismos experimentales y sus advertencias. No es necesaria para entender el relato principal.')

    with st.expander('Evidencia y metodología · examinar eventos y descargar',expanded=False):
        if st.checkbox('Mostrar tabla de evidencia',value=False,key=key_prefix+'_evidence_enable'):
            st.caption('Datos fuente de la selección y trazabilidad. Cada hallazgo se calcula con las mismas secuencias mostradas arriba.')
            evidence_view=t[['match_id','period','minute','lane','phase','actions','box_entries','shots','outcome','xg','xg_n']].copy()
            evidence_view['partido']=evidence_view.match_id.map(labels).fillna('Partido sin rival identificado')
            st.dataframe(evidence_view.drop(columns=['match_id']).rename(columns={
                'period':'Parte','minute':'Minuto','lane':'Corredor de inicio','phase':'Tipo de posesión',
                'actions':'Acciones','box_entries':'Entradas al área','shots':'Remates',
                'outcome':'Desenlace','xg':'xG observado','xg_n':'Remates con xG','partido':'Partido'}),
                hide_index=True,use_container_width=True)
            st.download_button('Descargar secuencias CSV',t.drop(columns=['key']).to_csv(index=False).encode('utf-8-sig'),
                file_name='efos_ataque_secuencias.csv',mime='text/csv',key=key_prefix+'_export')
            if st.checkbox('Examinar eventos de una secuencia',value=False,key=key_prefix+'_source_enable'):
                _evidence(d,candidates,key_prefix+'_last_evidence',labels)
        st.markdown('**Alcance y límites**')
        st.caption('Sólo eventos StatsBomb disponibles; las posiciones no son simultáneas. Posesión controlada sólo si está etiquetada. '
                   'xG y OBV proceden del proveedor. Los cortes espaciales y temporales son operativos, no causalidad demostrada. '
                   'OC, HPS, CTS y ESI mantienen sus fórmulas actuales.')


def _evidence(d,t,key,labels):
    if t.empty:st.info('No hay secuencias para este filtro.');return
    options=t.key.tolist()
    names={r.key:_sequence_label(r,labels) for _,r in t.iterrows()}
    chosen=st.selectbox('Elegir secuencia',options,format_func=lambda v:names.get(v,'Secuencia'),key=key+'_select')
    _chart(V.figure_sequence_board(d,chosen),key+'_pitch')
    fields=['event_id','match_id','period','possession','index','minute','second','player','event_type',
            'pass_recipient_name','outcome_name','location_x','location_y','end_location_x','end_location_y','obv_total_net']
    st.dataframe(d[d['_poss_key'].isin([chosen])][[c for c in fields if c in d]],hide_index=True,use_container_width=True)
