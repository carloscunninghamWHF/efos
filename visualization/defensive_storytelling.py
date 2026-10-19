"""Guided defensive stories. Every example is one observed possession."""
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from intelligence.defensive_insights import zone_exposure, recovery_stats, zone
from intelligence.defensive_open_play import event_detail, DEFENSE_TYPES
from visualization.defensive_open_play_maps import sequence, _layout, BLUE, RED, GREEN


def route_patterns(d, events, team):
    rows=[]
    grouped={(str(m),p):g.sort_values(['period','index']) for (m,p),g in events.groupby(['match_id','possession'],sort=False)}
    for r in d[d.entry_event_id.ne('')].itertuples():
        ev=grouped.get((str(r.match_id),r.possession))
        if ev is None: continue
        entry=ev[ev.event_id.astype(str).eq(str(r.entry_event_id))]
        if entry.empty: continue
        shots=ev[ev.team.ne(team)&ev.event_type.eq('Shot')&ev['index'].gt(entry.iloc[0]['index'])]
        end=zone(shots.iloc[0].location_x,shots.iloc[0].location_y) if len(shots) else 'Sin remate posterior registrado'
        rows.append(dict(sample_id=r.sample_id,match_id=r.match_id,entry=r.entry_zone,end=end))
    return pd.DataFrame(rows,columns=['sample_id','match_id','entry','end'])


def lane_comparison(z):
    fig=go.Figure()
    labels=z.zona.str.replace('Cerca de portería propia · ','',regex=False)
    for name,values,color in [('Sin remate posterior registrado',z.posesiones-z.con_remate,BLUE),
                              ('Con remate posterior',z.con_remate,RED)]:
        fig.add_trace(go.Bar(y=labels,x=values,orientation='h',name=name,marker_color=color,
                            text=values,textposition='auto'))
    fig=_layout(fig,300)
    fig.update_layout(barmode='stack',xaxis_title='Posesiones por primera entrada (volumen)',legend=dict(y=-.4))
    return fig


def example(group, events, team, key, title='Seguir una posesión real'):
    if group.empty or events is None: return
    st.markdown('#### '+title)
    opts=group.sort_values(['match_id','minute','possession'])
    lookup={r.sample_id:r for r in opts.itertuples()}
    sid=st.selectbox('Jugada que respalda la lectura',list(lookup),key=key,
        format_func=lambda x:f'{lookup[x].match_id} · {lookup[x].minute:.0f}′ · posesión {lookup[x].possession} · '+
        ('con remate' if lookup[x].shot else 'sin remate registrado'))
    r=lookup[sid]; ev=event_detail(events,r.match_id,r.possession)
    own=ev[ev.team.eq(team)&ev.event_type.isin(DEFENSE_TYPES)]
    c1,c2,c3=st.columns(3)
    c1.markdown('**1 · Entrada / inicio**')
    c1.write(r.entry_zone if r.entry_event_id else 'Sin entrada al último tercio identificada.')
    c2.markdown('**2 · Intervención**')
    c2.write(f'{len(own)} acciones defensivas registradas. '+
             (f'Primera: {own.iloc[0].event_type} · {own.iloc[0].player}.' if len(own) else 'No se infiere ausencia de oposición.'))
    c3.markdown('**3 · Continuación**')
    c3.write(('Hay remate rival en la posesión. ' if r.shot else 'No hay remate rival registrado. ')+
             (f'Control posterior confirmado: {r.control_player}, {r.control_seconds:.1f} s desde la contrapresión.'
              if r.control_confirmed else 'Sin control posterior confirmado por la regla de contrapresión.'))
    st.plotly_chart(sequence(events,team,r.match_id,r.possession),use_container_width=True,key=key+'_pitch')
    st.caption('Rival avanza → portería propia. Azul: pases (línea continua) y conducciones (punteada); '
               'dorado: intervenciones defensivas numeradas; cruz roja: remate. Cada segmento corresponde a un evento. '
               'No se conectan huecos entre eventos ni se dibujan jugadores sin ubicación observada.')
    if r.control_confirmed:
        st.write(f'**Después de esta posesión:** el primer control se observa en **{r.control_zone}** '
                 f'(evento {r.control_event_id}). No equivale necesariamente al lugar exacto del robo.')
    with st.expander('Cronología y eventos de esta jugada'):
        st.dataframe(ev[['event_id','minute','second','team','player','event_type','outcome_name']],hide_index=True)


