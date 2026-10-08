from pathlib import Path
import pandas as pd

from ui.data_catalog import scan_catalog, period_options, paths_for_selection, context_for_selection, ALL_PERIODS
from intelligence.cts import compute_adaptation_score
from coach_story.executive_pdf import build_executive_pdf


def test_catalog_detects_repo_team_and_periods():
    root=Path(__file__).resolve().parents[1]
    cat=scan_catalog(root/'data'/'raw'/'statsbomb', root/'config'/'team_metadata.yaml')
    assert len(cat)>=2
    row=cat.iloc[0]
    opts=period_options(cat,row.league,row.season,row.team)
    assert ALL_PERIODS in opts
    paths=paths_for_selection(cat,row.league,row.season,row.team,ALL_PERIODS)
    assert len(paths)>=2
    ctx=context_for_selection(cat,row.league,row.season,row.team,ALL_PERIODS)
    assert ctx['team']==row.team
    assert ctx.get('coach')


def test_adaptation_score_from_recovery_windows():
    s=pd.DataFrame({'state':['tension','fragility','stability','collapse'],
                    'next_state':['adaptation','tension','stability','stability']})
    # 2 of 3 disturbed windows recover to adaptation/stability
    assert round(compute_adaptation_score(s),2)==66.67


def test_executive_pdf_is_one_page_payload():
    result={
      'focal_team':'Equipo X','ESI':72.0,
      'coach_identity':{'estructura':{'dibujo_principal':'4-3-3'}},
      'football_report':{
        'equipo':'Equipo X','ficha':{'partidos':10},
        'textos':{'entrenador':'Equipo proactivo y estable.'},
        'fortalezas':[{'titulo':'Presión alta','dato':'8.0 recuperaciones','rivales':'5.0'}],
        'debilidades':[{'titulo':'Balón parado','dato':'0.50 xG','rivales':'0.30'}],
        'como_jugarle':['Atacar el espacio a la espalda.'],
      },
      'evidence':{'claims':[{'id':'x'}]},
      'coach_story':{}
    }
    pdf=build_executive_pdf(result,{'coach':'DT Demo','league':'Liga MX','season':'2025-2026','period':'Apertura (P1)'})
    assert pdf.startswith(b'%PDF')
    # ReportLab emits /Count 1 for a one-page document.
    assert b'/Count 1' in pdf
