"""Interpret video-derived tactical framework into auditable Coach Story claims."""
from __future__ import annotations


def _pct(v):
    return None if v is None else 100.0*float(v)


def _claim(id_, claim, evidence, source, confidence, limitation, n=None):
    return {
        "id": id_, "section": "tactical_framework", "claim": claim,
        "evidence": evidence, "n": int(n or 0), "source": source,
        "confidence": confidence, "limitation": limitation,
    }


def interpret_tactical_framework(tf: dict | None) -> dict:
    if not tf:
        return {"claims": [], "summary": [], "weekly_planning_hypotheses": []}
    d=tf.get("defensive_profile",{}); b=tf.get("construction_progression",{}); o=tf.get("offensive_microconcepts",{}); v=tf.get("value_purpose",{})
    claims=[]; summary=[]

    h=d.get("defensive_action_height",{}); hx=h.get("value")
    if hx is not None:
        text=(f"La altura media de las acciones defensivas es x={hx:.1f}/120 ({h.get('band','perfil no clasificado')}). "
              "EFOS la interpreta como altura de intervención, no como posición exacta de la línea defensiva.")
        claims.append(_claim("tactical_defensive_height",text,{"mean_x":hx,"actions":h.get("actions")},h.get("source","EVENT"),h.get("confidence","HIGH"),h.get("limitation"),h.get("actions")))
        summary.append(text)

    cp=d.get("counterpress",{}); hp=d.get("high_press_share",{}); oppp=d.get("opponent_passes_under_pressure",{})
    cp_rate=cp.get("rate"); hp_rate=hp.get("rate"); press_rate=oppp.get("rate")
    if any(x is not None for x in [cp_rate,hp_rate,press_rate]):
        text=(f"Sin balón, el equipo registra {cp.get('per_match',0) or 0:.1f} acciones de counterpress por partido; "
              f"{_pct(hp_rate) or 0:.1f}% de sus Pressure events aparecen en x≥80 y {_pct(press_rate) or 0:.1f}% de los pases rivales están etiquetados bajo presión.")
        claims.append(_claim("tactical_pressing_profile",text,{"counterpress":cp,"high_press_share":hp,"opponent_passes_under_pressure":oppp},"EVENT","HIGH","Describe frecuencia y localización; no demuestra por sí sola el mecanismo colectivo de presión.",cp.get("denominator")))
        summary.append(text)

    off=d.get("opponent_offside_outcomes",{})
    if off.get("count") is not None:
        text=(f"El rival acumula {off.get('count',0)} pases terminados en offside ({off.get('per_match',0) or 0:.2f} por partido). "
              "Es una señal compatible con coordinación de profundidad, pero no se etiqueta automáticamente como 'trampa de fuera de juego'.")
        claims.append(_claim("tactical_offside_proxy",text,{"opponent_offside_outcomes":off},off.get("source","EVENT_PROXY"),off.get("confidence","MEDIUM"),off.get("limitation"),off.get("denominator")))

    pa=b.get("pressure_attraction_passes",{}); pr=b.get("pressure_release_success",{}); tm=b.get("third_man_progression_proxy",{}); hs=b.get("halfspace_entries",{})
    if pa.get("count") is not None:
        rr=_pct(pr.get("rate"))
        text=(f"EFOS detecta {pa.get('count',0)} pases completados bajo presión antes de x=80 como proxy de atracción ('fishing'). "
              f"En {rr:.1f}% de esos casos" if rr is not None else f"EFOS detecta {pa.get('count',0)} pases de atracción; sin cobertura suficiente para medir la liberación posterior")
        if rr is not None:
            text += " la posesión encuentra una liberación progresiva dentro de la ventana secuencial configurada."
        claims.append(_claim("tactical_pressure_attraction",text,{"pressure_attraction":pa,"pressure_release":pr},"SEQUENCE_PROXY","MEDIUM","Proxy secuencial; no prueba intención deliberada de atraer presión.",pa.get("denominator")))
        summary.append(text)

    text=(f"En progresión se observan {hs.get('per_match',0) or 0:.1f} entradas a half-space por partido y "
          f"{tm.get('per_match',0) or 0:.1f} cadenas A→B→C progresivas por partido como proxy de tercer hombre.")
    claims.append(_claim("tactical_progression_patterns",text,{"halfspace_entries":hs,"third_man_progression_proxy":tm},"EVENT/SEQUENCE_PROXY","MEDIUM","Las zonas y la regla A→B→C son definiciones operativas; no observan movimientos sin balón.",(hs.get("denominator") or 0)))
    summary.append(text)

    ali=o.get("cross_to_danger_zone_proxy",{}); inter=o.get("interval_entries",{})
    text=(f"En último tercio aparecen {inter.get('per_match',0) or 0:.1f} pases por partido hacia el intervalo central-lateral y "
          f"{ali.get('per_match',0) or 0:.1f} centros por partido que cumplen la geometría del proxy 'Aliup'.")
    claims.append(_claim("tactical_offensive_microconcepts",text,{"interval_entries":inter,"cross_to_danger_zone_proxy":ali},"EVENT_PROXY","MEDIUM" if inter.get("count",0) else "LOW","El proxy Aliup no identifica rosca, pierna cambiada ni receptor/segundo palo real; los intervalos son zonas configurables.",(inter.get("denominator") or 0)))
    summary.append(text)

    xg=v.get("xg",{}); obv=v.get("obv",{})
    if xg.get("total") is not None or obv.get("total_net") is not None:
        text=(f"La capa de valor acumula xG={xg.get('total') if xg.get('total') is not None else 'N/A'} "
              f"({xg.get('per_match') if xg.get('per_match') is not None else 'N/A'} por partido) y OBV neto={obv.get('total_net') if obv.get('total_net') is not None else 'N/A'}.")
        claims.append(_claim("tactical_value_layer",text,{"xg":xg,"obv":obv},"EVENT_MODEL","HIGH" if xg.get("total") is not None else "MEDIUM","xG/OBV expresan valor esperado; no prueban el principio táctico que originó la acción.",xg.get("shots",0)))

    return {
        "summary": summary[:5],
        "claims": claims,
        "defensive_profile": d,
        "construction_progression": b,
        "offensive_microconcepts": o,
        "value_purpose": v,
        "weekly_planning_hypotheses": tf.get("weekly_planning_hypotheses",[]),
        "terminology": tf.get("terminology",{}),
        "methodological_guardrail": tf.get("methodological_guardrail"),
        "data_quality": tf.get("data_quality",{}),
    }