def vulnerabilities(d, events, team, key):
    st.markdown('### ¿Cómo consigue el rival llegar al remate?')
    z=zone_exposure(d)
    if z.empty:
        st.info('No hay entradas al último tercio identificables en esta selección. No se estima vulnerabilidad por carril.')
        return
    n=int(z.posesiones.sum()); volume=z.sort_values('posesiones',ascending=False).iloc[0]
    st.write(f'Podemos seguir la primera entrada al último tercio en **{n} de {len(d)} posesiones**. '
             f'La vía más utilizada es **{volume.zona}**, con **{int(volume.posesiones)} entradas**. '
             'Una vía frecuente no es automáticamente la más peligrosa: compara su proporción con remate y su repetición.')
    st.plotly_chart(lane_comparison(z),use_container_width=True,key=key+'_volume')
    for col,r in zip(st.columns(len(z)),z.itertuples()):
        with col:
            st.markdown('**'+r.zona.split(' · ')[-1].capitalize()+'**')
            st.metric('Entradas que continúan hasta remate',f'{r.pct_remate:.1f}%')
            st.write(f'**{r.con_remate} de {r.posesiones}** posesiones · **{r.partidos}** partidos.')
            st.caption(r.evidencia+'. El remate puede producirse en otro carril.')
    lane=st.selectbox('¿Qué vía quieres entender?',z.zona.tolist(),key=key+'_lane')
    g=d[d.entry_zone.eq(lane)]; shot_n=int(g.shot_after_entry.sum())
    st.info(f'**Lectura del carril:** en {shot_n} de {len(g)} entradas hubo un remate posterior; '
            f'en {len(g)-shot_n} no lo hubo. Esto no confirma una recuperación en los casos sin remate. '
            'Revisa cómo se conecta la entrada con la siguiente acción rival y dónde aparece la oposición.')
    by_match=g.groupby('match_id').agg(entradas=('sample_id','size'),remates=('shot_after_entry','sum'))
    fig=go.Figure(go.Scatter(x=by_match.entradas,y=by_match.remates,mode='markers',text=by_match.index,
        marker=dict(size=13,color=RED),hovertemplate='Partido %{text}<br>%{x} entradas · %{y} con remate<extra></extra>'))
    fig=_layout(fig,260);fig.update_layout(xaxis_title='Entradas por partido',yaxis_title='Entradas con remate posterior')
    st.plotly_chart(fig,use_container_width=True,key=key+'_matches')
    st.caption('Cada punto es un partido. Puntos superpuestos pueden representar varios partidos; consulta el respaldo. '
               'La dispersión permite comprobar si la señal se concentra en un encuentro.')
    outcome=st.radio('Contrastar desenlace',['Todas','Con remate posterior','Sin remate posterior'],horizontal=True,key=key+'_outcome')
    eg=g if outcome=='Todas' else g[g.shot_after_entry.eq(outcome=='Con remate posterior')]
    if eg.empty: st.info('No hay jugadas con ese desenlace en el carril seleccionado.')
    else: example(eg,events,team,key+'_example')
    with st.expander('Respaldo numérico de carriles y partidos'):
        st.dataframe(z,hide_index=True); st.dataframe(by_match)
    st.caption('Primera entrada = pase completado o conducción que cruza x=80. Cada posesión cuenta una vez. '
               'Sin entrada identificada no significa sin peligro. Los eventos no prueban huecos entre líneas ni fallos individuales.')


