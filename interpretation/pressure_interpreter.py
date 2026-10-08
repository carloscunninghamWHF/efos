"""Interpret Pressure Context and HPS components without overstating causality."""
from __future__ import annotations
import pandas as pd


def _component_view(summary: dict) -> dict:
    out={}
    for k,v in (summary.get("components") or {}).items():
        out[k]={
            "mean":None if v.get("mean") is None else round(float(v["mean"]),6),
            "coverage_pct":round(100*float(v.get("coverage",0)),2)
        }
    return out


def interpret_pressure(pressure_context: pd.DataFrame, focal_team: str, pressure_summary: dict, hps: float, hps_meta: dict, imposed_summary: dict|None=None) -> dict:
    pc = pressure_context[pressure_context["team"].eq(focal_team)].copy() if pressure_context is not None and len(pressure_context) else pd.DataFrame()
    n = int(len(pc)); imposed_summary=imposed_summary or {}
    overall_mean_pci = float(pressure_summary.get("mean_pci", 0.0))
    mean_pci = float(hps_meta.get("mean_pci", overall_mean_pci))
    high_rate = float(pressure_summary.get("high_pressure_rate", 0.0))
    lane_cov = float(pressure_summary.get("lane_closure_coverage", 0.0))
    comps = {k: float(hps_meta.get(k, 0.0)) for k in ["retention", "progression", "value_preservation", "decision_stability"]}
    comp_pct = {k: round(100*v, 2) for k,v in comps.items()}
    source = "360_SNAPSHOT" if lane_cov > 0 else "EVENT_PROXY"
    confidence = "MEDIUM"  # proxy limits intentionally cap interpretive confidence

    claim = (
        f"HPS v2 = {float(hps):.2f} con un PCI medio de {mean_pci:.3f} sobre las acciones elegibles de HPS. EFOS separa el estímulo "
        f"(presión/restricción rival) de la respuesta del sistema. Retención={comp_pct['retention']:.1f}, progresión={comp_pct['progression']:.1f}, "
        f"preservación de valor={comp_pct['value_preservation']:.1f} y estabilidad de decisión={comp_pct['decision_stability']:.1f} en escala 0–100."
    )
    pressure_claim = (
        f"El PCI medio sobre todas las acciones contextuales del equipo es {overall_mean_pci:.3f}; el {100*high_rate:.1f}% supera el umbral operativo "
        f"de presión alta (PCI≥0.60). La cobertura de Lane Closure es {100*lane_cov:.1f}%; con 0% el motor trabaja como EVENT_PROXY y no como tracking/360 completo."
    )

    imposed_claim=None
    imposed_components=_component_view(imposed_summary)
    if imposed_summary:
        ipci=float(imposed_summary.get("mean_pci",0.0)); ihr=float(imposed_summary.get("high_pressure_rate",0.0))
        d=imposed_components.get("direct_pressure",{}).get("mean"); nb=imposed_components.get("nearby_pressure",{}).get("mean")
        bc=imposed_components.get("boundary_constraint",{}).get("mean"); dr=imposed_components.get("defensive_responsibility",{}).get("mean")
        imposed_claim=(
            f"Sobre acciones del rival, el contexto defensivo asociado al equipo registra PCI medio={ipci:.3f} y {100*ihr:.1f}% de acciones en PCI≥0.60. "
            f"Los componentes medios son presión directa={0 if d is None else d:.3f}, presión cercana={0 if nb is None else nb:.3f}, "
            f"restricción de banda={0 if bc is None else bc:.3f} y DefR={0 if dr is None else dr:.3f}. DefR se interpreta como proxy de responsabilidad defensiva, no como intensidad física."
        )

    claims=[
        {"id":"pressure_resistance","section":"pressure_resistance","claim":claim,
         "evidence":{"HPS":round(float(hps),4),"mean_PCI_HPS_actions":round(mean_pci,6),"components":comp_pct,"n_actions":int(hps_meta.get("n_actions",0))},
         "n":int(hps_meta.get("n_actions",0)),"source":source,"confidence":confidence,
         "limitation":"PCI EVENT_PROXY no contiene velocidad/dirección continuas; HPS no implica intención del entrenador."},
        {"id":"pressure_environment","section":"pressure_resistance","claim":pressure_claim,
         "evidence":{"mean_PCI_all_actions":round(overall_mean_pci,6),"high_pressure_rate_pct":round(100*high_rate,2),"lane_closure_coverage_pct":round(100*lane_cov,2),"threshold":0.60,"components":_component_view(pressure_summary)},
         "n":n,"source":source,"confidence":"MEDIUM",
         "limitation":"El umbral PCI=0.60 es operativo y requiere calibración externa."},
    ]
    if imposed_claim:
        claims.append({"id":"pressure_imposed_context","section":"pressing_model","claim":imposed_claim,
                       "evidence":{"mean_PCI_opponent_actions":round(float(imposed_summary.get('mean_pci',0)),6),"high_pressure_rate_pct":round(100*float(imposed_summary.get('high_pressure_rate',0)),2),"components":imposed_components},
                       "n":int(imposed_summary.get("n_actions",0)),"source":"EVENT_PROXY","confidence":"MEDIUM",
                       "limitation":"Las acciones del rival bajo presión son compatibles con restricción generada por el equipo defensor, pero no equivalen a tracking continuo ni aíslan todas las causas contextuales."})

    return {
        "hps": round(float(hps), 4),"mean_pci_hps_actions":round(mean_pci,6),"mean_pci_all_context_actions":round(overall_mean_pci,6),
        "high_pressure_rate":round(high_rate,6),"lane_closure_coverage":round(lane_cov,6),"components_faced":_component_view(pressure_summary),
        "components_imposed":imposed_components,"imposed_summary":{"mean_pci":round(float(imposed_summary.get('mean_pci',0)),6),"high_pressure_rate":round(float(imposed_summary.get('high_pressure_rate',0)),6),"n_actions":int(imposed_summary.get('n_actions',0))} if imposed_summary else {},
        "components_0_100":comp_pct,"claims":claims
    }
