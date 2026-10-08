from coach_story.pdf_report import build_coach_story_pdf


def test_pdf_report_builds_bytes(tmp_path):
    story = {
        "team":"Demo FC",
        "title":"EFOS Coach Story - Demo FC",
        "analysis_metadata":{"matches_analyzed":2,"team_events":120,"files_loaded":2,"frames360_loaded":0},
        "executive_summary":{"narrative":"Demo FC muestra un patrón estable.","key_question":"¿Cómo responde al cambio?"},
        "system_identity":{"ESI":70.0,"dimensions":{"OC":60,"HPS":70,"RPS":80,"DS":75,"DER":65},"strongest_relative":"RPS","weakest_relative":"OC"},
        "contextual_behavior":{"rows":[]},
        "pressure_resistance":{"mean_pci_hps_actions":0.35},
        "dynamic_states":{"state_distribution":{"stability":{"windows":5,"share_pct":50},"adaptation":{"windows":5,"share_pct":50}},"claims":[]},
        "defensive_traps":{},
        "coach_tactical_signature":{"defense":65.0,"transition":55.0,"adaptation":None},
        "coach_tactical_signature_interpretation":{"claims":[]},
        "coach_principles":[],
        "player_participation":{},
        "temporal_evolution":{"phases":[]},
        "tactical_framework":{"defensive_profile":{},"construction_progression":{},"offensive_microconcepts":{},"value_purpose":{},"claims":[]},
        "conclusion":"Demo FC presenta regularidades observables.",
        "limitations":["Muestra de prueba."],
    }
    result={"coach_story":story,"evidence":{"claims":[]},"focal_team":"Demo FC"}
    out=tmp_path/"coach_story.pdf"
    data=build_coach_story_pdf(result,out)
    assert data.startswith(b"%PDF")
    assert len(data)>5000
    assert out.exists() and out.stat().st_size==len(data)
