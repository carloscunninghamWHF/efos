"""Coach-facing recovery and vulnerability explanations, backed by event IDs."""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from intelligence.defensive_insights import zone_exposure, recovery_stats, pattern_table
from visualization.defensive_open_play_maps import _pitch, _layout, AMBER, GREEN


def recovery_map(d,which=None):
    cp=d[d.counterpress_observed]
    rec=cp[cp.control_confirmed]
    fig=make_subplots(rows=1,cols=1)
    _pitch(fig)
    for data,x,y,color,label in [(cp,'cp_x','cp_y',AMBER,'Inicio de contrapresión etiquetada'),
                                (rec,'control_x','control_y',GREEN,'Primer control posterior confirmado')]:
        if which is not None and x!=which: continue
        fig.add_trace(go.Scatter(x=data[x],y=data[y],mode='markers',name=label,
            marker=dict(size=9,color=color,opacity=.65),
            customdata=data[['match_id','possession','minute']].to_numpy(),
            hovertemplate='Partido %{customdata[0]} · posesión %{customdata[1]}<br>Minuto %{customdata[2]}<extra>%{fullData.name}</extra>'))
    return _layout(fig,380)


def exposure_map(table):
    # One cell for each final-third entry lane. No interpolation or invented positions.
    fig=make_subplots(rows=1,cols=1); _pitch(fig)
    for j,name in enumerate(['franja inferior','carril central','franja superior']):
        match=table[table.zona.str.endswith(name)]
        if len(match):
            r=match.iloc[0]; fraction=r.pct_remate/100
            label=f'{int(r.con_remate)}/{int(r.posesiones)} con remate<br>{r.pct_remate:.1f}% · {int(r.partidos)} partidos'
            fill=f'rgba(190,70,65,{.10+.65*fraction})'
        else: label='Sin entradas observadas'; fill='#E8ECEF'
        fig.add_shape(type='rect',x0=80,x1=120,y0=j*80/3,y1=(j+1)*80/3,
                      line=dict(color='white'),fillcolor=fill,layer='below')
        fig.add_annotation(x=100,y=(j+.5)*80/3,text=label,showarrow=False,font=dict(size=11))
    fig.add_annotation(x=35,y=40,text='Rival avanza →<br>Primera entrada observada<br>al último tercio',showarrow=False)
    return _layout(fig,370)


