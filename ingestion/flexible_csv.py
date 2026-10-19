"""Explicit CSV mapping and capability checks; never infer missing possessions."""
import io
import pandas as pd

ALIASES={
 'pass_recipient_name':['pass_recipient_name','pass_recipient','receptor'],
 'under_pressure':['under_pressure','bajo_presion'],'pass_switch':['pass_switch','cambio_orientacion'],
 'pass_cross':['pass_cross','centro'],'obv_total_net':['obv_total_net'],
 'possession_directness':['possession_directness'],'is_transition':['is_transition'],
 'is_controlled_possession':['is_controlled_possession'],'score_state':['score_state'],
 'team':['team','team_name','equipo'],'event_type':['event_type','event_type_name','type','evento','accion'],
 'match_id':['match_id','partido'],'period':['period','periodo'],'index':['index','idx','orden'],
 'possession':['possession','posesion'],'possession_team':['possession_team','possession_team_name','equipo_posesion'],
 'minute':['minute','minuto'],'second':['second','segundo'],'event_id':['event_id','id'],
 'player':['player','player_name','jugador'],'location_x':['location_x','x'], 'location_y':['location_y','y'],
 'end_location_x':['end_location_x','end_x'],'end_location_y':['end_location_y','end_y'],
 'counterpress':['counterpress','contrapresion'],'statsbomb_xg':['statsbomb_xg','shot_statsbomb_xg','xg'],
 'play_pattern_name':['play_pattern_name','play_pattern','patron'],
 'type_name':['type_name','subtipo'],'outcome_name':['outcome_name','resultado'],
 'shot_outcome':['shot_outcome','shot_outcome_name'],'pass_outcome':['pass_outcome','pass_outcome_name']}
EVENTS=['Pass','Carry','Shot','Pressure','Ball Recovery','Interception','Duel','Block','Clearance',
 'Foul Committed','Foul Won','Dribble','Dribbled Past','Dispossessed','Miscontrol','Error',
 'Ball Receipt*','Goal Keeper','50/50','Shield','Offside','Half End','Half Start','Starting XI',
 'Bad Behaviour','Player Off','Player On','Referee Ball-Drop','Substitution','Tactical Shift','Injury Stoppage','Own Goal For','Own Goal Against','Ball Out']


def read_flexible(raw,encoding='auto',separator='auto'):
    encodings=['utf-8-sig','cp1252','latin-1'] if encoding=='auto' else [encoding]
    for enc in encodings:
        try: text=raw.decode(enc);break
        except UnicodeDecodeError: continue
    else: raise ValueError('No se pudo decodificar el archivo; selecciona su codificación.')
    sep=None if separator=='auto' else separator
    df=pd.read_csv(io.StringIO(text),sep=sep,engine='python')
    if df.empty: raise ValueError('El archivo no contiene filas.')
    return df,enc


def suggest_mapping(df):
    return {field:next((c for c in names if c in df.columns),None) for field,names in ALIASES.items()}


def adapt(df,mapping,event_map=None,length=120,width=80,orientation='actor',direction=None,flip_y=False):
    selected={k:v for k,v in mapping.items() if v}
    if len(set(selected.values()))!=len(selected): raise ValueError('Una columna no puede representar dos campos distintos.')
    out=pd.DataFrame({k:df[v] for k,v in selected.items()})
    if 'event_type' in out:out['event_type']=out.event_type.replace({'Carries':'Carry'})
    if event_map and 'event_type' in out: out['event_type']=out.event_type.map(lambda x:event_map.get(str(x),x))
    for col in ['period','index','possession','minute','second','location_x','location_y','end_location_x','end_location_y','statsbomb_xg']:
        if col in out: out[col]=pd.to_numeric(out[col],errors='coerce')
    if length<=0 or width<=0: raise ValueError('Dimensiones del campo inválidas.')
    for col in ['location_x','end_location_x']:
        if col in out:out[col]=out[col]*120/length
    for col in ['location_y','end_location_y']:
        if col in out:out[col]=out[col]*80/width
    if flip_y:
        for col in ['location_y','end_location_y']:
            if col in out:out[col]=80-out[col]
    if orientation=='fixed':
        if direction is None or not df[direction].astype(str).isin(['1','-1']).all():
            raise ValueError('Coordenadas fijas requieren una columna por evento: 1 ataca hacia +X, -1 hacia -X.')
        reverse=df[direction].astype(str).eq('-1')
        for col,maximum in [('location_x',120),('end_location_x',120),('location_y',80),('end_location_y',80)]:
            if col in out:out.loc[reverse,col]=maximum-out.loc[reverse,col]
    exact_duplicates=0
    if {'match_id','period','index'}<=set(out):
        exact_duplicates=int(out.duplicated().sum())
        out=out.drop_duplicates().copy()
    invalid_xy=0
    for x,y in [('location_x','location_y'),('end_location_x','end_location_y')]:
        if {x,y}<=set(out):
            invalid=(out[x].notna()&~out[x].between(0,120))|(out[y].notna()&~out[y].between(0,80))
            invalid_xy+=int(invalid.sum());out.loc[invalid,[x,y]]=float('nan')
    if 'match_id' in out:out['match_id']=out.match_id.astype('string')
    required=['match_id','period','index','possession','team','possession_team','event_type','minute','second','play_pattern_name']
    missing=[c for c in required if c not in out]
    invalid=pd.Series(False,index=out.index)
    for c in required:
        if c in out: invalid |= out[c].isna()|out[c].astype(str).str.strip().eq('')
    unknown=sorted(set(out.event_type.dropna().astype(str))-set(EVENTS)) if 'event_type' in out else []
    duplicates=int(out.duplicated(['match_id','period','index']).sum()) if {'match_id','period','index'}<=set(out) else 0
    # Missing outcome semantics must not make unknown passes appear completed.
    outcome_ok='outcome_name' in out or 'pass_outcome' in out
    if 'outcome_name' not in out and 'pass_outcome' in out:out['outcome_name']=out.pass_outcome
    if 'outcome_name' in out and 'shot_outcome' in out:
        mask=out.event_type.eq('Shot');out.loc[mask,'outcome_name']=out.loc[mask,'shot_outcome']
    # Reject malformed clocks and ordering rather than fabricate chronology.
    for c in ['period','index','possession','minute','second']:
        if c in out:
            invalid |= out[c].isna() | out[c].lt(0) | out[c].mod(1).ne(0)
    if 'second' in out: invalid |= out.second.ge(60)
    if 'period' in out: invalid |= ~out.period.between(1,5)
    out=out.loc[~invalid].copy()
    spatial={'location_x','location_y','end_location_x','end_location_y'}<=set(out)
    if not missing and not duplicates and not unknown and outcome_ok and spatial:
        ready=len(out)>0
    else:ready=False
    # Local row identifiers are explicit provenance, not provider IDs.
    if 'event_id' not in out:out['event_id']=['csv-row-'+str(i+2) for i in out.index]
    else:
        absent=out.event_id.isna()|out.event_id.astype(str).str.strip().eq('')
        out.loc[absent,'event_id']=['csv-row-'+str(i+2) for i in out.index[absent]]
    report=dict(rows=len(df),usable=len(out),excluded=int(invalid.sum()),exact_duplicates_removed=exact_duplicates,invalid_coordinates=invalid_xy,
        missing=missing,unknown_events=unknown,duplicate_order=duplicates,defense_ready=ready,
        spatial=spatial,outcome_available=outcome_ok,counterpress_available='counterpress' in out,
        xg_available='statsbomb_xg' in out,teams=sorted(out.team.dropna().astype(str).unique()) if 'team' in out else [])
    return out,report
