"""Evidence-first interpretation of ESI and its dimensions.

Important: scores are interpreted relatively inside the EFOS model/sample until
external league benchmarks are calibrated. This module never labels a score as
universally "good" or "bad".
"""
from __future__ import annotations
from typing import Any
import math
import numpy as np
from config_loader import get_thresholds

DIMENSION_LABELS = {
    "OC": "Organización colectiva (OC)",
    "HPS": "Estabilidad bajo presión (HPS)",
    "RPS": "Respuesta ante riesgo (RPS)",
    "DS": "Estabilidad de decisión (DS)",
    "DER": "Respuesta tras pérdida (DER)",
}

DIMENSION_MEANING = {
    "OC": "representa la cohesión organizacional estimada del sistema a partir de su compactación espacial y señales de control disponibles",
    "HPS": "representa cuánto de la funcionalidad del equipo se conserva cuando aumenta la restricción contextual rival",
    "RPS": "representa la estabilidad con la que el sistema procesa acciones de riesgo en zonas vulnerables dentro de la definición actual",
    "DS": "representa la estabilidad de ejecución/decisión observada frente a las probabilidades de pase disponibles",
    "DER": "representa la rapidez con la que el sistema recupera equilibrio después de pérdidas y cambios de estado",
}


def _num(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _confidence_label(n: int, source: str = "EVENT") -> str:
    cfg=get_thresholds().get("coach_story",{}).get("confidence",{})
    high_n=int(cfg.get("high_n",1000)); medium_n=int(cfg.get("medium_n",100))
    if source in {"EXPERIMENTAL", "TRAP_ENGINE"}:
        return "EXPERIMENTAL"
    if source == "360_SNAPSHOT":
        return "MEDIUM"
    if n >= high_n:
        return "HIGH"
    if n >= medium_n:
        return "MEDIUM"
    return "LOW"


def _cap_composite(label: str) -> str:
    """Los índices compuestos usan pesos aún no calibrados: su confianza máxima es MEDIUM."""
    return "MEDIUM" if label == "HIGH" else label


def interpret_metrics(esi: float, dimensions: dict, hps_meta: dict | None = None, n_events: int = 0) -> dict:
    """Return structured, non-benchmark claims for system identity and dimensions."""
    hps_meta = hps_meta or {}
    dims = {k: _num(dimensions.get(k)) for k in DIMENSION_LABELS}
    ordered = sorted(dims.items(), key=lambda kv: kv[1], reverse=True)
    strongest = ordered[0][0] if ordered else None
    weakest = ordered[-1][0] if ordered else None
    median = float(np.median(list(dims.values()))) if dims else 0.0
    tol=float(get_thresholds().get("coach_story",{}).get("relative_delta_tolerance",2.0))

    claims = []
    for key, value in dims.items():
        delta = value - median
        relation = "por encima" if delta > tol else "por debajo" if delta < -tol else "cerca"
        text = (
            f"{DIMENSION_LABELS[key]} = {value:.2f}. Dentro de las cinco dimensiones del propio modelo, "
            f"se sitúa {relation} de la mediana interna ({median:.2f}); {DIMENSION_MEANING[key]}."
        )
        claims.append({
            "id": f"metric_{key.lower()}",
            "section": "system_identity",
            "claim": text,
            "evidence": {"metric": key, "value": round(value, 4), "internal_median": round(median, 4), "delta_vs_internal_median": round(delta, 4)},
            "n": int(hps_meta.get("n_actions", n_events) if key == "HPS" else n_events),
            "source": "EVENT_PROXY" if key == "HPS" else "EFOS_METRIC",
            "confidence": _cap_composite(_confidence_label(int(hps_meta.get("n_actions", n_events) if key == "HPS" else n_events), "EVENT")),
            "limitation": "Comparación relativa dentro del modelo/muestra; no es un benchmark de liga calibrado.",
        })

    strongest_text = (
        f"El ESI global es {float(esi):.2f}. La dimensión relativamente más alta dentro del perfil es "
        f"{DIMENSION_LABELS.get(strongest, strongest)} ({dims.get(strongest, 0):.2f}) y la relativamente más baja es "
        f"{DIMENSION_LABELS.get(weakest, weakest)} ({dims.get(weakest, 0):.2f}). Esto describe la forma interna del perfil, no una clasificación absoluta."
    )
    overview = {
        "id": "system_identity_overview",
        "section": "system_identity",
        "claim": strongest_text,
        "evidence": {"ESI": round(float(esi), 4), "dimensions": dims, "strongest_relative": strongest, "weakest_relative": weakest},
        "n": int(n_events),
        "source": "EFOS_METRIC",
        "confidence": _cap_composite(_confidence_label(int(n_events), "EVENT")),
        "limitation": "ESI y dimensiones siguen siendo hipótesis descriptivas hasta completar calibración externa.",
    }
    return {
        "ESI": round(float(esi), 4),
        "dimensions": dims,
        "strongest_relative": strongest,
        "weakest_relative": weakest,
        "internal_median": round(median, 4),
        "overview": overview,
        "claims": claims,
    }
