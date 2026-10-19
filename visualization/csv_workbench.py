"""CSV import workbench integrated in the team selection screen."""
import hashlib
import json
import pandas as pd
import streamlit as st
from ingestion.flexible_csv import ALIASES,EVENTS,read_flexible,suggest_mapping,adapt
from visualization.defensive_open_play_app import render_defensive_module


def render_csv_workbench():
    st.markdown('## Analizar un CSV de otro equipo')
    st.write('Carga una tabla de eventos o estadísticas agregadas. Relaciona sus columnas y revisa qué análisis permite. '
             'Los archivos originales no se modifican. Incluye las acciones de ambos equipos para analizar la defensa.')
    files=st.file_uploader('CSV de uno o varios partidos con la misma estructura',type=['csv'],accept_multiple_files=True,key='flex_files')
    if not files:return
    digest=hashlib.sha256(b''.join(f.getvalue() for f in files)).hexdigest()[:12]
    a,b=st.columns(2)
    encoding=a.selectbox('Codificación',['auto','utf-8-sig','cp1252','latin-1'])
    separator=b.selectbox('Separador',['auto',',',';','\t','|'])
    try:
        loaded=[read_flexible(f.getvalue(),encoding,separator) for f in files]
        columns=list(loaded[0][0].columns)
        if any(list(x[0].columns)!=columns for x in loaded):
            st.error('Los archivos tienen estructuras diferentes. Cárgalos por separado o unifica sus columnas.');return
        df=pd.concat([x[0] for x in loaded],ignore_index=True)
    except (ValueError,UnicodeError,pd.errors.ParserError) as exc:
        st.error(str(exc));return
    st.caption(f'{len(df):,} filas · {len(files)} archivo(s) · codificación: '+', '.join(sorted(set(x[1] for x in loaded))))
    st.dataframe(df.head(8),hide_index=True)
    kind=st.radio('Contenido del archivo',['Eventos de juego','Estadísticas agregadas'],horizontal=True,key=digest+'_kind')
    if kind=='Estadísticas agregadas':
        teamcol=st.selectbox('Columna del equipo',columns,key=digest+'_agg_team')
        focal=st.selectbox('Equipo',sorted(df[teamcol].dropna().astype(str).unique()),key=digest+'_agg_focal')
        selected=df[df[teamcol].astype(str).eq(focal)]
        st.dataframe(selected,hide_index=True)
        st.info('Resumen agregado: estas filas no permiten reconstruir posesiones, recorridos ni contrapresión. '
                'No se suman porcentajes o promedios sin conocer sus denominadores.');return
    suggested=suggest_mapping(df);mapping={}
    with st.expander('1 · Relacionar columnas',expanded=True):
        cols=st.columns(3)
        for i,field in enumerate(ALIASES):
            options=['No disponible']+columns
            pick=cols[i%3].selectbox(field,options,index=options.index(suggested[field]) if suggested[field] else 0,key=digest+'_map_'+field)
            mapping[field]=None if pick=='No disponible' else pick
    if mapping['event_type']:
        values=sorted(df[mapping['event_type']].dropna().astype(str).unique())
        unknown=[x for x in values if x not in EVENTS and x!='Carries']
    else:unknown=[]
    event_map={}
    if unknown:
        with st.expander('Traducir nombres de eventos',expanded=True):
            for value in unknown:
                target=st.selectbox(value,['Sin equivalencia']+EVENTS,key=digest+'_event_'+value)
                if target!='Sin equivalencia':event_map[value]=target
    with st.expander('2 · Coordenadas y significado de los datos',expanded=True):
        a,b=st.columns(2)
        length=a.number_input('Longitud del campo en el archivo',min_value=1.,value=120.)
        width=b.number_input('Anchura del campo en el archivo',min_value=1.,value=80.)
        orient=st.selectbox('Dirección de ataque de las coordenadas',['Por equipo actor: siempre hacia +X','Campo fijo: cambia por equipo / periodo'])
        direction=None
        if orient.startswith('Campo fijo'):
            direction=st.selectbox('Columna de dirección: 1 hacia +X; -1 hacia -X',columns)
        flip=st.checkbox('Invertir eje Y (origen vertical opuesto)')
        confirmed=st.checkbox('Confirmo orientación, reloj acumulado del partido y segundos 0–59; los resultados usan etiquetas StatsBomb (vacío = pase completado).',key=digest+'_semantics')
        st.caption('play_pattern_name debe identificar reinicios y balón parado. Para otros proveedores, normaliza esos valores '
                   'a Regular Play, From Counter, From Corner, From Free Kick, From Throw In, From Goal Kick o From Kick Off. '
                   'No se infiere que un pase sin resultado fue completado sin esta confirmación.')
    try:
        events,report=adapt(df,mapping,event_map,length,width,'fixed' if orient.startswith('Campo fijo') else 'actor',direction,flip)
    except ValueError as exc: st.error(str(exc));return
    st.markdown('### 3 · Calidad y capacidades')
    a,b,c=st.columns(3)
    a.metric('Filas recibidas',report['rows']);b.metric('Filas con campos requeridos válidos',report['usable']);c.metric('Filas excluidas',report['excluded'])
    st.write(f"Duplicados exactos consolidados: {report['exact_duplicates_removed']} · Coordenadas fuera de rango anuladas: {report['invalid_coordinates']} · Órdenes de evento duplicados: {report['duplicate_order']}.")
    if report['missing']:st.warning('Faltan campos para secuencias defensivas: '+', '.join(report['missing']))
    if report['unknown_events']:st.warning('Eventos sin equivalencia: '+', '.join(report['unknown_events']))
    if not report['outcome_available']:st.warning('Sin resultado de pases: no se pueden identificar entradas completadas.')
    if not report['spatial']:st.warning('Sin todas las coordenadas de inicio y fin: no se habilitan mapas de rutas.')
    st.caption(('Contrapresión disponible. ' if report['counterpress_available'] else 'Sin etiqueta de contrapresión: no se evalúa presión tras pérdida. ')+
               ('Campo xG disponible; se comprobará su cobertura. ' if report['xg_available'] else 'Sin xG: los remates se cuentan, sin estimar su calidad. ')+
               'Sin 360 adjunto: no se dibujan posiciones simultáneas.')
    st.download_button('Descargar informe de calidad',json.dumps(report,ensure_ascii=False,indent=2),'efos_calidad_csv.json','application/json')
    if not report['teams']:st.info('Relaciona la columna del equipo para continuar.');return
    team=st.selectbox('Equipo que quieres analizar',report['teams'],key=digest+'_team')
    if not report['defense_ready'] or not confirmed:
        st.info('Disponible: resumen de registros. El atlas se habilita al completar y confirmar los campos requeridos.')
        if 'event_type' in events:
            st.dataframe(events[events.team.eq(team)].event_type.value_counts().rename_axis('Evento').reset_index(name='Registros'),hide_index=True)
        return
    matches=sorted(events.match_id.dropna().astype(str).unique())
    chosen=st.multiselect('Partidos para el análisis',matches,default=matches,key=digest+'_matches')
    selected=events[events.match_id.isin(chosen)]
    if selected.empty:st.info('Selecciona al menos un partido.');return
    from visualization.organized_attack_app import render_attack_module
    render_attack_module(selected,team,key_prefix='csv_attack_'+digest)
    valid=selected.groupby('match_id').team.nunique()
    if valid.lt(2).any():
        st.error('Hay partidos con acciones de un solo equipo. Incluye también los eventos del rival para analizar vulnerabilidad.');return
    st.success(f'Muestra CSV activa: {team} · {len(chosen)} partidos. Los filtros siguientes usan únicamente estos datos.')
    st.download_button('Descargar eventos normalizados',selected.to_csv(index=False).encode('utf-8-sig'),'efos_eventos_normalizados.csv','text/csv')
    render_defensive_module(selected,team,key_prefix='csv_'+digest)
