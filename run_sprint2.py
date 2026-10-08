"""EFOS v0.2 Sprint 2 runner over a normalized events CSV."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from ingestion.validation import deduplicate_events, validate_events
from ingestion.input_adapter import load_event_csv
from context.game_context import add_score_state
from objects.possessions import build_possessions
from objects.sequences import build_sequences
from objects.transitions import detect_transitions
from behavior.tactical import tactical_summary
from intelligence.cts import compute_cts

def run_df(df: pd.DataFrame, focal_team: str, expected_matches: int | None=None, outdir: Path|None=None):
    df=df.copy()
    teams=set(df["team"].dropna().astype(str).unique()) if "team" in df else set()
    if focal_team not in teams:
        raise ValueError(f"El equipo '{focal_team}' no aparece en los datos. Equipos disponibles: {sorted(teams)}")
    df, dedup=deduplicate_events(df)
    validation=validate_events(df, expected_matches)
    if any(x in validation['issues'] for x in ['duplicate_event_ids','location_x_out_of_bounds','location_y_out_of_bounds']):
        raise ValueError(f"Data integrity gate failed: {validation['issues']}")
    ctx=add_score_state(df,focal_team)
    seq=build_sequences(ctx)
    poss=build_possessions(seq)
    tr=detect_transitions(seq,5.0)
    sm=tactical_summary(seq,focal_team)
    team_losses=tr[tr.team_lost==focal_team] if not tr.empty else tr
    transition_rate=float(team_losses.response_within_5s.mean()) if len(team_losses) else 0.0
    cts=compute_cts(sm,transition_rate)
    result={"validation":validation,"dedup":dedup,"summary":sm,"cts":cts,"possessions":poss,"transitions":tr,"events":seq}
    if outdir:
        outdir.mkdir(parents=True,exist_ok=True)
        seq.to_csv(outdir/'events_context.csv',index=False)
        poss.to_csv(outdir/'possessions.csv',index=False)
        tr.to_csv(outdir/'transitions.csv',index=False)
        pd.DataFrame([sm]).to_csv(outdir/'tactical_summary.csv',index=False)
        pd.DataFrame([cts]).to_csv(outdir/'cts_baseline.csv',index=False)
    return result


def run(path: Path, focal_team: str, expected_matches: int | None=None, outdir: Path|None=None):
    df,_ = load_event_csv(path)
    return run_df(df, focal_team, expected_matches, outdir)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--events',required=True)
    ap.add_argument('--team',required=True)
    ap.add_argument('--expected-matches',type=int,default=None)
    ap.add_argument('--out',default='data/processed/sprint2')
    a=ap.parse_args()
    r=run(Path(a.events),a.team,a.expected_matches,Path(a.out))
    print('Validation:',r['validation'])
    print('Dedup:',r['dedup'])
    print('Tactical summary:',r['summary'])
    print('CTS baseline:',r['cts'])
