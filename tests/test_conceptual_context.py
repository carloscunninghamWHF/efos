from copy import deepcopy
import json
from knowledge.tactical_context import context_for,enrich_claims

def test_enrichment_preserves_all_original_evidence():
    claims=[{'id':'tactical_pressure_attraction','claim':'4 de 12 casos','evidence':{'n':4,'denominator':12,'rate':1/3,'ids':['a','b']},'n':4,'confidence':'MEDIUM'}]
    before=deepcopy(claims);out=enrich_claims(claims)
    assert claims==before
    assert {k:v for k,v in out[0].items() if k!='conceptual_context'}==before[0]
    out[0]['evidence']['n']=99
    assert claims==before

def test_missing_input_has_no_diagnoses():
    assert enrich_claims([])==[]

def test_catalog_return_is_independent_and_does_not_expose_theoretical_sources():
    a=context_for('pressure');a['reading']='modificado'
    b=context_for('pressure')
    assert b['reading'] != 'modificado'
    assert 'references' not in b and 'sources' not in b
    assert 'no es un hallazgo' in b['status']
    json.dumps(b,allow_nan=False)
