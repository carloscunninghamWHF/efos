"""EFOS v0.3 Sprint 3 — Intelligence Engine runner."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from run_sprint2 import run as run_sprint2
from metrics.esi import compute_dimensions, compute_esi, esi_by_context
from intelligence.match_windows import compute_match_windows
from intelligence.dtc import build_dtc
from players.lap import compute_lap
from coach_story.principles import detect_principles

def run(path:Path,focal_team:str,expected_matches:int|None=None,outdir:Path|None=None):
    base=run_sprint2(path,focal_team,expected_matches,None)
    ev=base['events']; tr=base['transitions']
    dims=compute_dimensions(ev,focal_team,tr); esi=compute_esi(dims)
    context_esi=esi_by_context(ev,focal_team,tr)
    windows=compute_match_windows(ev,focal_team,tr)
    states,dtc=build_dtc(windows)
    lap=compute_lap(ev,focal_team)
    principles=detect_principles(ev,focal_team,tr)
    result={**base,'esi_dimensions':dims,'ESI':esi,'esi_by_context':context_esi,'match_windows':windows,'dtc_states':states,'dtc_matrix':dtc,'lap':lap,'principles':principles}
    if outdir:
        outdir.mkdir(parents=True,exist_ok=True)
        pd.DataFrame([{**dims,'ESI':esi}]).to_csv(outdir/'esi_overall.csv',index=False)
        context_esi.to_csv(outdir/'esi_by_context.csv',index=False)
        windows.to_csv(outdir/'match_windows.csv',index=False)
        states.to_csv(outdir/'dtc_states.csv',index=False)
        dtc.to_csv(outdir/'dtc_matrix.csv',index=False)
        lap.to_csv(outdir/'lap_players.csv',index=False)
        principles.to_csv(outdir/'coach_principle_candidates.csv',index=False)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--events',required=True); ap.add_argument('--team',required=True); ap.add_argument('--expected-matches',type=int); ap.add_argument('--out',default='data/processed/sprint3'); a=ap.parse_args()
    r=run(Path(a.events),a.team,a.expected_matches,Path(a.out))
    print('ESI:',r['ESI'],r['esi_dimensions']); print('Principles:'); print(r['principles'].to_string(index=False))
