"""Generic end-to-end StatsBomb CSV -> EFOS Sprint 4 Coach Story.

Examples:
    python run_real.py --inputs data/raw/statsbomb/*.csv
    python run_real.py --inputs club_export.csv --team "Tigres UANL"
    python run_real.py --inputs league_export.csv --all-teams
"""
from __future__ import annotations
import argparse
import glob
from pathlib import Path
from run_sprint4 import run, run_all_teams


def expand(patterns):
    files=[]
    for p in patterns:
        hits=sorted(glob.glob(p)); files.extend(hits if hits else [p])
    return files


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--inputs',nargs='+',required=True)
    ap.add_argument('--team',default='auto')
    ap.add_argument('--all-teams',action='store_true')
    ap.add_argument('--expected-matches',type=int,default=None)
    ap.add_argument('--out',default='data/processed/sprint4_real')
    ap.add_argument('--export-event-tables',action='store_true')
    a=ap.parse_args()
    paths=expand(a.inputs)
    if len(paths)!=1:
        from ingestion.statsbomb_wide_csv import load_statsbomb_wide
        combined=Path(a.out)/'_combined_events.csv'; combined.parent.mkdir(parents=True,exist_ok=True)
        load_statsbomb_wide(paths).to_csv(combined,index=False); source=combined
    else:
        source=Path(paths[0])
    if a.all_teams:
        rr=run_all_teams(source,a.expected_matches,Path(a.out),export_event_tables=a.export_event_tables)
        print(f'Completado para {len(rr)} equipos -> {Path(a.out).resolve()}')
    else:
        r=run(source,a.team,a.expected_matches,Path(a.out),export_event_tables=a.export_event_tables)
        print(f"Equipo: {r['focal_team']} | ESI: {r['ESI']:.2f} | Resultados: {Path(a.out).resolve()}")
