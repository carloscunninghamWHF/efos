"""Editorial rendering of EFOS tactical diagnosis; no theoretical bibliography in UI."""
from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from interpretation.tactical_reasoning import build_tactical_reasoning

COLORS={'Izquierda':'#6A88A8','Centro':'#C89B3C','Derecha':'#1C3957'}


def _reading(item, prefix):
    with st.container(border=True):
        claim = item.get('claim_v1') or {}
        if claim:
            st.caption(f"Evidencia {claim['evidence_level']} · {claim['sample']['n_matches']} partidos · {claim['claim_id']}")
        st.markdown(f"**{item['question']}**")
        st.write(item['observation'])
        st.markdown('**Qué revela en esta muestra**')
        st.write(item['interpretation'])
        st.markdown('**Qué debe revisar el cuerpo técnico**')
        st.write(item['action'])
        with st.expander('Comprobar evidencia y otras explicaciones'):
            st.caption('Muestra: '+item['scope'])
            st.write('Contexto: '+item['context'])
            st.write('Otra explicación posible: '+item['alternative'])
            st.write('Limitación: '+item['limitation'])
            e=item['evidence']
            st.caption(f"Numerador: {e['observed']} · Denominador: {e['denominator']} · "
                       f"Partidos: {e['matches']} · Definición: {e['metric']}")
            if item['cases']:
                st.caption('Identificadores de secuencias para auditoría: '+', '.join(item['cases'][:8]))


def _analysis(result:dict):
    return result.get('tactical_reasoning') or build_tactical_reasoning(result)


def find_reading(result:dict, ident:str):
    """Return one connected-diagnosis finding by id, or None when the sample cannot support it."""
    analysis=_analysis(result)
    return next((f for f in analysis.get('findings',[]) if f.get('id')==ident),None)


def render_answer(result:dict, ident:str, key:str):
    """Answer card for one question of a module (v0.4.25 question navigation)."""
    item=find_reading(result,ident)
    if item is not None:
        claims = _analysis(result).get('claims_v1', [])
        matched = next((c for c in claims if c['claim_id'] and c['question'] == item['question']), None)
        item = dict(item, claim_v1=matched)
    if item is None:
        st.caption('El diagnóstico conectado no tiene una muestra evaluable para esta pregunta; '
                   'el contenido inferior describe sólo lo observado.')
        return
    st.markdown("<div class='efos-answer-kicker'>RESPUESTA EFOS · MUESTRA PRINCIPAL</div>",unsafe_allow_html=True)
    _reading(item,key)


def render_lane_chart(result:dict, key:str):
    analysis=_analysis(result)
    lanes=analysis.get('lane_table')
    if lanes is None or lanes.empty:
        return
    fig=go.Figure()
    for _,r in lanes.iterrows():
        fig.add_trace(go.Bar(x=[r['lane']],y=[r['porcentaje_inicios']],name=str(r['lane']),
            marker_color=COLORS.get(str(r['lane']),'#62758D'),
            customdata=[[int(r['posesiones']),int(r['con_remate']),float(r['tasa_remate_pct'])]],
            hovertemplate='%{x}: %{y:.1f}% de inicios<br>%{customdata[0]} posesiones<br>'
                          '%{customdata[1]} con remate (%{customdata[2]:.1f}% del corredor)<extra></extra>'))
    fig.update_layout(title='¿Dónde comienzan las posesiones observadas?',showlegend=False,
                      yaxis_title='% de posesiones con corredor conocido',yaxis_range=[0,100],
                      xaxis_title='Primer corredor registrado',height=330,margin=dict(t=45,l=30,r=10,b=40),
                      paper_bgcolor='white',plot_bgcolor='white')
    st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False},key=key)
    st.caption('Las barras representan origen, no entradas al último tercio. El remate es un desenlace '
               'de la misma posesión, no una atribución causal al corredor.')


