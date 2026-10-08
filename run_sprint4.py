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
from players.lap import compute_lap
from coach_story.principles import detect_principles
from coach_story.story_builder import build_coach_story
from coach_story.tactical_framework import extract_tactical_framework
from coach_story.report_generator import render_coach_story_md
from coach_story.pdf_report import build_coach_story_pdf
from behavior.tactical import tactical_summary
from ingestion.input_adapter import load_event_csv, load_event_csvs
from intelligence.team_scope import resolve_focal_team, team_coverage, slugify_team
from coach_story.coach_fit import style_by_match, style_profile, coach_fit
from coach_story.coach_profile import build_coach_profile, render_coach_profile_md, _starters
from coach_story.football_report import build_football_report, render_football_report_md
from coach_story.football_pdf import build_football_pdf
from config_loader import get_coach_archetypes


def run(path, focal_team:str|None=None, expected_matches:int|None=None, outdir:Path|None=None, frames360_path:Path|None=None, export_event_tables:bool=False):
    paths = list(path) if isinstance(path, (list, tuple, set)) else [path]
    input_events,input_meta = load_event_csvs(paths) if len(paths) > 1 else load_event_csv(paths[0])
    focal_team,team_resolution=resolve_focal_team(input_events,focal_team)
    # expected_matches is validation-only. If omitted, EFOS uses all matches
    # available for the selected team without assuming a league/season length.
    base=run_sprint2_df(input_events,focal_team,expected_matches,None); ev=base['events']; tr=base['transitions']
    frames=load_statsbomb_360(frames360_path)
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
            'tactical_summary':summary,'tactical_framework':tactical_framework,'transition_response_rate':transition_rate,'adaptation_score':adaptation_score,'frames360_loaded':len(frames)}
    coach_story,evidence=build_coach_story(result,focal_team)
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
    result.update({'style_profile':style,'coach_fit':fit,'coach_identity':coach_identity,'football_report':football})
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

