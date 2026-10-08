"""
statsbomb_360.py
-----------------
Carga freeze-frames de StatsBomb 360, cuando existen.

Principio clave (sección 6 y 28): si el archivo 360 no existe, el sistema
NO debe inventar posiciones espaciales. Este loader simplemente reporta
disponibilidad y, si hay datos, produce un dict indexado por event_id.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger("efos.ingestion.statsbomb_360")


def load_statsbomb_360(path: Optional[Union[str, Path]]) -> dict[str, dict]:
    """
    Devuelve {event_id: freeze_frame_dict}. Si `path` es None o el archivo
    no existe, devuelve un dict vacío — el resto del sistema debe
    interpretar un dict vacío como "360 no disponible", nunca como error.
    """
    if path is None:
        logger.info("No se proporcionó ruta de datos 360. 360 no disponible.")
        return {}

    path = Path(path)
    if not path.exists():
        logger.info("Archivo 360 no encontrado en %s. 360 no disponible.", path)
        return {}

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        logger.warning("Formato 360 inesperado en %s. Se ignora.", path)
        return {}

    frames: dict[str, dict] = {}
    for frame in raw:
        if not isinstance(frame, dict):
            continue
        event_id = frame.get("event_uuid") or frame.get("event_id")
        if event_id is None:
            continue
        frames[str(event_id)] = {
            "event_id": str(event_id),
            "visible_area": frame.get("visible_area"),
            "freeze_frame": frame.get("freeze_frame", []),
        }

    logger.info("Freeze-frames 360 cargados: %d", len(frames))
    return frames


def has_360_data(frames: dict[str, dict]) -> bool:
    """Helper explícito de disponibilidad, usado por el pipeline principal."""
    return len(frames) > 0