def patterns(d,events,team,key):
    st.markdown('### Patrones: de la entrada al desenlace')
    p=route_patterns(d,events,team)
    if p.empty:
        st.info('Sin rutas identificables para esta selección.');return
    groups=p.groupby(['entry','end']).agg(n=('sample_id','size'),matches=('match_id','nunique')).reset_index()
    repeated=groups[groups.n.ge(2)].sort_values(['matches','n'],ascending=False)
    if repeated.empty:
        st.info('No hay rutas repetidas: los casos aislados siguen disponibles en el explorador.');return
    st.write('Agrupamos por carril de primera entrada y zona del primer remate posterior, o ausencia de remate. '
             'Son rutas de eventos repetidas; no una reconstrucción del movimiento de todos los jugadores.')
    labels={i:f'{r.entry.split(" · ")[-1]} → {r.end} · {r.n} posesiones / {r.matches} partidos'
            for i,r in repeated.iterrows()}
    choice=st.selectbox('Ruta repetida que quieres revisar',list(labels),format_func=labels.get,key=key+'_route')
    r=repeated.loc[choice]
    st.markdown(f'**Entrada por {r.entry.split(" · ")[-1]} → {r.end}**')
    st.write(f'Se observa en **{int(r.n)} posesiones de {int(r.matches)} partidos**. '
             +('Es una señal exploratoria; puede depender de un rival o de pocos casos. ' if r.n<30 or r.matches<5 else 'Es una regularidad descriptiva de la muestra. ')+
             'Aporta una selección concreta de jugadas para comprobar cómo continúa el ataque después de entrar.')
    st.write('**Pregunta para el cuerpo técnico:** ¿qué acción rival conecta la entrada con el desenlace y qué intervención defensiva aparece entre ambas?')
    ids=set(p[(p.entry==r.entry)&(p.end==r.end)].sample_id)
    example(d[d.sample_id.isin(ids)],events,team,key+'_pattern_example','Comprobar la ruta en una jugada')


def priorities(d,events,team,key):
    st.markdown('### Tres conclusiones para revisar con el cuerpo técnico')
    z=zone_exposure(d);k=recovery_stats(d)
    st.markdown('**1 · Lo que sí podemos confirmar**')
    st.write(f'En {k["recovered"]} de {k["n"]} posesiones con contrapresión etiquetada aparece control posterior confirmado. '
             'Es evidencia de regreso del control, no una atribución causal ni una tasa sobre todas las pérdidas.')
    if len(z):
        qualified=z[(z.posesiones>=30)&(z.partidos>=5)]
        candidates=qualified if len(qualified) else z
        r=candidates.sort_values(['pct_remate','posesiones'],ascending=False).iloc[0]
        st.markdown('**2 · La señal de vulnerabilidad que conviene contrastar**')
        st.write(f'{r.zona}: **{int(r.con_remate)}/{int(r.posesiones)}** entradas con remate posterior '
                 f'(**{r.pct_remate:.1f}%**), en **{int(r.partidos)} partidos**. '+
                 ('Muestra exploratoria. ' if qualified.empty else '')+
                 'Es la mayor proporción entre los carriles comparados'+(' con al menos 30 entradas y 5 partidos.' if len(qualified) else '.'))
        st.plotly_chart(lane_comparison(z),use_container_width=True,key=key+'_summary_plot')
        st.markdown('**3 · Una revisión concreta antes de proponer una tarea**')
        st.write('Contrasta una entrada con remate y otra sin remate del carril señalado. '
                 'Revisa el recorrido del balón, la primera oposición registrada y la acción siguiente. '
                 'Comprueba coberturas con vídeo o 360 antes de atribuir responsabilidades o prescribir un ajuste.')
        example(d[d.entry_zone.eq(r.zona)],events,team,key+'_priority_example')
    else:
        st.info('Faltan entradas identificables para priorizar una zona; no se fabrica una conclusión táctica.')
