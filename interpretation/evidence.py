"""Assemble all Coach Story claims into one auditable evidence registry."""
from __future__ import annotations
from datetime import datetime, timezone
from config_loader import get_thresholds


def build_evidence_bundle(team: str, sections: list[dict], principles=None, temporal=None) -> dict:
    claims=[]
    for section in sections:
        claims.extend(section.get("claims", []))
    if principles is not None and len(principles):
        ccfg=get_thresholds().get("coach_story",{}).get("confidence",{})
        hi=float(ccfg.get("principle_high_score",75.0)); med=float(ccfg.get("principle_medium_score",50.0))
        for i,row in principles.reset_index(drop=True).iterrows():
            src=row.get("source","PATTERN_ENGINE")
            src="PATTERN_ENGINE" if src is None or str(src).lower()=="nan" else str(src)
            conf="EXPERIMENTAL" if src=="TRAP_ENGINE" else ("HIGH" if float(row.get("confidence",0))>=hi else "MEDIUM" if float(row.get("confidence",0))>=med else "LOW")
            claims.append({
                "id":f"principle_{i+1}","section":"coach_principles",
                "claim":f"Patrón candidato: {row.get('principle')} — incidencia {float(row.get('value_pct',0)):.1f}% y confidence score {float(row.get('confidence',0)):.1f}/100.",
                "evidence":{k:(v.item() if hasattr(v,'item') else v) for k,v in row.to_dict().items()},
                "n":int(row.get("evidence_n",0)),"source":src,
                "confidence":conf,
                "limitation":"Patrón conductual observado; no demuestra por sí solo una instrucción deliberada del entrenador."
            })
    if temporal:
        claims.extend(temporal.get("claims", []))
    return {
        "team":team,
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "method":"Data -> Rule -> Evidence -> Narrative",
        "claims":claims,
        "confidence_legend":{
            "HIGH":"señal directa con cobertura amplia dentro de la muestra",
            "MEDIUM":"inferencia/proxy con cobertura suficiente pero limitaciones metodológicas",
            "LOW":"cobertura reducida o patrón débil",
            "EXPERIMENTAL":"motor/umbral pendiente de calibración empírica"
        }
    }
