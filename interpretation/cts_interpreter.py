"""Describe each Coach Tactical Signature component and its current heuristic meaning."""
from __future__ import annotations

MEANINGS={
    "construction":"densidad heurística de pases de construcción respecto al volumen total de eventos",
    "progression":"densidad heurística de progresiones profundas desde zona inicial hacia X>80",
    "attack":"densidad heurística de eventos del equipo en último tercio",
    "defense":"densidad heurística de eventos Pressure ejecutados por el equipo",
    "transition":"proporción de pérdidas con respuesta registrada dentro de 5 segundos",
    "adaptation":"componente reservado para adaptación; en Sprint 4 no está estimado como dimensión independiente",
    "trap_efficiency":"DTE del Trap Engine; experimental hasta calibración",
    "pressure_resistance":"HPS v2 utilizado como componente de resistencia contextual",
    "mean_pressure_context":"PCI medio reescalado a 0–100",
    "confidence":"cobertura muestral interna del CTS, no certeza causal del análisis",
}


def interpret_cts(cts: dict) -> dict:
    rows=[]; claims=[]
    for k,v in cts.items():
        if k=="adaptation" and v is None:
            rows.append({"component":k,"value":None,"meaning":MEANINGS[k]})
        elif isinstance(v,(int,float)):
            rows.append({"component":k,"value":round(float(v),4),"meaning":MEANINGS.get(k,"componente descriptivo del CTS")})
    claim="CTS funciona como vector descriptivo y no como calificación única del entrenador. " + "; ".join(f"{r['component']}={r['value']:.1f}" for r in rows if r['component'] not in {'confidence','adaptation'} and r['value'] is not None) + ". Adaptation permanece N/A en Sprint 4."
    claims.append({"id":"coach_tactical_signature","section":"coach_signature","claim":claim,"evidence":{"components":rows},"n":0,
                   "source":"CTS_ENGINE","confidence":"MEDIUM","limitation":"Las escalas CTS son heurísticas internas y no están calibradas como percentiles de liga."})
    return {"components":rows,"claims":claims}
