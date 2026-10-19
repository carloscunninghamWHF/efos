#!/usr/bin/env python3
"""EFOS offline precompute worker: private CSV.GZ -> complete, versioned analysis.

Usage:
  python3 tools/precompute_supabase.py --list
  python3 tools/precompute_supabase.py --dataset-id UUID --team 'Guadalajara' [--apply]

Run on a trusted local computer, never inside public Streamlit UI. Only --apply
writes; all outputs are private and RLS-gated for authenticated org members.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui import supabase_bridge as SB
from ui.analysis_archive import FORMAT, archive, sha256_bytes
from ui.analysis_identity import signature, scope_key
from run_sprint4 import run as analyze

DEFAULT_URL = 'https://uvcqmxjjajgensjdidso.supabase.co'


def admin_config():
    url = os.environ.get('EFOS_SUPABASE_URL', DEFAULT_URL).strip().rstrip('/')
    key = os.environ.get('EFOS_SUPABASE_SECRET_KEY') or getpass('Clave secreta de Supabase (oculta): ')
    if not key or not (key.startswith('sb_secret_') or key.startswith('eyJ')):
        raise ValueError('Se requiere una clave secreta de backend, nunca una publishable/anon.')
    cfg = {'url': url, 'anon_key': key}
    return cfg, key


def records(cfg, token, table, fields='*', **filters):
    return SB._rest(cfg, token, table, fields,
                    {key: f'eq.{value}' for key, value in filters.items()})


def admin_json(cfg, token, path, *, method, obj):
    return SB._request(cfg, path, token, method=method, payload=obj,
                       extra_headers={'Prefer': 'resolution=merge-duplicates,return=representation'})


def process_team(cfg, key, dataset, rows, team, requested_matches=None, *, apply=False):
    allowed = {str(r['provider_match_id']) for r in rows if r['team_name'] == team}
    selected = sorted({i.strip() for i in requested_matches.split(',') if i.strip()}) if requested_matches else sorted(allowed)
    if not selected or not set(selected).issubset(allowed):
        raise ValueError('Selecciona únicamente partidos registrados para este equipo.')
    version, engine_hash = signature()
    scope = scope_key(selected)
    existing = records(cfg,key,'efos_analysis_runs','id,status',
                       dataset_id=dataset['id'],scope_key=scope,focal_team=team,
                       engine_version=version,parameters_sha256=engine_hash)
    if any(x['status']=='ready' for x in existing):
        print(f'{team}: análisis ya preparado, sin recálculo.',flush=True)
        return
    print(f"Equipo: {team} | Partidos: {len(selected)} | Versión: {version}",flush=True)
    if not apply:
        print('  Vista previa. Usa --apply para procesar y guardar.',flush=True)
        return
    sources = records(cfg,key,'efos_source_files',
                      'bucket,storage_path,file_sha256,source_bytes,status,dataset_id',dataset_id=dataset['id'])
    if not sources:
        raise ValueError('El dataset no tiene archivos originales registrados.')
    paths = []
    cache_dir = ROOT/'.runtime'/'worker_inputs'/dataset['id']
    for src in sources:
        paths.append(SB.cache_source(cfg,key,src,cache_dir))
    print('  Ejecutando motor táctico EFOS…',flush=True)
    result = analyze(paths, focal_team=team, match_ids=selected, outdir=None)
    compressed = archive(result)
    digest = sha256_bytes(compressed)
    print(f'  Snapshot: {len(compressed)/1024/1024:.2f} MiB; SHA256 {digest[:12]}…',flush=True)
    if existing and existing[0]['status']=='processing':
        raise ValueError('Este análisis ya se está procesando. Revisa su estado antes de reintentar.')
    if existing:
        run_id = existing[0]['id']
        admin_json(cfg,key,'/rest/v1/efos_analysis_runs?id=eq.'+run_id,
                   method='PATCH',obj={'status':'processing','error_message':None})
    else:
        payload={'dataset_id':dataset['id'],'scope_key':scope,'focal_team':team,
                 'engine_version':version,'parameters_sha256':engine_hash,'status':'processing',
                 'started_at':datetime.now(timezone.utc).isoformat(),
                 'summary':{'match_ids':selected,'format':FORMAT,'engine_hash':engine_hash}}
        response=admin_json(cfg,key,'/rest/v1/efos_analysis_runs',method='POST',obj=payload)
        if not isinstance(response,list) or not response:
            raise ValueError('No se pudo crear el registro del análisis.')
        run_id=response[0]['id']
    artifact_path=f'analysis/{dataset["id"]}/{run_id}/analysis.json.gz'
    try:
        SB._request(cfg, '/storage/v1/object/'+SB.BUCKET+'/'+quote(artifact_path,safe='/'),key,
                    method='POST',content_bytes=compressed,
                    extra_headers={'Content-Type':'application/gzip','x-upsert':'true'})
        admin_json(cfg,key,'/rest/v1/efos_analysis_artifacts?on_conflict=analysis_run_id%2Cstorage_path',
                   method='POST',obj={'analysis_run_id':run_id,'module':'shared','artifact_kind':'json',
                   'storage_path':artifact_path,'sha256':digest,'metadata':{'format':FORMAT,'bytes':len(compressed)}})
        admin_json(cfg,key,'/rest/v1/efos_analysis_runs?id=eq.'+run_id,method='PATCH',
                   obj={'status':'ready','summary':{'match_ids':selected,'events':len(result['events']),
                   'team':team,'format':FORMAT,'engine_hash':engine_hash},'error_message':None,
                   'finished_at':datetime.now(timezone.utc).isoformat()})
    except Exception as exc:
        try:
            admin_json(cfg,key,'/rest/v1/efos_analysis_runs?id=eq.'+run_id,method='PATCH',
                       obj={'status':'failed','error_message':str(exc)[:300]})
        except Exception:
            pass
        raise
    print(f'  LISTO: {team}. Análisis accesible para miembros autorizados.',flush=True)


def main():
    parser = argparse.ArgumentParser(description='EFOS: procesar análisis persistentes para Supabase')
    parser.add_argument('--list', action='store_true', help='Listar datasets del catálogo')
    parser.add_argument('--dataset-id', help='UUID del dataset en Supabase')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--team', help='Equipo exacto registrado')
    selection.add_argument('--all-teams', action='store_true', help='Todos los equipos del dataset; puede tardar horas')
    parser.add_argument('--matches', help='IDs separados por coma; requiere --team')
    parser.add_argument('--apply', action='store_true', help='Ejecutar y guardar análisis persistentes')
    args = parser.parse_args()
    if not args.list and (not args.dataset_id or not (args.team or args.all_teams)):
        parser.error('Usa --list o --dataset-id con --team o --all-teams')
    if args.matches and not args.team:
        parser.error('--matches requiere --team')
    cfg, key = admin_config()
    datasets = records(cfg, key, 'efos_datasets',
                       'id,organization_id,competition,season,period,team,events_count,matches_count,status')
    if args.list:
        for d in datasets:
            print(f"{d['id']} | {d['competition']} {d['season']} {d['period']} | {d['matches_count']} partidos")
        return
    dataset = next((d for d in datasets if d['id'] == args.dataset_id), None)
    if dataset is None:
        raise ValueError('El dataset solicitado no existe.')
    rows = records(cfg,key,'efos_catalog_match_teams',
                   'dataset_id,team_name,provider_match_id', dataset_id=args.dataset_id)
    options = sorted({r['team_name'] for r in rows})
    teams = options if args.all_teams else [args.team]
    missing = [team for team in teams if team not in options]
    if missing:
        raise ValueError('Equipo no encontrado. Disponibles: '+', '.join(options))
    print(f"Dataset: {dataset['competition']} {dataset['season']} ({dataset['period']})",flush=True)
    completed = 0
    for index, team in enumerate(teams,1):
        print(f'[{index}/{len(teams)}] ',end='',flush=True)
        try:
            process_team(cfg,key,dataset,rows,team,args.matches,apply=args.apply)
            completed += 1
        except Exception as exc:
            print(f'  ERROR en {team}: {exc}',file=sys.stderr,flush=True)
            if not args.all_teams:
                raise
    print(f'Finalizado: {completed}/{len(teams)} equipos sin error.',flush=True)
    if completed != len(teams):
        raise ValueError('Algunos equipos no se procesaron correctamente; revisa los mensajes anteriores.')


if __name__ == '__main__':
    try:
        main()
    except (SB.CloudError, OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
