"""Sprint A: epistemic gates, source honesty and deterministic references."""
import copy
import pandas as pd
import pytest

from interpretation.claim_contract import (build_reasoning_claim,
                                           evaluate_claim_evidence, validate_claim_contract)


def _case():
    result = {"focal_team": "Club X", "events": pd.DataFrame({"match_id": ["2", "1", "2"]})}
    finding = {"id": "inicio", "module": "Cómo ataca", "question": "¿Dónde inicia?",
               "observation": "Dos inicios por derecha", "context": "Dos partidos",
               "interpretation": "Se observaron inicios", "alternative": "Marcador",
               "action": "Revisar vídeo", "limitation": "Sin tracking",
               "scope": "2 posesiones, 2 partidos", "evidence": {"observed": 2, "denominator": 2, "matches": 2},
               "cases": ["pos:2"]}
    return result, finding


def test_v1_is_deterministic_and_preserves_input():
    result, finding = _case()
    snapshot = copy.deepcopy(finding)
    a = build_reasoning_claim(result, finding)
    b = build_reasoning_claim(result, finding)
    validate_claim_contract(a)
    assert a == b and finding == snapshot
    assert a['evidence_level'] == 'E1'
    assert a['scope']['match_ids'] == ['1', '2']
    assert a['sample']['denominator'] == 2
    assert a['evidence_records'] == []  # A 'case' is not automatically an event ID.
    assert a['provenance']['source_signature'].startswith('claim-payload-sha256:')


def test_missing_sample_abstains():
    result, finding = _case()
    result['events'] = pd.DataFrame()
    claim = build_reasoning_claim(result, finding)
    validate_claim_contract(claim)
    assert claim['evidence_level'] == 'E0'
    assert claim['interpretation'] is None and claim['decision_options'] == []


def test_mismatch_between_match_count_and_known_ids_abstains():
    result, finding = _case()
    finding['evidence']['matches'] = 3
    claim = build_reasoning_claim(result, finding)
    assert claim['evidence_level'] == 'E0'


def test_levels_require_explicit_corroborration():
    args = dict(team='A', match_ids=['1', '2', '3'], n=35, n_matches=3,
                baseline=True, contextual_repetitions=2)
    assert evaluate_claim_evidence(requested='E2', **args)[0] == 'E2'
    assert evaluate_claim_evidence(requested='E3', **args)[0] == 'E2'
    assert evaluate_claim_evidence(requested='E3', mechanism_reviewed=True,
                                   sources=['video'], **args)[0] == 'E3'
    assert evaluate_claim_evidence(requested='E4', mechanism_reviewed=True,
                                   sources=['video'], **args)[0] == 'E3'
    assert evaluate_claim_evidence(requested='E4', mechanism_reviewed=True,
                                   sources=['video'], out_of_sample_validated=True, **args)[0] == 'E4'
    assert evaluate_claim_evidence(requested='E2', **{**args,'baseline':False})[0] == 'E1'


def test_schema_e0_forbids_decision():
    result, finding = _case()
    result['events'] = pd.DataFrame()
    claim = build_reasoning_claim(result, finding)
    claim['decision_options'] = [{'hypothesis': 'unsafe'}]
    with pytest.raises(ValueError, match='E0'):
        validate_claim_contract(claim)
