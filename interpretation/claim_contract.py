"""EFOS Claim Contract v1: provenance-aware, conservative tactical claims.

Presentation-only adapter. Never mutates events, metrics, possession logic or data.
An evidence level is an epistemic class, NOT a probability of correctness.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

STATUS = {
    "E0": "not_evaluable", "E1": "descriptive", "E2": "contextual_pattern",
    "E3": "plausible_mechanism", "E4": "validated_intervention",
}
ALLOWED_SOURCES = {"StatsBomb_events", "StatsBomb_360", "video", "tracking", "manual_verified", "other"}


def _n(value: Any) -> int:
    try:
        n = int(value)
        return max(0, n)
    except (ValueError, TypeError, OverflowError):
        return 0


def _ids(result: dict) -> list[str]:
    """Read exact match IDs from events when present; never infer from counts."""
    events = result.get("events")
    if events is not None and hasattr(events, "columns") and "match_id" in events.columns:
        values = events["match_id"].dropna().unique().tolist()
        return sorted({str(v) for v in values if str(v).strip()})
    return sorted({str(v) for v in (result.get("match_ids") or []) if v is not None and str(v).strip()})


def evaluate_claim_evidence(*, requested: str = "E1", team: str = "", match_ids=(),
                            n: int = 0, n_matches: int = 0, baseline: bool = False,
                            contextual_repetitions: int = 0, mechanism_reviewed: bool = False,
                            sources=(), out_of_sample_validated: bool = False,
                            missing_fields=()) -> tuple[str, str]:
    """Never promote an unverified description into tactical mechanism or advice."""
    if (not team.strip() or not match_ids or n < 1 or n_matches < 1
            or n_matches > len(set(map(str, match_ids))) or missing_fields):
        return "E0", "Muestra, identidad de equipo o trazabilidad de partidos insuficiente."
    if requested not in STATUS:
        raise ValueError(f"Nivel de evidencia desconocido: {requested}")
    if requested == "E0":
        return "E0", "Afirmación marcada como no evaluable."
    if requested == "E1":
        return "E1", "Registro descriptivo; no implica causalidad ni estilo estable."
    if not (baseline and n >= 30 and n_matches >= 3 and contextual_repetitions >= 2):
        return "E1", "Faltan comparación contextual, repetición o muestra para E2."
    if requested == "E2":
        return "E2", "Patrón contextual con comparación y repetición verificadas."
    if not (mechanism_reviewed and bool(set(sources) & {"video", "tracking", "manual_verified"})):
        return "E2", "E3 exige revisión del mecanismo y corroboración independiente."
    if requested == "E3":
        return "E3", "Mecanismo plausible triangulado; no prueba causalidad."
    if not out_of_sample_validated:
        return "E3", "E4 requiere evaluación empírica fuera de muestra."
    return "E4", "Intervención evaluada fuera de muestra; debe declarar sus supuestos."


def _source_records(finding: dict) -> list[dict]:
    """Never reinterpret an arbitrary sequence key as event_id or clip_id."""
    output = []
    for record in finding.get("evidence_records", []) or []:
        if not isinstance(record, dict) or record.get("source") not in ALLOWED_SOURCES or not record.get("match_id"):
            continue
        entry = {"source": record["source"], "match_id": str(record["match_id"])}
        if record.get("event_ids"):
            entry["event_ids"] = [str(x) for x in record["event_ids"]]
        for key in ("possession_id", "frame_id", "clip_id"):
            if record.get(key) is not None:
                entry[key] = str(record[key])
        output.append(entry)
    return output


def build_reasoning_claim(result: dict, finding: dict) -> dict:
    """Wrap a legacy finding in Claim v1 without changing its existing fields."""
    team = str(result.get("focal_team") or "")
    match_ids = _ids(result)
    ev = finding.get("evidence") or {}
    n_matches = _n(ev.get("matches"))
    n = _n(ev.get("denominator") or ev.get("observed"))
    note = str(finding.get("scope") or "")
    raw_ids = json.dumps(match_ids, separators=(",", ":"), ensure_ascii=False)
    key = "matches:" + sha256(raw_ids.encode("utf-8")).hexdigest() if match_ids else "matches:unverified"
    unit = ("events" if finding.get("id") == "conexiones_principales" else "possessions")
    status, reason = evaluate_claim_evidence(
        requested=finding.get("requested_evidence_level", "E1"), team=team,
        match_ids=match_ids, n=n, n_matches=n_matches,
        baseline=bool(finding.get("baseline_verified")),
        contextual_repetitions=_n(finding.get("contextual_repetitions")),
        mechanism_reviewed=bool(finding.get("mechanism_reviewed")),
        sources=finding.get("verified_sources") or [],
        out_of_sample_validated=bool(finding.get("out_of_sample_validated")),
        missing_fields=finding.get("missing_fields") or [],
    )
    full_id = json.dumps([team, key, finding.get("module"), finding.get("id")], ensure_ascii=False)
    claim_id = "efos:" + sha256(full_id.encode("utf-8")).hexdigest()[:20]
    limitations = [str(finding.get("limitation") or "Limitaciones no documentadas."), reason]
    if not finding.get("evidence_records"):
        limitations.append("Evidencia agregada: aún no hay vínculos comprobados a event_id individuales.")
    if finding.get("cases"):
        limitations.append("Las claves legacy de secuencia no se interpretan como event_id ni clips verificados.")
    observation = str(finding.get("observation") or "") if status != "E0" else None
    interpretation = str(finding.get("interpretation") or "") if status != "E0" else None
    action = str(finding.get("action") or "").strip()
    decision_options = ([{"hypothesis": "Explorar esta hipótesis, sin prescribir un ajuste automático.",
                          "risk": str(finding.get("limitation") or "Debe verificarse el contexto."),
                          "validation_action": action}] if status != "E0" and action else [])
    source_payload = json.dumps({"team": team, "matches": match_ids, "evidence": ev,
                                 "observation": observation}, sort_keys=True,
                                ensure_ascii=False, default=str)
    signature = "claim-payload-sha256:" + sha256(source_payload.encode("utf-8")).hexdigest()
    return {
        "schema_version": "1.0.0", "claim_id": claim_id,
        "scope": {"team": team or "Equipo sin identificar", "coach": result.get("coach"),
                  "tenure_id": result.get("tenure_id"), "league": result.get("league"),
                  "season": result.get("season"), "scope_key": key, "match_ids": match_ids,
                  "filters": {}, "coordinates": "StatsBomb_120x80_focal_own_goal_X0"},
        "question": str(finding.get("question") or "Pregunta no disponible"),
        "observation": observation, "context": str(finding.get("context") or ""),
        "interpretation": interpretation,
        "alternative_explanations": ([str(finding["alternative"])] if finding.get("alternative") else []),
        "evidence_level": status,
        "sample": {"n_matches": n_matches, "unit": unit, "n": n,
                   "denominator": _n(ev["denominator"]) if ev.get("denominator") is not None else None,
                   "baseline_description": finding.get("baseline_description") if finding.get("baseline_verified") else None,
                   "coverage_note": note},
        "evidence_records": _source_records(finding), "limitations": limitations,
        "decision_options": decision_options, "status": STATUS[status],
        "provenance": {"pipeline_version": "EFOS_REASONING_0424",
                       "source_signature": signature, "generated_at": None},
    }


def validate_claim_contract(claim: dict) -> None:
    """Fast invariant checks. JSON Schema is the authoritative full validator."""
    mandatory = ("schema_version", "claim_id", "scope", "question", "observation", "context",
                 "interpretation", "evidence_level", "sample", "evidence_records", "limitations",
                 "status", "provenance")
    missing = [key for key in mandatory if key not in claim]
    if missing:
        raise ValueError(f"Campos faltantes: {missing}")
    level = claim["evidence_level"]
    if claim["schema_version"] != "1.0.0" or level not in STATUS or claim["status"] != STATUS[level]:
        raise ValueError("Versión, evidencia o estado incoherentes")
    if level == "E0" and (claim["interpretation"] is not None or claim.get("decision_options")):
        raise ValueError("E0 debe abstenerse de interpretar y recomendar")
    if claim["sample"]["n_matches"] > len(set(claim["scope"]["match_ids"])):
        if level != "E0":
            raise ValueError("Muestra de partidos incompatible con alcance")
