"""Build structured Coach Story JSON from EFOS outputs."""
from __future__ import annotations
import math
from interpretation.metric_interpreter import interpret_metrics
from interpretation.pressure_interpreter import interpret_pressure
from interpretation.trap_interpreter import interpret_traps
from interpretation.temporal import analyze_temporal_evolution
from interpretation.context_interpreter import interpret_context_esi
from interpretation.dtc_interpreter import interpret_dtc
from interpretation.lap_interpreter import interpret_lap
from interpretation.cts_interpreter import interpret_cts
from interpretation.tactical_framework import interpret_tactical_framework
from interpretation.evidence import build_evidence_bundle


DIM_LABELS = {
    "OC":"Organización colectiva",
    "HPS":"Estabilidad bajo presión",
    "RPS":"Respuesta ante riesgo",
    "DS":"Estabilidad de decisión",
    "DER":"Respuesta tras pérdida",
}
PRINCIPLE_LABELS = {
    "Ball retention under high constraint":"Conservación bajo alta restricción",
    "Defensive trap execution":"Ejecución de traps defensivos",
    "Immediate response after possession loss":"Respuesta inmediata tras pérdida",
    "Boundary use within high-constraint actions":"Uso de banda como restricción",
    "High-block pressure":"Presión en bloque alto",
    "Direct pressure on opponent actions":"Presión directa sobre acciones rivales",
    "Direct deep progression from X<40 to X>80":"Progresión directa desde inicio a último tercio",
    "Passing-lane denial":"Cierre de líneas de pase",
}


def _clean_source(v, default="PATTERN_ENGINE"):
    if v is None: return default
    try:
        if isinstance(v,float) and math.isnan(v): return default
    except Exception: pass
    s=str(v)
    return default if s.lower()=="nan" else s


def build_coach_story(result: dict, focal_team: str) -> tuple[dict,dict]:
    ev=result["events"]
    system=interpret_metrics(result["ESI"],result["esi_dimensions"],result.get("hps_meta",{}),int((ev.team==focal_team).sum()))
    pressure=interpret_pressure(result.get("pressure_context"),focal_team,result.get("pressure_summary",{}),result["esi_dimensions"].get("HPS",0),result.get("hps_meta",{}),result.get("pressure_imposed_summary",{}))
    traps=interpret_traps(result.get("traps"),result.get("trap_metrics",{}))
    context=interpret_context_esi(result.get("esi_by_context"))
    dynamic=interpret_dtc(result.get("dtc_states"),result.get("dtc_matrix"))
    players=interpret_lap(result.get("lap"))
    signature=interpret_cts(result.get("cts",{}))
    temporal=analyze_temporal_evolution(ev,result.get("match_windows"))
    tactical=interpret_tactical_framework(result.get("tactical_framework"))
    principles=result.get("principles")
    cts=result.get("cts",{})

    principle_records=[]
    if principles is not None and len(principles):
        for _,r in principles.iterrows():
            principle_records.append({
                "principle":str(r.get("principle")),"display_name":PRINCIPLE_LABELS.get(str(r.get("principle")),str(r.get("principle"))),"value_pct":round(float(r.get("value_pct",0)),2),
                "confidence_score":round(float(r.get("confidence",0)),2),"evidence_n":int(r.get("evidence_n",0)),
                "source":_clean_source(r.get("source"))
            })

    reliable=[p for p in principle_records if p["source"]!="TRAP_ENGINE"]
    top_principles=reliable[:3] if reliable else principle_records[:3]
    pp=", ".join(p.get("display_name",p["principle"]) for p in top_principles) if top_principles else "sin patrones candidatos suficientes"
    strong=system.get("strongest_relative"); weak=system.get("weakest_relative")
    strong_label=DIM_LABELS.get(strong,strong); weak_label=DIM_LABELS.get(weak,weak)
    dims=system.get("dimensions",{})
    strong_value=float(dims.get(strong,0)); weak_value=float(dims.get(weak,0))
    tf_build=tactical.get("construction_progression",{}); tf_def=tactical.get("defensive_profile",{})
    release=tf_build.get("pressure_release_success",{}).get("rate")
    counter_pm=tf_def.get("counterpress",{}).get("per_match")
    high_press=tf_def.get("high_press_share",{}).get("rate")
    tactical_phrase=[]
    if counter_pm is not None and high_press is not None:
        tactical_phrase.append(f"Sin balón registra {counter_pm:.1f} acciones de counterpress por partido y {100*high_press:.1f}% de sus Pressure events aparecen en x≥80.")
    if release is not None:
        tactical_phrase.append(f"Con balón, {100*release:.1f}% de las secuencias que cumplen el proxy de atracción de presión encuentran una liberación progresiva posterior.")
    conclusion=(
        f"En la muestra analizada, {focal_team} se define principalmente por {strong_label.lower()} ({strong_value:.1f}/100), mientras {weak_label.lower()} ({weak_value:.1f}/100) es la dimensión relativamente más variable del perfil. "
        + " ".join(tactical_phrase)
        + f" Los patrones candidatos con mayor evidencia incluyen {pp}. EFOS describe regularidades observadas; no afirma por sí solo que sean instrucciones deliberadas del entrenador."
    )
    key_question=(
        f"¿Qué provoca los momentos en que {weak_label.lower()} se separa del comportamiento habitual y cómo cambia la respuesta del equipo después?"
    )


    story={
        "team":focal_team,
        "title":f"EFOS Coach Story — {focal_team}",
        "method":"Data -> Metrics -> Interpretation -> Evidence -> Coach Story",
        "executive_summary":{"narrative":conclusion,"key_question":key_question,"strongest":strong_label,"weakest":weak_label},
        "system_identity":system,
        "contextual_behavior":context,
        "pressure_resistance":pressure,
        "dynamic_states":dynamic,
        "defensive_traps":traps,
        "coach_tactical_signature":cts,
        "coach_tactical_signature_interpretation":signature,
        "coach_principles":principle_records,
        "player_participation":players,
        "temporal_evolution":temporal,
        "tactical_summary":result.get("tactical_summary",{}),
        "tactical_framework":tactical,
        "transition_response_rate":result.get("transition_response_rate"),
        "conclusion":conclusion,
        "limitations":[
            "ESI y sus dimensiones aún no están calibrados como benchmark universal de liga.",
            "PCI basado sólo en eventos es un proxy: no equivale a tracking continuo ni a Time-to-Intercept real.",
            "Trap Engine y DTE permanecen experimentales hasta calibrar umbrales/outcomes contra video o etiquetado humano.",
            "DTC depende de umbrales configurables y debe validarse antes de tratar sus estados como categorías universales.",
            "LAP mide participación en acciones críticas definidas por el modelo, no calidad global del jugador.",
            "Los patrones observados no demuestran por sí solos intención o instrucción del entrenador.",
            "Fishing, tercer hombre, Aliup, intervalos y trampa de fuera de juego se reportan como proxies cuando el event data no observa directamente el movimiento/estructura requerido.",
            "La planificación semanal generada es una hipótesis de foco técnico-táctico; EFOS no prescribe carga física ni sustituye el scouting específico del próximo rival.",
            "Cuando no hay fecha de partido, la evolución usa orden de aparición del dataset, no cronología calendario."
        ]
    }
    evidence=build_evidence_bundle(focal_team,[system,context,pressure,dynamic,traps,signature,players,tactical],principles,temporal)
    return story,evidence
