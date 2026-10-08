"""Convierte uno o varios CSV anchos de StatsBomb al CSV normalizado de EFOS.

Uso:
    python prepare_statsbomb.py --inputs data/raw/statsbomb/*.csv --out data/processed/events_normalized.csv
"""
from __future__ import annotations
import argparse
import glob
import logging
from pathlib import Path
from ingestion.statsbomb_wide_csv import load_statsbomb_wide

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")


def expand(patterns):
    files = []
    for p in patterns:
        hits = sorted(glob.glob(p))
        files.extend(hits if hits else [p])
    return files


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", default=["data/raw/statsbomb/*.csv"])
    ap.add_argument("--out", default="data/processed/events_normalized.csv")
    a = ap.parse_args()
    df = load_statsbomb_wide(expand(a.inputs))
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Guardado: {out} ({len(df)} eventos, {df.match_id.nunique()} partidos)")
    print("Equipos:", ", ".join(sorted(df.team.dropna().unique())))
