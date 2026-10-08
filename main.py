"""
main.py — EFOS Prototype v0.1
------------------------------
Sprint 1: Data Ingestion + Normalization.

Uso:
    python main.py --demo
        Genera datos sintéticos y corre el pipeline de ingestión +
        normalización de punta a punta, sin credenciales externas.

    python main.py --data path/to/dir
        Espera encontrar en ese directorio (nombres flexibles):
            events.json       (StatsBomb events, requerido)
            frames_360.json   (StatsBomb 360, opcional)
            pip_one.json      (PIP One, opcional)
        Detecta automáticamente qué fuentes están disponibles y lo reporta.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config_loader import get_parameters
from ingestion.statsbomb_events import load_statsbomb_events
from ingestion.statsbomb_360 import load_statsbomb_360, has_360_data
from ingestion.pip_one import load_pip_one, merge_pip_one_with_events
from ingestion.csv_events import load_csv_events, load_csv_pip_one
from normalization.events import normalize_events
from data.synthetic import write_synthetic_dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("efos.main")


def _resolve_source_paths(data_dir: Path, fmt: str = "json") -> dict:
    if fmt == "csv":
        candidates = {
            "events": ["events.csv", "statsbomb_events.csv"],
            "frames_360": ["frames_360.csv", "360.csv"],
            "pip_one": ["pip_one.csv", "pip1.csv"],
        }
    else:
        candidates = {
            "events": ["events.json", "statsbomb_events.json"],
            "frames_360": ["frames_360.json", "360.json", "statsbomb_360.json"],
            "pip_one": ["pip_one.json", "pip1.json"],
        }
    resolved = {}
    for key, names in candidates.items():
        found = None
        for name in names:
            candidate = data_dir / name
            if candidate.exists():
                found = candidate
                break
        resolved[key] = found
    return resolved


def run_sprint1(events_path: Path, frames_360_path, pip_one_path, fmt: str = "json") -> dict:
    """
    Ejecuta ingestión + normalización y devuelve un dict con resultados y
    metadatos. `fmt` selecciona el loader de eventos/PIP One:
        "json" -> ingestion.statsbomb_events / ingestion.pip_one (StatsBomb)
        "csv"  -> ingestion.csv_events (formato plano de una fila por evento)

    Nota: StatsBomb 360 (freeze-frames por jugador) no tiene un formato CSV
    estándar en este prototipo; en modo csv se admite igualmente un JSON de
    360 si se provee, pero por defecto no se espera.
    """
    if fmt == "csv":
        raw_events = load_csv_events(events_path)
        pip_df = load_csv_pip_one(pip_one_path) if pip_one_path else load_pip_one(None)
    else:
        raw_events = load_statsbomb_events(events_path)
        pip_df = load_pip_one(pip_one_path)

    freeze_frames = load_statsbomb_360(frames_360_path)

    events_df = normalize_events(raw_events, freeze_frames=freeze_frames)
    merged_df = merge_pip_one_with_events(events_df, pip_df)

    availability = {
        "events_available": len(raw_events) > 0,
        "data_360_available": has_360_data(freeze_frames),
        "pip_one_available": not pip_df.empty,
    }

    return {
        "raw_event_count": len(raw_events),
        "normalized_df": merged_df,
        "availability": availability,
    }


def print_report(result: dict) -> None:
    df = result["normalized_df"]
    avail = result["availability"]

    print("\n" + "=" * 70)
    print("EFOS Prototype v0.1 — Sprint 1: Data Ingestion + Normalization")
    print("=" * 70)
    print(f"Events available:   {'YES' if avail['events_available'] else 'NO'}")
    print(f"360 available:      {'YES' if avail['data_360_available'] else 'NO'}")
    print(f"PIP One available:  {'YES' if avail['pip_one_available'] else 'NO'}")
    print("-" * 70)
    print(f"Raw events read:        {result['raw_event_count']}")
    print(f"Normalized events:      {len(df)}")
    if not df.empty:
        print(f"Matches:                {df['match_id'].nunique()}")
        print(f"Teams:                  {sorted(df['team'].dropna().unique().tolist())}")
        print(f"Event types:            {df['event_type'].nunique()} distintos")
        print(f"Events with 360 data:   {int(df['has_360'].sum())}")
        print(f"Events with PIP match:  {int(df['pip_event_type'].notna().sum())}")
        print("-" * 70)
        print("Muestra de dataset normalizado (5 filas):")
        cols = ["match_id", "minute", "second", "team", "player",
                "event_type", "location_x", "location_y", "has_360", "pip_event_type"]
        cols = [c for c in cols if c in df.columns]
        with with_pd_options():
            print(df[cols].head(5).to_string(index=False))
    print("=" * 70 + "\n")


def with_pd_options():
    import pandas as pd
    class _Ctx:
        def __enter__(self):
            pd.set_option("display.width", 140)
            pd.set_option("display.max_columns", 20)
        def __exit__(self, *a):
            pass
    return _Ctx()


def save_processed(df, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "normalized_events.csv"
    df.to_csv(out_path, index=False)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="EFOS Prototype v0.1")
    parser.add_argument("--demo", action="store_true",
                         help="Genera datos sintéticos y corre el pipeline completo.")
    parser.add_argument("--data", type=str, default=None,
                         help="Directorio con events.json / frames_360.json / pip_one.json")
    parser.add_argument("--csv", type=str, default=None,
                         help="Directorio con events.csv / pip_one.csv (formato plano)")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    fmt = "csv" if args.csv else "json"

    if args.demo:
        demo_dir = base_dir / "data" / "raw" / "demo"
        logger.info("Modo --demo: generando datos sintéticos en %s", demo_dir)
        paths = write_synthetic_dataset(demo_dir)
        events_path = paths["events"]
        frames_360_path = paths["frames_360"]
        pip_one_path = paths["pip_one"]
    elif args.data:
        data_dir = Path(args.data)
        if not data_dir.exists():
            logger.error("El directorio de datos no existe: %s", data_dir)
            sys.exit(1)
        resolved = _resolve_source_paths(data_dir)
        if resolved["events"] is None:
            logger.error(
                "No se encontró un archivo de eventos StatsBomb en %s "
                "(se buscó events.json / statsbomb_events.json).", data_dir
            )
            sys.exit(1)
        events_path = resolved["events"]
        frames_360_path = resolved["frames_360"]
        pip_one_path = resolved["pip_one"]
    elif args.csv:
        data_dir = Path(args.csv)
        if not data_dir.exists():
            logger.error("El directorio de datos no existe: %s", data_dir)
            sys.exit(1)
        resolved = _resolve_source_paths(data_dir, fmt="csv")
        if resolved["events"] is None:
            logger.error(
                "No se encontró un archivo de eventos CSV en %s "
                "(se buscó events.csv / statsbomb_events.csv).", data_dir
            )
            sys.exit(1)
        events_path = resolved["events"]
        frames_360_path = resolved["frames_360"]  # normalmente None en modo csv
        pip_one_path = resolved["pip_one"]
    else:
        parser.print_help()
        sys.exit(0)

    result = run_sprint1(events_path, frames_360_path, pip_one_path, fmt=fmt)
    print_report(result)

    out_path = save_processed(result["normalized_df"], base_dir / "data" / "processed")
    logger.info("Dataset normalizado guardado en: %s", out_path)


if __name__ == "__main__":
    main()
