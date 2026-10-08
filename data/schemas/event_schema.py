"""
event_schema.py
----------------
Esquemas Pydantic que definen el contrato de datos de EFOS.

Estos modelos son deliberadamente permisivos con campos opcionales:
el reglamento del prototipo (sección 5) exige que el sistema NUNCA
asuma que un campo existe. Si StatsBomb no trae un dato, el campo
queda en None y así se propaga explícitamente aguas abajo — nunca
se inventa un valor.
"""
from __future__ import annotations

from typing import Optional, List, Tuple
from pydantic import BaseModel, Field, ConfigDict


class NormalizedEvent(BaseModel):
    """Evento StatsBomb normalizado al esquema interno de EFOS."""
    model_config = ConfigDict(extra="ignore")

    match_id: str
    event_id: Optional[str] = None
    index: Optional[int] = None          # orden original del evento en el partido
    possession: Optional[int] = None
    possession_team: Optional[str] = None
    team: str
    player: Optional[str] = None
    minute: Optional[int] = None
    second: Optional[float] = None
    timestamp_seconds: Optional[float] = None   # minute*60 + second, para ordenar/mergear
    event_type: str
    location_x: Optional[float] = None   # coordenadas ya normalizadas (ver normalization/coordinates.py)
    location_y: Optional[float] = None
    end_location_x: Optional[float] = None
    end_location_y: Optional[float] = None
    pass_outcome: Optional[str] = None
    shot_outcome: Optional[str] = None
    duel_outcome: Optional[str] = None
    under_pressure: Optional[bool] = None

    # trazabilidad de disponibilidad de datos (sección 6)
    has_360: bool = False


class Freeze360Player(BaseModel):
    """Posición de un jugador visible en un freeze-frame de StatsBomb 360."""
    model_config = ConfigDict(extra="ignore")

    x: float
    y: float
    teammate: bool
    actor: bool = False
    keeper: bool = False


class Freeze360Frame(BaseModel):
    """Freeze-frame asociado a un evento (cuando existe dato 360)."""
    model_config = ConfigDict(extra="ignore")

    event_id: str
    match_id: str
    visible_area: Optional[List[Tuple[float, float]]] = None
    players: List[Freeze360Player] = Field(default_factory=list)


class PipOneEvent(BaseModel):
    """
    Esquema estándar para eventos capturados manualmente (human-in-the-loop)
    vía PIP One. Ver sección 7 del documento de especificación.
    """
    model_config = ConfigDict(extra="ignore")

    match_id: str
    timestamp_seconds: float
    team: str
    player: str
    event_type: str            # p.ej. preventive_cover, decoy_run, safety_pass...
    zone: Optional[str] = None
    target_player: Optional[str] = None
    context: Optional[str] = None
    confidence: Optional[float] = None   # 0-1, confianza del analista
    analyst_id: Optional[str] = None
