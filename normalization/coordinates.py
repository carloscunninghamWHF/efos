"""
coordinates.py
---------------
Normaliza coordenadas de eventos (y de freeze-frames 360) a un sistema
consistente de cancha, según config/parameters.yaml -> pitch.

Sistema de referencia por defecto: StatsBomb (120 x 80, origen esquina
inferior izquierda del equipo atacante hacia la derecha). Este módulo
existe para que, si en el futuro se ingiere una fuente con otro sistema
(p.ej. Opta 100x100), el resto del pipeline no tenga que cambiar.
"""
from __future__ import annotations

from typing import Optional, Tuple

from config_loader import get_parameters


def get_pitch_dimensions() -> Tuple[float, float]:
    p = get_parameters()["pitch"]
    return float(p["length_m"]), float(p["width_m"])


def normalize_point(
    x: Optional[float],
    y: Optional[float],
    clip: Optional[bool] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Devuelve (x, y) validado dentro de los límites de la cancha configurada.
    Si x o y son None, se devuelven None explícitamente (no se inventa
    posición — principio de degradación explícita, sección 6).
    """
    if x is None or y is None:
        return None, None

    length, width = get_pitch_dimensions()
    if clip is None:
        clip = get_parameters()["normalization"]["clip_out_of_bounds"]

    if clip:
        x = max(0.0, min(length, x))
        y = max(0.0, min(width, y))

    return float(x), float(y)


def extract_location(location: Optional[list]) -> Tuple[Optional[float], Optional[float]]:
    """
    StatsBomb representa `location` como [x, y] (a veces con un tercer
    valor de altura en eventos de disparo, que aquí se ignora). Devuelve
    (None, None) si el campo no existe.
    """
    if not location or len(location) < 2:
        return None, None
    return normalize_point(location[0], location[1])
