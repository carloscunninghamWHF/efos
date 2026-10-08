"""
pip_one.py
-----------
Carga eventos PIP One (capturados manualmente por un analista) y define
la lógica de fusión con los eventos StatsBomb, respetando incertidumbre
temporal (sección 7 de la especificación).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from config_loader import get_thresholds

logger = logging.getLogger("efos.ingestion.pip_one")

PIP_ONE_FIELDS = [
    "match_id", "timestamp", "team", "player", "event_type",
    "zone", "target_player", "context", "confidence", "analyst_id",
]


def load_pip_one(path: Optional[Union[str, Path]]) -> pd.DataFrame:
    """
    Lee un archivo JSON de eventos PIP One y devuelve un DataFrame con
    el esquema estándar. Si `path` es None o no existe, devuelve un
    DataFrame vacío con las columnas esperadas — "PIP One no disponible"
    es un estado válido y explícito, no un error.
    """
    if path is None:
        logger.info("No se proporcionó ruta de eventos PIP One. PIP One no disponible.")
        return pd.DataFrame(columns=PIP_ONE_FIELDS)

    path = Path(path)
    if not path.exists():
        logger.info("Archivo PIP One no encontrado en %s. PIP One no disponible.", path)
        return pd.DataFrame(columns=PIP_ONE_FIELDS)

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list) or len(raw) == 0:
        logger.warning("Archivo PIP One vacío o con formato inesperado: %s", path)
        return pd.DataFrame(columns=PIP_ONE_FIELDS)

    df = pd.DataFrame(raw)
    for col in PIP_ONE_FIELDS:
        if col not in df.columns:
            df[col] = None

    df = df[PIP_ONE_FIELDS].rename(columns={"timestamp": "timestamp_seconds"})
    logger.info("Eventos PIP One cargados: %d", len(df))
    return df


def merge_pip_one_with_events(
    events_df: pd.DataFrame,
    pip_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Fusiona eventos PIP One con eventos StatsBomb normalizados usando
    match_id + team + player + una ventana de tolerancia temporal
    (pip_one_merge.timestamp_tolerance_seconds en thresholds.yaml).

    No se exige coincidencia exacta de timestamp: los eventos manuales
    tienen incertidumbre temporal inherente (sección 7). El resultado
    añade, a cada fila de events_df, las columnas:
        pip_event_type, pip_zone, pip_target_player, pip_context,
        pip_confidence, pip_analyst_id
    dejándolas en None cuando no hay match.
    """
    pip_cols = ["pip_event_type", "pip_zone", "pip_target_player",
                "pip_context", "pip_confidence", "pip_analyst_id"]

    result = events_df.copy()
    for col in pip_cols:
        result[col] = None

    if pip_df.empty:
        logger.info("PIP One vacío: se omite el merge, columnas PIP quedan en None.")
        return result

    tolerance = get_thresholds()["pip_one_merge"]["timestamp_tolerance_seconds"]
    matched = 0

    for idx, ev in result.iterrows():
        candidates = pip_df[
            (pip_df["match_id"] == ev["match_id"])
            & (pip_df["team"] == ev["team"])
            & (pip_df["player"] == ev.get("player"))
        ]
        if candidates.empty:
            continue

        candidates = candidates.copy()
        candidates["delta"] = (
            candidates["timestamp_seconds"] - ev["timestamp_seconds"]
        ).abs()
        best = candidates[candidates["delta"] <= tolerance].sort_values("delta")

        if not best.empty:
            row = best.iloc[0]
            result.at[idx, "pip_event_type"] = row["event_type"]
            result.at[idx, "pip_zone"] = row["zone"]
            result.at[idx, "pip_target_player"] = row["target_player"]
            result.at[idx, "pip_context"] = row["context"]
            result.at[idx, "pip_confidence"] = row["confidence"]
            result.at[idx, "pip_analyst_id"] = row["analyst_id"]
            matched += 1

    logger.info(
        "Merge PIP One completado. Eventos con match: %d / %d (tolerancia=%.1fs)",
        matched, len(result), tolerance,
    )
    return result