def render_insights(d,key_prefix,events=None,team=None):
    st.markdown('### Presión tras pérdida: ¿dónde volvemos a controlar el balón?')
    st.caption('Misma situación, tramo y marcador de la cabecera. Se identifican las posesiones con '
               'acciones defensivas etiquetadas counterpress; pueden aparecer también en contraataques. '
               'No equivale al total de pérdidas ni a todas las presiones del equipo.')
    k=recovery_stats(d)
    a,b,c=st.columns(3)
    a.metric('Posesiones con contrapresión etiquetada',k['n'])
    b.metric('Con control posterior confirmado',f"{k['recovered']} / {k['n']}" if k['n'] else 'Sin muestra')
    c.metric('Control en ≤10 s desde la primera acción',f"{k['fast']} / {k['n']}" if k['n'] else 'Sin muestra')
    if k['n']:
        left,right=st.columns(2)
        with left:
            st.markdown('**Dónde comienza la contrapresión**')
            st.plotly_chart(recovery_map(d,'cp_x'),use_container_width=True,key=f'{key_prefix}_recovery_start')
        with right:
            st.markdown('**Dónde se confirma el control posterior**')
            st.plotly_chart(recovery_map(d,'control_x'),use_container_width=True,key=f'{key_prefix}_recovery_end')
        st.write('**Dorado:** primera acción etiquetada de contrapresión. **Verde:** primera acción con balón '
                 'que confirma el regreso del control al equipo. Portería propia a la derecha. '
                 'El verde localiza el control observado; no siempre el instante exacto del robo.')
        st.caption(f"Ubicación disponible en {k['located']} de {k['recovered']} controles confirmados. "
                   'No se unen los puntos porque no conocemos el recorrido completo del balón.')
        rec=d[d.control_confirmed]
        if len(rec):
            counts=rec.control_zone.value_counts()
            st.write(f'El control posterior aparece con mayor frecuencia en **{counts.index[0]}** '
                     f'({int(counts.iloc[0])} de {len(rec)} casos confirmados). '
                     f'La mediana de tiempo entre la primera contrapresión y el primer control es '
                     f'**{k["median_seconds"]:.1f} segundos** entre los casos confirmados.')
    else:
        st.info('No hay contrapresión etiquetada en este filtro. No significa que el equipo no haya intentado presionar.')
    st.caption('Confirmación conservadora: acción propia con balón en la siguiente posesión, mismo periodo, '
               'sin reinicio ni interrupción registrada y a un máximo de 5 s del último evento de la posesión rival. '
               'El umbral de 10 s describe control rápido desde la primera contrapresión; no es un estándar validado. '
               'Los casos restantes son «sin control confirmado», no recuperaciones fallidas. '
               'La secuencia temporal no demuestra que la presión causara la recuperación.')
    from visualization.defensive_storytelling import vulnerabilities, patterns, example
    if events is not None:
        example(d[d.counterpress_observed],events,team,key_prefix+'_cp_example',
                'De la contrapresión al control: revisar una secuencia')
        vulnerabilities(d,events,team,key_prefix)
        patterns(d,events,team,key_prefix)
    with st.expander('Evidencia de recuperaciones y entradas · partido, posesión y evento'):
        cols=['match_id','possession','minute','scenario','counterpress_observed','cp_event_id','cp_zone',
              'control_confirmed','control_event_id','control_player','control_zone','control_seconds',
              'entry_event_id','entry_zone','shot_after_entry','xg_after_entry','entry_xg_complete']
        evidence=d[cols].rename(columns={'match_id':'Partido','possession':'Posesión','minute':'Minuto',
            'scenario':'Situación','counterpress_observed':'Contrapresión etiquetada','cp_event_id':'Evento de contrapresión',
            'cp_zone':'Zona de contrapresión','control_confirmed':'Control confirmado','control_event_id':'Evento de control',
            'control_player':'Jugador con control','control_zone':'Zona de control','control_seconds':'Segundos hasta control',
            'entry_event_id':'Evento de entrada','entry_zone':'Zona de entrada','shot_after_entry':'Remate posterior',
            'xg_after_entry':'xG posterior','entry_xg_complete':'xG completo'})
        st.dataframe(evidence,hide_index=True,use_container_width=True)
        st.download_button('Descargar evidencia CSV',evidence.to_csv(index=False).encode('utf-8-sig'),
                           'efos_defensive_evidence.csv','text/csv',key=f'{key_prefix}_insights_csv')


def render_insight_summary(d):
    st.markdown('#### Recuperación y señales de vulnerabilidad')
    k=recovery_stats(d)
    if k['n']:
        st.write(f'De **{k["n"]} posesiones con contrapresión etiquetada**, '
                 f'**{k["recovered"]}** tienen control posterior confirmado y **{k["fast"]}** '
                 'lo muestran en un máximo de 10 segundos desde la primera acción etiquetada. '
                 'Los casos sin confirmación no se interpretan automáticamente como fallos.')
    else:
        st.write('Sin contrapresión etiquetada en esta selección para evaluar el control posterior.')
    z=zone_exposure(d)
    if len(z):
        # No categorical recommendation on highest tiny denominator.
        qualified=z[(z.posesiones>=30)&(z.partidos>=5)]
        candidates=qualified if len(qualified) else z
        r=candidates.sort_values(['pct_remate','posesiones'],ascending=False).iloc[0]
        st.write(f'Entre los carriles '+('con al menos 30 posesiones y 5 partidos' if len(qualified) else 'observados, con muestra exploratoria')+
                 f', la mayor proporción de remates posteriores aparece en **{r.zona}**: '
                 f'**{int(r.con_remate)} de {int(r.posesiones)} posesiones ({r.pct_remate:.1f}%)**, '
                 f'en **{int(r.partidos)} partidos**. '
                 'Conviene revisar esas secuencias para entender cómo continuó la jugada; '
                 'esto no prueba un hueco entre defensores ni causalidad del carril de entrada.')
    st.caption('Tactical Gap · capa descriptiva: localiza señales para revisar. '
               'No se calcula GOS/GES 0–100 porque no hay una fórmula calibrada ni una referencia táctica esperada validada. '
               'No se infieren espacios entre líneas, marcajes, fatiga o estados psicológicos a partir de estos eventos.')
