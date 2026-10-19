"""EFOS v0.4 Sprint 4 — Pressure & Constraint Engine runner.
Completes roadmap points 1–7 while preserving Sprint 3 compatibility.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from run_sprint2 import run_df as run_sprint2_df
from ingestion.statsbomb_360 import load_statsbomb_360
from metrics.esi import compute_dimensions,compute_esi,esi_by_context
from metrics.hps import compute_hps
from metrics.pressure import summarize_pressure_context
from intelligence.pressure_context import build_pressure_context
from intelligence.trap_detection import detect_traps
from intelligence.match_windows import compute_match_windows
from intelligence.dtc import build_dtc
from intelligence.cts import compute_cts, compute_adaptation_score
from intelligence.organized_defense_story import build_defensive_story
from intelligence.smart_defense_tactics import analyze_smart_defense, configured_defensive_settings
from intelligence.defensive_open_play import analyze as analyze_open_play_defense, STATES as OPEN_PLAY_STATES
from intelligence.corner_engine import analyze_corners
from intelligence import organized_attack as _OA
from intelligence.offensive_story import build_offensive_story, coach_claims
from intelligence.set_piece_patterns import _corner_config
from intelligence.set_piece_patterns import analyze_set_pieces, KINDS, SCOPE, narrative_findings, context_finding
from players.lap import compute_lap
from coach_story.principles import detect_principles
from coach_story.story_builder import build_coach_story
from interpretation.tactical_reasoning import build_tactical_reasoning
from intelligence.transition_story import analyze_transitions
from coach_story.tactical_framework import extract_tactical_framework
from coach_story.report_generator import render_coach_story_md
from coach_story.pdf_report import build_coach_story_pdf
from behavior.tactical import tactical_summary
from ingestion.input_adapter import load_event_csv, load_event_csvs
from ingestion.statsbomb_auxiliary import extract_statsbomb_auxiliary
from intelligence.team_scope import resolve_focal_team, team_coverage, slugify_team
from coach_story.coach_fit import style_by_match, style_profile, coach_fit
from coach_story.coach_profile import build_coach_profile, render_coach_profile_md, _starters
from coach_story.football_report import build_football_report, render_football_report_md
from coach_story.football_pdf import build_football_pdf
from config_loader import get_coach_archetypes


def run(path, focal_team:str|None=None, expected_matches:int|None=None, outdir:Path|None=None, frames360_path:Path|None=None, export_event_tables:bool=False, match_ids=None):
    paths = list(path) if isinstance(path, (list, tuple, set)) else [path]
    input_events,input_meta = load_event_csvs(paths) if len(paths) > 1 else load_event_csv(paths[0])
    if match_ids is not None:
        selected={str(match) for match in match_ids}
        if not selected:
            raise ValueError("Debes seleccionar al menos un partido para analizar.")
        filtered=input_events[input_events["match_id"].astype(str).isin(selected)].copy()
        missing=selected-set(filtered["match_id"].astype(str).unique())
        if missing:
            raise ValueError(f"Los partidos solicitados no aparecen en el CSV: {sorted(missing)}")
        input_events=filtered.reset_index(drop=True)
        input_meta={**input_meta, "available_matches_before_filter":input_meta.get("n_matches_loaded"),
                    "n_matches_loaded":int(input_events["match_id"].nunique()),
                    "n_events_loaded":len(input_events), "selected_match_ids":sorted(selected)}
    focal_team,team_resolution=resolve_focal_team(input_events,focal_team)
    # expected_matches is validation-only. If omitted, EFOS uses all matches
    # available for the selected team without assuming a league/season length.
    base=run_sprint2_df(input_events,focal_team,expected_matches,None); ev=base['events']; tr=base['transitions']
    frames=load_statsbomb_360(frames360_path)
    # The wide export may contain separate shot-time freeze frame and lineup
    # rows. Preserve these by event ID instead of confusing them with 360.
    wide_paths=[p for p in paths if str(p).lower().endswith(('.csv', '.csv.gz'))]
    if 'STATSBOMB_WIDE' in input_meta.get('source_formats', [input_meta.get('format')]):
        from ingestion.input_adapter import inspect_csv_schema
        wide_paths=[p for p in paths if inspect_csv_schema(p)['format']=='STATSBOMB_WIDE']
        shot_frames,formation_rows=extract_statsbomb_auxiliary(wide_paths, match_ids)
    else:
        shot_frames,formation_rows=pd.DataFrame(),pd.DataFrame()
    input_meta={**input_meta, 'shot_freeze_frame_rows':len(shot_frames),
                'shot_freeze_frame_events':int(shot_frames.event_id.nunique()) if not shot_frames.empty else 0,
                'formation_rows':len(formation_rows)}
    sp_required={'match_id','period','possession','team','event_type','type_name','timestamp_seconds'}
    if sp_required.issubset(ev.columns):
        corner_sequences,corner_summary,corner_claims=analyze_corners(ev,focal_team,frames360=frames,config=_corner_config())
        set_piece_sequences,set_piece_summary,set_piece_claims=analyze_set_pieces(ev,focal_team,corner_sequences)
    else:
        corner_sequences=pd.DataFrame(); set_piece_sequences=pd.DataFrame()
        corner_summary={'status':'NOT_COMPUTABLE','missing':sorted(sp_required.difference(ev.columns)),'sides':{}}
        set_piece_summary={'status':'NOT_COMPUTABLE','missing':sorted(sp_required.difference(ev.columns)),'by_kind':{}}
        corner_claims=[];set_piece_claims=[]
    pc=build_pressure_context(ev,frames)
    hps,hps_actions,hps_meta=compute_hps(ev,focal_team,pc)
    dims=compute_dimensions(ev,focal_team,tr,pc); dims['HPS']=hps; esi=compute_esi(dims)
    context_esi=esi_by_context(ev,focal_team,tr,pc)
    windows=compute_match_windows(ev,focal_team,tr); states,dtc=build_dtc(windows)
    traps,trap_metrics=detect_traps(ev,focal_team,pc)
    pressure_summary=summarize_pressure_context(pc,focal_team,'faced')
    pressure_imposed_summary=summarize_pressure_context(pc,focal_team,'imposed')
    lap=compute_lap(ev,focal_team)
    principles=detect_principles(ev,focal_team,tr,pc,traps)
    summary=tactical_summary(ev,focal_team)
    tactical_framework=extract_tactical_framework(ev,focal_team)
    transition_rate=float(tr[tr.team_lost.eq(focal_team)].response_within_5s.mean()) if len(tr) and len(tr[tr.team_lost.eq(focal_team)]) else 0.0
    adaptation_score=compute_adaptation_score(states)
    cts=compute_cts(summary,transition_rate,trap_metrics,hps,pressure_summary,adaptation_score=adaptation_score)
    result={**base,'focal_team':focal_team,'input_metadata':input_meta,'team_resolution':team_resolution,
            'team_coverage':team_coverage(input_events),'pressure_context':pc,'pressure_summary':pressure_summary,
            'pressure_imposed_summary':pressure_imposed_summary,'hps_actions':hps_actions,'hps_meta':hps_meta,
            'esi_dimensions':dims,'ESI':esi,'esi_by_context':context_esi,'match_windows':windows,'dtc_states':states,
            'dtc_matrix':dtc,'traps':traps,'trap_metrics':trap_metrics,'cts':cts,'lap':lap,'principles':principles,
            'tactical_summary':summary,'tactical_framework':tactical_framework,'transition_response_rate':transition_rate,'adaptation_score':adaptation_score,'frames360_loaded':len(frames),
            'shot_freeze_frames':shot_frames,'formation_lineups':formation_rows,
            'corner_sequences':corner_sequences,'corner_summary':corner_summary,
            'set_piece_sequences':set_piece_sequences,'set_piece_summary':set_piece_summary}
    defensive_story=build_defensive_story(ev,focal_team)
    sd_possessions,sd_players,sd_summary,sd_claims=analyze_smart_defense(ev,focal_team,configured_defensive_settings())
    # v0.4.13: open-play-only scenarios, distinct from v0.4.12 full opposition-attack engine.
    open_play_need={'match_id','period','index','possession','team','possession_team','event_type'}
    if open_play_need.issubset(ev.columns) and ev['possession_team'].notna().any():
        open_play_possessions,open_play_events=analyze_open_play_defense(ev,focal_team)
    else:
        open_play_possessions=pd.DataFrame();open_play_events=pd.DataFrame()
    # v0.4.19: one canonical offensive sample and story shared with attack UX and Coach Story.
    try:
        offensive_events=_OA.prepare_attack(ev,focal_team)
        offensive_possessions=_OA.possession_table(offensive_events)
        offensive_story=build_offensive_story(offensive_events,offensive_possessions)
        result['organized_attack_data']=(offensive_events,offensive_possessions)
    except (ValueError,KeyError,TypeError) as exc:
        offensive_story={'status':'NOT_COMPUTABLE','overview':'Ataque no evaluable con las columnas disponibles.',
                         'reason':str(exc),'n_possessions':0,'n_matches':0,'insights':[]}
    result['offensive_story']=offensive_story
    result['defensive_open_play_possessions']=open_play_possessions
    result['defensive_open_play_events']=open_play_events
    # Freeze frames are kept only when actually provided; never synthesize tracking.
    result['defensive_360_frames']=frames
    result["defensive_story"]=defensive_story
    result["smart_defense_possessions"]=sd_possessions
    result["smart_defense_players"]=sd_players
    result["smart_defense_summary"]=sd_summary
    coach_story,evidence=build_coach_story(result,focal_team)
    coach_story["defensive_story"]=defensive_story
    # JSON-compatible public digest: identifiers of specific events stay in Evidence Layer.
    coach_story['offensive_story']={
        'overview':offensive_story.get('overview'),
        'status':offensive_story.get('status'),
        'n_possessions':offensive_story.get('n_possessions',0),
        'n_matches':offensive_story.get('n_matches',0),
        'insights':[{k:v for k,v in item.items() if k!='keys'}
                    for item in offensive_story.get('insights',[])],
        'limitations':offensive_story.get('limitations',[]),
    }
    evidence['claims'].extend(coach_claims(offensive_story))
    coach_story["smart_defense_tactics"]=sd_summary
    evidence["claims"].extend(defensive_story["claims"]+sd_claims)
    coach_story['corner_sequence']=corner_summary
    coach_story['set_piece_story']=set_piece_summary
    evidence['claims'].extend(corner_claims+set_piece_claims)
    coach_story['analysis_metadata']={
        'focal_team': focal_team,
        'team_selection_mode': team_resolution['mode'],
        'input_format': input_meta['format'],
        'source_files': input_meta.get('source_files', [Path(paths[0]).name]),
        'files_loaded': int(input_meta.get('n_files_loaded', 1)),
        'matches_analyzed': int(ev.loc[ev.team.eq(focal_team),'match_id'].nunique()),
        'events_in_dataset': int(len(ev)),
        'team_events': int(ev.team.eq(focal_team).sum()),
        'frames360_loaded': int(len(frames)),
        'formula_profile': 'EFOS_v0.4.7_FootballNative_UI',
    }
    # Capa de fútbol: perfil del entrenador e informe para cuerpo técnico (lenguaje de vestuario)
    style=style_profile(style_by_match(ev,focal_team)); fit=coach_fit(style,get_coach_archetypes())
    coach_identity=build_coach_profile(ev,focal_team,style,fit,transition_rate)
    football=build_football_report(ev,focal_team,coach_identity,fit,dims,esi,lap,states,transition_rate,_starters(ev,focal_team))
    coach_story['coach_identity']={k:v for k,v in coach_identity.items()}
    evidence['claims'].append({'id':'coach_identity_1','section':'coach_identity','claim':coach_identity['textos']['retrato'],
        'evidence':{'dibujo_principal':coach_identity['estructura'].get('dibujo_principal'),'por_marcador':coach_identity['por_marcador']},
        'n':int(coach_identity['partidos']),'source':'COACH_PROFILE_ENGINE','confidence':'MEDIUM',
        'limitation':'Describe al equipo bajo este cuerpo técnico; no separa decisiones del entrenador de la calidad de los jugadores.'})
    # Only sample-supported findings are inserted in the coach-facing report.
    if not set_piece_sequences.empty:
        story=[]
        for kind in KINDS:
            for side in SCOPE:
                observed=[f['detail'] for f in narrative_findings(set_piece_sequences,side,kind)
                          if f.get('status')=='observed']
                if observed:
                    story.append(f"{kind} ({side.lower()}): " + " ".join(observed[:2]))
        if story:
            football['textos']['balon_parado'] += " " + " ".join(story[:4])
    if offensive_story.get('n_possessions',0):
        # Coach-facing description, consistent with the same underlying sequence table.
        football['textos']['ataque_organizado'] += ' ' + offensive_story['overview']
    if sd_claims:
        # Descriptive comparisons only. They do not demonstrate a formation or a coach's intent.
        football['textos']['defensa_organizada'] += " " + " ".join(c['claim'] for c in sd_claims[:2])
    result.update({'style_profile':style,'coach_fit':fit,'coach_identity':coach_identity,'football_report':football})
    # Same strict definition used by the transition chapters shown in attack/defense.
    result['verified_transitions']=analyze_transitions(ev,focal_team)
    result['tactical_reasoning']=build_tactical_reasoning(result)
    result['coach_story']=coach_story; result['evidence']=evidence
    if outdir:
        outdir.mkdir(parents=True,exist_ok=True)
        pc_cols=[c for c in ['match_id','event_id','index','team','possession','timestamp_seconds','event_type','location_x','location_y','under_pressure','direct_pressure','nearby_pressure','boundary_constraint','defensive_responsibility','control_constraint','lane_closure','reachability','tti','pci','pressure_source'] if c in pc.columns]
        hps_cols=[c for c in ['match_id','event_id','team','possession','timestamp_seconds','event_type','pci','pressure_source','retention_stability','progression_stability','value_preservation','decision_stability_hps','pressure_weight'] if c in hps_actions.columns]
        if export_event_tables:
            pc[pc_cols].to_csv(outdir/'pressure_context_events.csv',index=False)
            hps_actions[hps_cols].to_csv(outdir/'hps_actions.csv',index=False)
        pd.DataFrame([{**dims,'ESI':esi,**{f'hps_{k}':v for k,v in hps_meta.items()}}]).to_csv(outdir/'esi_overall.csv',index=False)
        context_esi.to_csv(outdir/'esi_by_context.csv',index=False); windows.to_csv(outdir/'match_windows.csv',index=False)
        states.to_csv(outdir/'dtc_states.csv',index=False); dtc.to_csv(outdir/'dtc_matrix.csv',index=False)
        traps.to_csv(outdir/'defensive_traps.csv',index=False); pd.DataFrame([trap_metrics]).to_csv(outdir/'trap_metrics.csv',index=False)
        pd.DataFrame([cts]).to_csv(outdir/'coach_tactical_signature.csv',index=False); lap.to_csv(outdir/'lap_players.csv',index=False)
        principles.to_csv(outdir/'coach_principle_candidates.csv',index=False)
        pd.DataFrame([{**dims,'ESI':esi,'mean_PCI':pressure_summary.get('mean_pci',0.0),**trap_metrics}]).to_csv(outdir/'metrics_summary.csv',index=False)
        result['team_coverage'].to_csv(outdir/'team_coverage.csv',index=False)
        schema_report={**input_meta,'resolved_team':focal_team,'team_resolution':team_resolution,'expected_matches_validation':expected_matches}
        with open(outdir/'input_profile.json','w',encoding='utf-8') as f: json.dump(schema_report,f,ensure_ascii=False,indent=2)
        with open(outdir/'defensive_story.json','w',encoding='utf-8') as f: json.dump(defensive_story,f,ensure_ascii=False,indent=2)
        open_play_possessions.to_csv(outdir/'defensive_open_play_possessions.csv',index=False)
        sd_possessions.to_csv(outdir/'smart_defense_possessions.csv',index=False)
        sd_players.to_csv(outdir/'smart_defense_players.csv',index=False)
        with open(outdir/'smart_defense_summary.json','w',encoding='utf-8') as f: json.dump(sd_summary,f,ensure_ascii=False,indent=2)
        corner_sequences.to_csv(outdir/'corner_sequences.csv',index=False)
        set_piece_sequences.to_csv(outdir/'set_piece_sequences.csv',index=False)
        with open(outdir/'corner_summary.json','w',encoding='utf-8') as f: json.dump(corner_summary,f,ensure_ascii=False,indent=2)
        with open(outdir/'set_piece_summary.json','w',encoding='utf-8') as f: json.dump(set_piece_summary,f,ensure_ascii=False,indent=2)
        # Audit-ready diagnosis: exact denominators and contexts, never conceptual bibliographies.
        reason=result['tactical_reasoning']
        payload={k:v for k,v in reason.items() if k not in ('lane_table','defense_table')}
        with open(outdir/'diagnostico_conectado.json','w',encoding='utf-8') as f:
            json.dump(payload,f,ensure_ascii=False,indent=2)
        reason['lane_table'].to_csv(outdir/'diagnostico_carriles.csv',index=False)
        reason['defense_table'].to_csv(outdir/'diagnostico_escenarios_rivales.csv',index=False)
        with open(outdir/'offensive_story.json','w',encoding='utf-8') as f:
            json.dump(coach_story['offensive_story'],f,ensure_ascii=False,indent=2)
        with open(outdir/'coach_story.json','w',encoding='utf-8') as f: json.dump(coach_story,f,ensure_ascii=False,indent=2)
        with open(outdir/'tactical_framework.json','w',encoding='utf-8') as f: json.dump(tactical_framework,f,ensure_ascii=False,indent=2)
        with open(outdir/'evidence.json','w',encoding='utf-8') as f: json.dump(evidence,f,ensure_ascii=False,indent=2)
        (outdir/'coach_story.md').write_text(render_coach_story_md(coach_story,evidence),encoding='utf-8')
        style.to_csv(outdir/'style_profile.csv',index=False); fit.to_csv(outdir/'coach_fit.csv',index=False)
        with open(outdir/'coach_profile.json','w',encoding='utf-8') as f: json.dump(coach_identity,f,ensure_ascii=False,indent=2,default=float)
        (outdir/'perfil_entrenador.md').write_text(render_coach_profile_md(coach_identity),encoding='utf-8')
        (outdir/'informe_cuerpo_tecnico.md').write_text(render_football_report_md(football),encoding='utf-8')
        football['per_match'].to_csv(outdir/'partidos.csv',index=False); football['clips'].to_csv(outdir/'clips_sugeridos.csv',index=False)
        football['posiciones'].to_csv(outdir/'posiciones_medias.csv',index=False)
        fp=outdir/'informe_cuerpo_tecnico.pdf'; build_football_pdf(football,fp); result['football_pdf_path']=str(fp)
        pdf_path=outdir/'coach_story.pdf'
        build_coach_story_pdf(result,pdf_path)
        result['coach_story_pdf_path']=str(pdf_path)
    return result


def run_all_teams(path, expected_matches:int|None=None, outdir:Path|None=None, frames360_path:Path|None=None, export_event_tables:bool=False, min_matches:int=1):
    paths = list(path) if isinstance(path, (list, tuple, set)) else [path]
    events,_ = load_event_csvs(paths) if len(paths) > 1 else load_event_csv(paths[0])
    cov=team_coverage(events)
    selected=cov[cov.matches.ge(int(min_matches))].team.tolist()
    results={}
    for team in selected:
        team_out=(outdir/slugify_team(team)) if outdir else None
        results[team]=run(paths,team,expected_matches,team_out,frames360_path,export_event_tables)
    return results

if __name__=='__main__':
    ap=argparse.ArgumentParser(description='EFOS Sprint 4 — team-agnostic Coach Story engine')
    ap.add_argument('--events',required=True,help='EFOS normalized CSV or StatsBomb wide CSV')
    ap.add_argument('--team',default='auto',help="Focal team name. Default 'auto' detects a team-centric dataset.")
    ap.add_argument('--all-teams',action='store_true',help='Run the same EFOS pipeline for every team in the CSV')
    ap.add_argument('--min-matches',type=int,default=1,help='Minimum matches for --all-teams')
    ap.add_argument('--expected-matches',type=int,default=None,help='Optional validation gate; never assumed automatically')
    ap.add_argument('--360',dest='frames360'); ap.add_argument('--out',default='data/processed/sprint4')
    ap.add_argument('--export-event-tables',action='store_true',help='Export large event-level PCI/HPS CSV tables')
    a=ap.parse_args(); out=Path(a.out)
    if a.all_teams:
        rr=run_all_teams(Path(a.events),a.expected_matches,out,Path(a.frames360) if a.frames360 else None,a.export_event_tables,a.min_matches)
        print(f"EFOS completado para {len(rr)} equipos. Resultados: {out}")
    else:
        r=run(Path(a.events),a.team,a.expected_matches,out,Path(a.frames360) if a.frames360 else None,a.export_event_tables)
        print('Team:',r['focal_team'],'| selection:',r['team_resolution']['mode'],'| input:',r['input_metadata']['format'])
        print('ESI:',round(r['ESI'],2),r['esi_dimensions']); print('HPS v2:',r['hps_meta']); print('Traps:',r['trap_metrics']); print('CTS:',r['cts'])
        print('Coach Story:', str(out/'coach_story.md'))
        print('Informe para cuerpo técnico:', str(out/'informe_cuerpo_tecnico.pdf'))
        if len(r['principles']): print(r['principles'].to_string(index=False))

