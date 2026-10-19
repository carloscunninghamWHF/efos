"""Guardrails: no invented tactical facts, comparable samples or exposed bibliography."""
from copy import deepcopy
from pathlib import Path
import pandas as pd
from interpretation.tactical_reasoning import build_tactical_reasoning
from knowledge.tactical_context import context_for, enrich_claims
from coach_story.executive_pdf import build_executive_pdf
from intelligence.defensive_open_play import STATES


def example():
    vals=[]
    for i in range(90):
        lane='Derecha' if i<40 else 'Izquierda' if i<70 else 'Centro'
        vals.append(dict(lane=lane,match_id=f'm{i%5}',shots=int(i%4==0),
                         box_entries=int(i%3==0),key=(f'm{i%5}',1,i)))
    defense=pd.DataFrame([dict(scenario=STATES[i%3],match_id=f'm{i%5}',shot=bool(i%4==0)) for i in range(90)])
    transitions=pd.DataFrame([dict(team_lost='A',match_id=f'm{i%5}',response_within_5s=bool(i%2)) for i in range(60)])
    return dict(focal_team='A',events=pd.DataFrame([{'team':'A','match_id':'m1'}]),
                organized_attack_data=(pd.DataFrame(),pd.DataFrame(vals)),
                defensive_open_play_possessions=defense,transitions=transitions)


def test_connected_findings_cover_both_phases_and_transitions():
    result=example(); snapshot=deepcopy(result)
    r=build_tactical_reasoning(result)
    assert r['schema']=='EFOS_REASONING_0424'
    assert r['coverage']==4
    assert r['lane_table'].posesiones.sum()==90
    assert r['defense_table'].posesiones.sum()==90
    assert r['findings'][0]['evidence']['denominator']==90
    assert r['findings'][1]['evidence']['denominator']==90
    assert r['findings'][2]['evidence']['denominator']==90
    assert r['findings'][3]['evidence']['denominator']==60
    assert '40 de 90' in r['findings'][0]['observation']
    assert len(r['findings'][0]['cases'])<=12
    assert 'references' not in str(r).lower()
    assert 'youtube' not in str(r).lower()
    assert 'fabregas' not in str(r).lower()
    assert result['organized_attack_data'][1].equals(snapshot['organized_attack_data'][1])
    assert result['defensive_open_play_possessions'].equals(snapshot['defensive_open_play_possessions'])


def test_unknown_sample_does_not_produce_claims():
    r=build_tactical_reasoning({'focal_team':'A'})
    assert r['coverage']==0 and not r['findings']
    assert r['lane_table'].empty and r['defense_table'].empty


def test_partial_inputs_only_enable_supported_findings():
    r=build_tactical_reasoning({'focal_team':'A','transitions':pd.DataFrame({
        'team_lost':['B'],'response_within_5s':[True],'match_id':['m1']})})
    assert r['coverage']==0
    r=build_tactical_reasoning({'focal_team':'A','transitions':pd.DataFrame({
        'team_lost':['A'],'response_within_5s':[True],'match_id':['m1']})})
    assert len(r['findings'])==1
    assert r['findings'][0]['status']=='EXPLORATORIO'
    assert '1 de 1' in r['findings'][0]['observation']


def test_conceptual_sources_are_internal_only():
    claim=enrich_claims([{'id':'progression','claim':'Dato registrado'}])[0]
    assert 'references' not in claim['conceptual_context']
    assert 'references' not in context_for('defense')
    assert 'sources' not in context_for('defense')
    src=(Path(__file__).resolve().parents[1]/'visualization/efos_dashboard.py').read_text()
    assert 'render_reasoning(result' in src
    public_files=['visualization/tactical_context_ui.py','visualization/organized_attack_app.py',
                  'coach_story/report_generator.py']
    root=Path(__file__).resolve().parents[1]
    assert all("['references']" not in (root/x).read_text() for x in public_files)


def test_pdf_carries_connected_reading_without_external_bibliography(tmp_path):
    res=example()
    pdf=build_executive_pdf(res,{'league':'Liga MX','season':'2026'})
    assert pdf.startswith(b'%PDF')
    from pypdf import PdfReader
    reader=PdfReader(__import__('io').BytesIO(pdf))
    assert len(reader.pages)==1
    text=' '.join(page.extract_text() for page in reader.pages)
    assert 'LECTURA TÁCTICA CONECTADA' in text
    assert '¿Desde dónde empieza' in text
    assert 'Fàbregas' not in text and 'Youtube' not in text