def render_defense_chart(result:dict, key:str):
    d=_analysis(result).get('defense_table')
    if d is None or d.empty:
        return
    fig=go.Figure(go.Bar(y=d['scenario'].tolist(),x=d['tasa_remate_pct'].tolist(),orientation='h',
                       marker_color='#C89B3C',customdata=d[['con_remate','posesiones']].to_numpy(),
                       hovertemplate='%{y}: %{x:.1f}%<br>%{customdata[0]} de %{customdata[1]} posesiones<extra></extra>'))
    fig.update_layout(title='¿Cuándo remata el rival?',xaxis_title='% posesiones con remate',
                      xaxis_range=[0,100],height=330,margin=dict(t=45,l=190,r=15,b=35),
                      paper_bgcolor='white',plot_bgcolor='white',yaxis=dict(autorange='reversed'))
    st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False},key=key)
    st.caption('Cada porcentaje usa únicamente las posesiones de ese escenario. La proporción no equivale '
               'automáticamente a vulnerabilidad táctica.')


def render_reasoning(result:dict, chapter:str='all', show_intro:bool=True):
    analysis=result.get('tactical_reasoning') or build_tactical_reasoning(result)
    if not analysis['coverage']:
        st.info(analysis['identity'])
        return
    if chapter=='all' and show_intro:
        st.markdown('### Identidad de juego · lo que realmente encontramos')
        st.write(analysis['identity'])
        st.caption('Síntesis de muestras diferentes: cada afirmación conserva su propio denominador.')
        st.markdown('### ¿Qué debería estudiar el cuerpo técnico?')
        st.write(analysis['priority'])
        st.markdown('### El porqué detrás de los números')
        st.caption('Primero la lectura, después su evidencia. Las conclusiones se recalculan cuando cambia la muestra principal.')
    group={'attack':'Cómo ataca','defense':'Cómo defiende'}.get(chapter)
    findings=[f for f in analysis['findings'] if not group or f['module']==group]
    if not findings:
        st.info('No se dispone de muestras clasificadas suficientes para este diagnóstico.')
        return
    for i, finding in enumerate(findings):
        _reading(finding,f'{chapter}_{i}')
    if chapter in ('all','attack') and not analysis['lane_table'].empty:
        with st.expander('Ver gráfico · Origen observado y desenlace por corredor',expanded=chapter=='attack'):
            lanes=analysis['lane_table']
            fig=go.Figure()
            for _,r in lanes.iterrows():
                fig.add_trace(go.Bar(x=[r['lane']],y=[r['porcentaje_inicios']],name=str(r['lane']),
                    marker_color=COLORS.get(str(r['lane']),'#62758D'),
                    customdata=[[int(r['posesiones']),int(r['con_remate']),float(r['tasa_remate_pct'])]],
                    hovertemplate='%{x}: %{y:.1f}% de inicios<br>%{customdata[0]} posesiones<br>'
                                  '%{customdata[1]} con remate (%{customdata[2]:.1f}% del corredor)<extra></extra>'))
            fig.update_layout(title='¿Dónde comienzan las posesiones observadas?',showlegend=False,
                              yaxis_title='% de posesiones con corredor conocido',yaxis_range=[0,100],
                              xaxis_title='Primer corredor registrado',height=330,margin=dict(t=45,l=30,r=10,b=40),
                              paper_bgcolor='white',plot_bgcolor='white')
            st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False},key=f'reason_lanes_{chapter}')
            st.caption('Las barras representan origen, no entradas al último tercio. El remate es un desenlace '
                       'de la misma posesión, no una atribución causal al corredor.')
    if chapter in ('all','defense') and not analysis['defense_table'].empty:
        with st.expander('Ver gráfico · Situaciones de juego abierto y remates rivales',expanded=chapter=='defense'):
            d=analysis['defense_table']
            fig=go.Figure(go.Bar(y=d['scenario'].tolist(),x=d['tasa_remate_pct'].tolist(),orientation='h',
                               marker_color='#C89B3C',customdata=d[['con_remate','posesiones']].to_numpy(),
                               hovertemplate='%{y}: %{x:.1f}%<br>%{customdata[0]} de %{customdata[1]} posesiones<extra></extra>'))
            fig.update_layout(title='¿Cuándo remata el rival?',xaxis_title='% posesiones con remate',
                              xaxis_range=[0,100],height=330,margin=dict(t=45,l=190,r=15,b=35),
                              paper_bgcolor='white',plot_bgcolor='white',yaxis=dict(autorange='reversed'))
            st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False},key=f'reason_def_{chapter}')
            st.caption('Cada porcentaje usa únicamente las posesiones de ese escenario. La proporción no equivale '
                       'automáticamente a vulnerabilidad táctica.')
    if chapter=='all':
        st.caption(analysis['disclaimer'])
