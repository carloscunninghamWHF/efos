"""Optional, evidence-grounded 360 animations, isolated from EFOS core metrics."""
from __future__ import annotations
import json
import pandas as pd
import streamlit as st
from visualization import transition_animation as TA
from intelligence.offensive_story import readable_match_labels
from intelligence.transition_story import find_360_anchors


def _read_uploaded_frames(files) -> dict:
    """Parse native StatsBomb 360 JSON; do not synthesize missing frames."""
    frames={}
    for file in files:
        try:
            raw=json.loads(file.getvalue())
            if not isinstance(raw,list): continue
            for snap in raw:
                if not isinstance(snap,dict): continue
                event_id=snap.get('event_uuid') or snap.get('event_id')
                if event_id is None or not isinstance(snap.get('freeze_frame'),list): continue
                frames[str(event_id)]={'freeze_frame':snap['freeze_frame'],
                                        'visible_area':snap.get('visible_area'),
                                        'event_id':str(event_id)}
        except (ValueError,UnicodeDecodeError,TypeError):
            st.warning(f'No se pudo interpretar {file.name} como StatsBomb 360 nativo.')
    return frames


def _animation_starts(events:pd.DataFrame,frames:dict,team:str,direction:str,
                      anchor_ids:set[str]|None=None) -> pd.DataFrame:
    """Anchor transitions to REAL events, even when their 360 frame is absent.

    A 360 photo of a later event in the next 15 s can support an exploration;
    it must never be presented as the state at the instant of the regain/loss.
    """
    return find_360_anchors(events,team,direction,set(frames),anchor_ids=anchor_ids)


def render_transition_360(result:dict, team:str, fixed_direction:str|None=None,
                          match_ids:tuple|None=None, key_prefix:str="tr_360",
                          anchor_ids:set[str]|None=None):
    events=result.get('events')
    st.markdown('### Animación 2D de una transición · StatsBomb 360')
    st.write('Explora una recuperación o pérdida real. Las fotografías 360 son observadas; entre eventos '
             'se interpola visualmente un movimiento probable, **no tracking real**.')
    frames=result.get('defensive_360_frames') or {}
    uploads=st.file_uploader('Añadir archivos StatsBomb 360 (JSON nativos, uno por partido)',
        type=['json'],accept_multiple_files=True,key=f'{key_prefix}_json')
    if uploads:
        frames={**frames,**_read_uploaded_frames(uploads)}
    if not frames:
        st.info('No se cargaron fotografías StatsBomb 360. El resto del análisis de transiciones permanece disponible.')
        return
    if not isinstance(events,pd.DataFrame) or events.empty:
        st.info('Sin eventos de partido para enlazar con fotografías 360.');return
    direction=(fixed_direction or st.radio('Situación de transición',['Tras recuperación','Tras pérdida'],
                       horizontal=True,key=f'{key_prefix}_direction'))
    starts=_animation_starts(events,frames,team,direction,anchor_ids=anchor_ids)
    if match_ids is not None:
        starts=starts[starts.match_id.astype(str).isin(set(match_ids))].copy()
    if starts.empty:
        st.info('Hay fotografías 360, pero ninguna coincide con eventos de la transición o con sus siguientes 15 s en el mismo partido y periodo.')
        return
    match_ids=starts.match_id.astype(str).drop_duplicates().tolist()
    labels=readable_match_labels(events,team,match_ids)
    match=st.selectbox('Partido',match_ids,format_func=lambda x:labels.get(x,'Partido'),key=f'{key_prefix}_match')
    current=starts[starts.match_id.astype(str).eq(match)]
    options=current.event_id.astype(str).tolist()
    rows={str(r.event_id):r for r in current.itertuples(index=False)}
    chosen=st.selectbox('Momento registrado',options,
        format_func=lambda eid:f"{rows[eid].minute:.0f}′ · {rows[eid].event_type} · {getattr(rows[eid],'player','')}",
        key=f'{key_prefix}_start')
    steps=TA.build_sequence(events,frames,team,chosen)
    if not steps:
        st.info('Esta jugada no tiene una fotografía 360 válida vinculada. No se dibujan posiciones inventadas.')
        return
    if steps[0]['t'] > 0.05:
        st.caption(f"No existe una fotografía en el evento inicial. La primera imagen realmente disponible corresponde a +{steps[0]['t']:.1f} s; no describe el momento exacto de la pérdida o recuperación.")
    mode=st.radio('Qué quieres examinar',
                  ['Fotografía original (evidencia)','Animación ilustrativa (interpolada)'],
                  horizontal=True,key=f'{key_prefix}_mode')
    if mode.startswith('Fotografía'):
        available=(steps[0]['visible'] is not None and steps[0]['is_team'].sum()>=2
                   and (~steps[0]['is_team']).sum()>=2)
        show_voronoi=st.checkbox('Mostrar Voronoi de proximidad geométrica',value=False,
                                 disabled=not available,key=f'{key_prefix}_voronoi')
        if not available:
            st.caption('Voronoi desactivado: se requieren área visible y ≥2 jugadores observados de cada equipo.')
        fig=TA.snapshot_figure(steps[0],team,show_voronoi=bool(show_voronoi and available))
        st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False},key=f'{key_prefix}_snapshot')
        st.caption('**Fotografía real:** ubicaciones anotadas en un evento de StatsBomb 360. '
                   'Voronoi, si se activa, muestra proximidad geométrica de jugadores visibles, '
                   'no dominio efectivo del espacio. Fuera del campo de visión no se asignan conclusiones.')
        return
    if len(steps)<2:
        st.info('Sólo hay una fotografía enlazada. Se puede inspeccionar arriba, pero no fabricar una animación.')
        return
    fps=st.select_slider('Fluidez de reproducción',options=[4,6,8,10],value=6,key=f'{key_prefix}_fps')
    fig=TA.plotly_animation(steps,team, f'{direction} · {labels.get(match)}',fps=fps)
    st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False},key=f'{key_prefix}_animation')
    st.caption(f'**Evidencia real:** {len(steps)} fotografías 360 enlazadas en los primeros 15 s. '
               '**Estimación visual:** trayectorias interpoladas y Voronoi interpolado, nunca tracking. '
               'Sólo se conocen jugadores visibles en las fotografías. Esta animación no alimenta métricas EFOS.')
    if st.button('Preparar GIF de esta secuencia',key=f'{key_prefix}_gif_generate'):
        with st.spinner('Renderizando GIF desde las fotografías 360…'):
            try:
                st.session_state[f'{key_prefix}_gif_cache']=TA.gif_bytes(steps,team,
                    f'{direction} · {labels.get(match)}',fps=6)
                st.session_state[f'{key_prefix}_gif_source']=chosen
            except Exception as exc:
                st.warning(f'No se pudo exportar el GIF en este entorno: {exc}')
    if st.session_state.get(f'{key_prefix}_gif_source')==chosen and st.session_state.get(f'{key_prefix}_gif_cache'):
        st.download_button('Descargar animación GIF',st.session_state[f'{key_prefix}_gif_cache'],
            file_name='EFOS_Transicion_360.gif',mime='image/gif',key=f'{key_prefix}_gif_download')
