"""Dos capítulos editoriales conectados, sin una pestaña extra de Transiciones.

Una evidencia = un grupo de eventos originales de StatsBomb. Voronoi y animación
son investigación opcional y NUNCA alimentan la conclusión principal.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from intelligence.transition_story import analyze_transitions, describe_transitions
from intelligence.offensive_story import readable_match_labels


@st.cache_data(show_spinner=False, max_entries=5)
def _compute(events: pd.DataFrame, team: str, match_ids: tuple | None):
    return analyze_transitions(events, team, match_ids)


def _map_points(data: pd.DataFrame, direction: str) -> go.Figure:
    """Locations of logged events only; no inferred player positioning or movement."""
    from visualization.transition_animation import _pitch_shapes_plotly
    fig = go.Figure()
    fig.update_layout(
        shapes=_pitch_shapes_plotly(), height=410,
        xaxis=dict(range=[-3,123],visible=False), yaxis=dict(range=[82,-2],visible=False,scaleanchor='x'),
        plot_bgcolor='#F8FAFC',paper_bgcolor='white',
        margin=dict(l=8,r=8,t=15,b=35),
        legend=dict(orientation='h',y=-.06,font=dict(size=11)),
    )
    groups = (
        [('Termina en remate ≤15 s', data.shots.gt(0), '#C89B3C'),
         ('Sin remate ≤15 s', data.shots.eq(0), '#64748B')]
        if direction == 'offensive' else
        [('Con presión registrada ≤5 s', data.pressures_5s.gt(0), '#C89B3C'),
         ('Sin presión registrada ≤5 s', data.pressures_5s.eq(0), '#64748B')]
    )
    for label, mask, color in groups:
        sub = data.loc[mask].copy()
        sub['location_x'] = pd.to_numeric(sub.location_x,errors='coerce')
        sub['location_y'] = pd.to_numeric(sub.location_y,errors='coerce')
        sub = sub.dropna(subset=['location_x','location_y'])
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub.location_x,y=sub.location_y,mode='markers',name=f'{label} · {len(sub)}',
            marker=dict(size=8,color=color,opacity=.69,line=dict(width=.45,color='white')),
            customdata=sub[['event_id','match_id']].astype(str).to_numpy(),
            hovertemplate='%{x:.1f}, %{y:.1f}<br>Partido: %{customdata[1]}<br>Evento: %{customdata[0]}<extra></extra>'
        ))
    return fig


def _case_selector(data: pd.DataFrame, events: pd.DataFrame, team: str, direction: str, key: str):
    if data.empty:
        return
    # Include examples with AND without a favorable outcome, not only highlights.
    field = 'shots' if direction == 'offensive' else 'rival_shots_15s'
    sample = pd.concat([data[data[field].gt(0)].head(5), data[data[field].eq(0)].head(5)])
    if len(sample) < 2:
        sample = data.head(10)
    else:
        sample = sample.drop_duplicates(subset='event_id')
    match_labels = readable_match_labels(events, team, sample.match_id.unique().tolist())
    rows = {str(x.event_id): x for x in sample.itertuples(index=False)}
    choice = st.selectbox('Jugada registrada', list(rows), key=f'{key}_case',
        format_func=lambda v: (f"{match_labels.get(str(rows[v].match_id),'Partido')} · "
                               f"{float(rows[v].minute):.0f}′ · {rows[v].anchor_type}"))
    chosen = rows[choice]
    if direction == 'offensive':
        outcome = (f'{int(chosen.shots)} remate(s)' if chosen.shots else 'Sin remate registrado')
        if chosen.shots:
            outcome += (f' · {chosen.xg:.3f} xG' if int(chosen.shots_with_xg) == int(chosen.shots)
                        else f' · xG disponible: {int(chosen.shots_with_xg)}/{int(chosen.shots)}')
        first=(f"{chosen.first_ball_action} · {chosen.first_ball_player if pd.notna(chosen.first_ball_player) else 'jugador no identificado'} "
               f"(+{chosen.first_action_after_s:.1f} s)" if pd.notna(chosen.first_ball_action) else 'no identificada')
        st.write(f"**Inicio:** {chosen.anchor_type} de {chosen.player if pd.notna(chosen.player) else 'jugador no identificado'}. "
                 f"**Primera acción con balón observada:** {first}. "
                 f"**Acciones posteriores (≤15 s, misma posesión):** {int(chosen.actions)}. "
                 f"**Desenlace:** {outcome}.")
    else:
        pressure_time=(f"primera a +{chosen.first_pressure_after_s:.1f} s" if pd.notna(chosen.first_pressure_after_s)
                       else 'sin presión registrada en esta ventana')
        st.write(f"**Inicio:** {chosen.anchor_type} de {chosen.player if pd.notna(chosen.player) else 'jugador no identificado'}, "
                 "seguida por posesión rival confirmada. "
                 f"**Respuesta en 5 s:** {int(chosen.pressures_5s)} presiones registradas ({pressure_time}); "
                 f"recuperación etiquetada: {'sí' if chosen.recovered_5s else 'no'}. "
                 f"**Remates del rival ≤15 s:** {int(chosen.rival_shots_15s)}.")
    st.caption('Cadena de eventos registrados: '+(chosen.sequence or 'no se registraron acciones adicionales en la ventana'))
    st.caption(f"Traza auditable: evento inicial `{chosen.event_id}` · {len(chosen.event_ids)} eventos vinculados. "
               "No describe carreras ni ubicación de jugadores sin balón.")


def render_transition_chapter(events:pd.DataFrame,team:str,direction:str,
                              match_ids=None, frames_360:dict|None=None,
                              key_prefix:str|None=None) -> None:
    """Use from attack or defense; no navigation side effects."""
    offensive = direction == 'offensive'
    key=key_prefix or ('tr_attack' if offensive else 'tr_defense')
    title = ('Tras recuperar · ¿cómo convierte la recuperación en ataque?' if offensive
             else 'Tras perder · ¿cómo responde antes de reorganizarse?')
    objective = ('**Objetivo:** describir la primera decisión con balón y su desenlace en ≤15 s, '
                 'sin confundir una recuperación con un contraataque necesariamente exitoso.' if offensive else
                 '**Objetivo:** identificar cuándo una pérdida es seguida de posesión rival, '
                 'y si se registra presión o recuperación inmediata en los siguientes 5 s.')
    st.markdown('### '+title)
    st.markdown(objective)
    ids=tuple(str(x) for x in match_ids) if match_ids is not None else None
    output=_compute(events,team,ids)
    summary=describe_transitions(output,direction)
    if output['status']!='ok':
        st.info(output.get('reason','No hay eventos suficientes.'))
        return
    data=output['offensive' if offensive else 'defensive']
    if not summary['n']:
        st.info(summary['story'])
        return
    st.write(summary['story'])
    if offensive:
        a,b,c=st.columns(3)
        a.metric('Recuperaciones elegibles',f"{summary['n']:,}",f"{summary['matches']} partidos")
        b.metric('Con remate en ≤15 s',f"{summary['shot_possessions']}/{summary['n']}",f"{summary['rate']:.1%} de las elegibles")
        xg_label=f"{summary['xg']:.2f}" if summary['xg'] is not None else 'Incompleto'
        c.metric('xG observado en 15 s',xg_label,f"cobertura: {summary['coverage'][0]}/{summary['coverage'][1]} remates")
        first=summary.get('common_first')
        if first:
            kind={'Pass':'pase','Carry':'conducción','Carries':'conducción','Dribble':'regate','Shot':'remate'}.get(first[0],first[0])
            st.write(f'**Primer gesto con balón registrado:** {kind} en {first[1]} de {first[2]} casos con acción identificable '
                     f'({first[1]/first[2]:.1%}); no representa necesariamente la intención original del jugador.')
        st.caption('Tiros y xG corresponden únicamente a eventos del equipo dentro de la misma posesión. '
                   'Se requiere Ball Recovery o Interception registrada al iniciar la posesión. '
                   'No incluye otras formas de recuperar sin etiqueta explícita.')
        label='Dónde se registra la recuperación y cuáles acaban en remate'
        follow='¿Qué primer pase o conducción aparece en los casos que progresan, y qué muestran los que no rematan?'
    else:
        a,b,c=st.columns(3)
        a.metric('Pérdidas verificables',f"{summary['n']:,}",f"{summary['matches']} partidos")
        b.metric('Con presión ≤5 s',f"{summary['pressure_cases']}/{summary['n']}",f"{summary['rate']:.1%} de las verificables")
        c.metric('Rival remata ≤15 s',f"{summary['rival_shot_cases']}/{summary['n']}",
                 f"Recuperaciones etiquetadas ≤5 s: {summary['regains']}")
        st.caption('Pérdida = acción candidata seguida de un cambio de posesión al rival (≤15 s). '
                   'Presión significa evento Pressure registrado, no intensidad colectiva deducida. '
                   'El remate rival se cuenta sólo dentro de su siguiente posesión.')
        label='Dónde se pierden balones y cuándo hay respuesta de presión registrada'
        follow='¿En qué zonas conviene revisar las pérdidas que permitieron rematar al rival sin presión registrada?'
    st.markdown('**Evidencia territorial · '+label+'**')
    st.plotly_chart(_map_points(data,direction),use_container_width=True,
                    config={'displaylogo':False},key=f'{key}_pitch')
    st.caption('Puntos = posición del evento original de StatsBomb, en coordenadas de ataque del equipo que '
               'realiza la acción. No representan una formación ni la ubicación simultánea del resto de jugadores.')
    st.markdown(f'**Pregunta para el cuerpo técnico:** {follow}')
    with st.expander('Explorar jugadas concretas y evidencia original',expanded=False):
        _case_selector(data,events,team,direction,key)
    with st.expander('Exploración espacial · fotografías 360 y animación opcional',expanded=False):
        st.caption('Es una capa de investigación visual separada de las estadísticas anteriores. '
                   'No calcula presión real, velocidad, superioridad táctica ni control de espacio a partir de Voronoi.')
        if st.checkbox('Activar explorador 360',value=False,key=f'{key}_enable360'):
            from visualization.transition_360_ui import render_transition_360
            render_transition_360({'events':events,'defensive_360_frames':frames_360 or {}},team,
                                  fixed_direction='Tras recuperación' if offensive else 'Tras pérdida',
                                  match_ids=ids,key_prefix=key,anchor_ids=set(data.event_id.astype(str)))
