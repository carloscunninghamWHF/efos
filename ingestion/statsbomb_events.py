"""
statsbomb_events.py
--------------------
Carga eventos StatsBomb (formato JSON estándar de la API abierta) y los
convierte en una lista de dicts "crudos pero seguros": no se asume que
ningún campo anidado exista. Cualquier campo ausente queda como None.

Este módulo NO normaliza coordenadas ni renombra tipos de evento — esa
responsabilidad es de normalization/. Aquí solo se garantiza que la
lectura no falle por estructura incompleta.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger("efos.ingestion.statsbomb_events")


def _safe_get(d: Optional[dict], *keys, default=None):
    """Navega un dict anidado devolviendo `default` si cualquier nivel falta."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_statsbomb_events(path: Union[str, Path]) -> list[dict]:
    """
    Lee un archivo de eventos StatsBomb (lista de eventos JSON) y devuelve
    una lista de dicts planos con los campos relevantes para EFOS.

    Campos ausentes en el evento original se devuelven como None en vez
    de lanzar KeyError — principio de "no asumir que un campo existe"
    (sección 5 de la especificación).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de eventos: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_events = json.load(f)

    if not isinstance(raw_events, list):
        raise ValueError(
            f"Formato inesperado en {path}: se esperaba una lista de eventos JSON."
        )

    parsed: list[dict] = []
    match_id = path.stem  # fallback si el evento no trae match_id explícito

    for ev in raw_events:
        if not isinstance(ev, dict):
            logger.warning("Evento omitido: no es un objeto JSON válido.")
            continue

        event_type = _safe_get(ev, "type", "name")
        team = _safe_get(ev, "team", "name")

        if event_type is None or team is None:
            # Sin tipo de evento o sin equipo, el evento no es utilizable
            # aguas abajo. Se descarta explícitamente (ver missing_data
            # .drop_event_if_missing en parameters.yaml).
            logger.debug("Evento descartado por falta de event_type o team.")
            continue

        record = {
            "match_id": str(ev.get("match_id", match_id)),
            "event_id": ev.get("id"),
            "index": ev.get("index"),
            "possession": ev.get("possession"),
            "possession_team": _safe_get(ev, "possession_team", "name"),
            "team": team,
            "player": _safe_get(ev, "player", "name"),
            "minute": ev.get("minute"),
            "second": ev.get("second"),
            "event_type": event_type,
            "location": ev.get("location"),                # [x, y] o None
            "pass": ev.get("pass"),
            "shot": ev.get("shot"),
            "carry": ev.get("carry"),
            "duel": ev.get("duel"),
            "duration": ev.get("duration"),
            "under_pressure": ev.get("under_pressure", False),
        }
        parsed.append(record)

    logger.info(
        "Eventos leídos: %d | Eventos válidos parseados: %d",
        len(raw_events), len(parsed),
    )
    return parsed
