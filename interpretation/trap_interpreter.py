"""Interpret the experimental Defensive Trap Engine."""
from __future__ import annotations
import pandas as pd


def interpret_traps(traps: pd.DataFrame, trap_metrics: dict) -> dict:
    attempts = int(trap_metrics.get("trap_attempts", 0))
    succ = int(trap_metrics.get("successful_traps", 0))
    dte = float(trap_metrics.get("DTE", 0.0))
    rate = float(trap_metrics.get("trap_rate", 0.0))
    outcomes = {}
    source_mix = {}
    if traps is not None and len(traps):
        outcomes = {str(k): int(v) for k,v in traps.loc[traps["successful"].fillna(False), "outcome_type"].fillna("Unknown").value_counts().head(8).items()}
        source_mix = {str(k): int(v) for k,v in traps["pressure_source"].fillna("UNKNOWN").value_counts().items()}
    claim = (
        f"El Trap Engine detecta {attempts} secuencias candidatas y clasifica {succ} como exitosas con la definición operativa actual, "
        f"produciendo DTE={dte:.2f}% y Trap Rate={rate:.2f} por cada 100 posesiones rivales observadas. "
        "Estos valores describen la salida del detector, no un benchmark validado de eficiencia defensiva."
    )
    return {
        "trap_attempts": attempts,
        "successful_traps": succ,
        "DTE": round(dte, 4),
        "trap_rate": round(rate, 4),
        "outcome_distribution": outcomes,
        "source_distribution": source_mix,
        "claims": [{
            "id":"defensive_traps","section":"defensive_traps","claim":claim,
            "evidence":{"trap_attempts":attempts,"successful_traps":succ,"DTE":round(dte,4),"trap_rate":round(rate,4),"top_outcomes":outcomes,"source_distribution":source_mix},
            "n":attempts,"source":"TRAP_ENGINE","confidence":"EXPERIMENTAL",
            "limitation":"Umbrales y definición de outcome siguen pendientes de calibración empírica; un DTE alto no debe interpretarse todavía como rendimiento real equivalente."}
        ]
    }
