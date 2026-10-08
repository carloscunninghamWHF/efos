"""Render EFOS Coach Story as a coach-facing, evidence-first Markdown report."""
from __future__ import annotations


def _conf(x):
    return f"**Confianza:** {x}"


def _fmt(v, n=2, suffix=""):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{n}f}{suffix}"
    except Exception:
        return str(v)


def _metric_line(label: str, metric: dict, rate_as_pct: bool = False) -> str:
    value = metric.get("value")
    count = metric.get("count")
    rate = metric.get("rate")
    per_match = metric.get("per_match")
    parts=[]
    if value is not None: parts.append(_fmt(value,2))
    if count is not None: parts.append(f"n={int(count)}")
    if per_match is not None: parts.append(f"{float(per_match):.2f}/partido")
    if rate is not None: parts.append(f"{100*float(rate):.1f}%" if rate_as_pct else f"rate={float(rate):.3f}")
    return f"| {label} | {' · '.join(parts) if parts else 'N/A'} | {metric.get('confidence','N/A')} | {metric.get('source','N/A')} |"


def render_coach_story_md(story: dict, evidence: dict) -> str:
    s=story; sys=s["system_identity"]; p=s["pressure_resistance"]; t=s["defensive_traps"]
    lines=[]; meta=s.get("analysis_metadata",{})
    lines += [f"# {s['title']}","",f"> **Método:** {s['method']}",""]
    if meta:
        lines += [
            f"> **Equipo focal:** {meta.get('focal_team','N/A')} · **Partidos:** {meta.get('matches_analyzed','N/A')} · **Eventos del equipo:** {meta.get('team_events','N/A')} · **Formato:** {meta.get('input_format','N/A')}",
            f"> **Archivos:** {meta.get('files_loaded','N/A')} · **Selección:** {meta.get('team_selection_mode','N/A')} · **Perfil:** `{meta.get('formula_profile','N/A')}`",
            ""
        ]

    # Coach-first opening
    tf=s.get("tactical_framework",{})
    ex=s.get("executive_summary",{})
    lines += ["## Coach Story — en 30 segundos","",ex.get("narrative",s.get("conclusion",sys.get("overview",{}).get("claim",""))),""]
    if ex.get("key_question"):
        lines += [f"> **La pregunta clave:** {ex['key_question']}",""]
    if tf.get("summary"):
        lines += ["### Lo que EFOS encontró"]
        for i,x in enumerate(tf["summary"][:5],1): lines.append(f"**{i:02d}.** {x}")
        lines.append("")

    lines += ["## 1. Identidad general del sistema","",sys["overview"]["claim"],"",_conf(sys["overview"]["confidence"]),""]
    lines += ["### Dimensiones ESI","","| Dimensión | Valor | Lectura |","|---|---:|---|"]
    for c in sys["claims"]:
        m=c["evidence"]["metric"]; v=c["evidence"]["value"]
        lines.append(f"| {m} | {v:.2f} | {c['claim']} |")
    lines += ["","> Las comparaciones son relativas dentro del modelo/muestra; no son benchmarks absolutos de liga.",""]

    ctx=s.get("contextual_behavior",{})
    lines += ["## 2. Identidad según el marcador",""]
    if ctx.get("rows"):
        lines += ["| Estado | ESI | OC | HPS | RPS | DS | DER | Eventos |","|---|---:|---:|---:|---:|---:|---:|---:|"]
        state_labels={"winning":"Ganando","drawing":"Empatando","losing":"Perdiendo"}
        for r in ctx["rows"]:
            lines.append(f"| {state_labels.get(r['score_state'],r['score_state'])} | {r['ESI']:.2f} | {r['OC']:.2f} | {r['HPS']:.2f} | {r['RPS']:.2f} | {r['DS']:.2f} | {r['DER']:.2f} | {r['n_events']} |")
        if ctx.get("claims"): lines += ["",ctx["claims"][0]["claim"],"",_conf(ctx["claims"][0]["confidence"]),""]
    else: lines += ["No hay contexto de marcador disponible.",""]

    lines += ["## 3. Comportamiento bajo presión","",p["claims"][0]["claim"],"",p["claims"][1]["claim"],"",_conf(p["claims"][0]["confidence"]),""]
    comp=p["components_0_100"]
    lines += ["| Componente HPS | Valor (0–100) |","|---|---:|",
              f"| Retención | {comp['retention']:.2f} |",f"| Progresión | {comp['progression']:.2f} |",
              f"| Preservación de valor | {comp['value_preservation']:.2f} |",f"| Estabilidad de decisión | {comp['decision_stability']:.2f} |",""]
    if len(p.get("claims",[]))>2:
        lines += ["### Presión impuesta al rival","",p["claims"][2]["claim"],"", "| Componente PCI | Media | Cobertura |","|---|---:|---:|"]
        labels={"direct_pressure":"Presión directa","nearby_pressure":"Presión cercana","boundary_constraint":"Confinamiento por banda","defensive_responsibility":"DefR","control_constraint":"Restricción de control","lane_closure":"Cierre de líneas"}
        for k,v in p.get("components_imposed",{}).items():
            mean="N/A" if v.get("mean") is None else f"{v['mean']:.3f}"
            lines.append(f"| {labels.get(k,k)} | {mean} | {v.get('coverage_pct',0):.1f}% |")
        lines.append("")

    dims=sys["dimensions"]
    lines += ["## 4. Estructura y respuesta defensiva","",
              f"DS = {dims.get('DS',0):.2f} y DER = {dims.get('DER',0):.2f}. EFOS trata organización/decisión y recuperación tras pérdida como dimensiones diferentes. Su distancia describe una asimetría del perfil, no una falla automática.",""]

    dyn=s.get("dynamic_states",{})
    lines += ["## 5. Momentos del partido",""]
    if dyn.get("claims"):
        lines += [dyn["claims"][0]["claim"],"",_conf(dyn["claims"][0]["confidence"]),"", "| Estado interno | Ventanas | Share |","|---|---:|---:|"]
        moment_labels={"stability":"Control","adaptation":"Recuperación / adaptación","tension":"Presión creciente","fragility":"Inestabilidad","collapse":"Ruptura estructural"}
        for k,v in dyn.get("state_distribution",{}).items(): lines.append(f"| {moment_labels.get(k,k)} | {v['windows']} | {v['share_pct']:.1f}% |")
        lines.append("")
    else: lines += ["No hay suficientes ventanas dinámicas.",""]

    lines += ["## 6. Principios de juego candidatos",""]
    if s["coach_principles"]:
        lines += ["| Patrón candidato | Incidencia | Confidence score | Evidencia | Fuente |","|---|---:|---:|---:|---|"]
        for r in s["coach_principles"]:
            lines.append(f"| {r.get('display_name',r['principle'])} | {r['value_pct']:.1f}% | {r['confidence_score']:.1f}/100 | {r['evidence_n']} | {r['source']} |")
    else: lines.append("No se detectaron patrones candidatos con la muestra disponible.")
    lines += ["","> Un patrón candidato describe regularidad observada; no demuestra por sí mismo una instrucción deliberada del entrenador.",""]

    # Video-derived tactical framework
    lines += ["## 7. Marco teórico-táctico derivado de video","",
              "Esta capa traduce conceptos del marco táctico a reglas auditables sobre eventos StatsBomb. Cuando el dato no observa directamente el concepto, EFOS lo marca como **proxy**.",""]
    if tf:
        d=tf.get("defensive_profile",{}); b=tf.get("construction_progression",{}); o=tf.get("offensive_microconcepts",{}); v=tf.get("value_purpose",{})
        lines += ["### 7.1 Perfil defensivo","","| Señal | Resultado | Confianza | Fuente |","|---|---|---|---|"]
        lines.append(_metric_line("Altura de intervención defensiva",d.get("defensive_action_height",{})))
        lines.append(_metric_line("Counterpress",d.get("counterpress",{}),True))
        lines.append(_metric_line("Offsides del rival (proxy)",d.get("opponent_offside_outcomes",{}),True))
        lines.append(_metric_line("Pases rivales bajo presión",d.get("opponent_passes_under_pressure",{}),True))
        lines.append(_metric_line("Pressure events altos (x≥80)",d.get("high_press_share",{}),True)); lines.append("")

        lines += ["### 7.2 Construcción y progresión","","| Señal | Resultado | Confianza | Fuente |","|---|---|---|---|"]
        lines.append(_metric_line("Directicidad media",b.get("possession_directness",{})))
        lines.append(_metric_line("Atracción de presión / Fishing",b.get("pressure_attraction_passes",{}),True))
        lines.append(_metric_line("Liberación tras atraer presión",b.get("pressure_release_success",{}),True))
        lines.append(_metric_line("Entradas a half-space",b.get("halfspace_entries",{}),True))
        lines.append(_metric_line("Tercer hombre (proxy A→B→C)",b.get("third_man_progression_proxy",{}),True)); lines.append("")

        lines += ["### 7.3 Microconceptos ofensivos","","| Señal | Resultado | Confianza | Fuente |","|---|---|---|---|"]
        lines.append(_metric_line("Centro a zona peligrosa / Aliup proxy",o.get("cross_to_danger_zone_proxy",{}),True))
        lines.append(_metric_line("Ataque intervalo central-lateral",o.get("interval_entries",{}),True)); lines.append("")

        lines += ["### 7.4 Propósito y valor (PMDS / xG / OBV)","","| Variable | Total | Por partido | Lectura |","|---|---:|---:|---|"]
        xg=v.get("xg",{}); obv=v.get("obv",{})
        lines.append(f"| xG | {_fmt(xg.get('total'),2)} | {_fmt(xg.get('per_match'),3)} | Calidad esperada de los remates |")
        lines.append(f"| OBV neto | {_fmt(obv.get('total_net'),3)} | {_fmt(obv.get('per_match'),3)} | Cambio de valor esperado asociado a acciones elegibles |")
        lines.append("")

        planning=tf.get("weekly_planning_hypotheses",[])
        if planning:
            lines += ["### 7.5 Hipótesis de foco semanal (estructura de microciclo del marco aportado)","",
                      "> No es una prescripción de carga ni un plan físico. Es un puente entre hallazgos de EFOS y temas técnico-tácticos a discutir con el staff.","",
                      "| Día | Tema | Foco sugerido por la evidencia | Requiere scouting rival |","|---|---|---|---|"]
            for r in planning:
                lines.append(f"| {r['day']} | {r['theme']} | {r['focus']} | {'Sí' if r.get('requires_opponent_data') else 'No'} |")
            lines.append("")
        lines += [f"> **Guardrail:** {tf.get('methodological_guardrail','Los proxies no prueban intención táctica.')} ",""]
    else:
        lines += ["No hay datos suficientes para construir el marco táctico.",""]

    lines += ["## 8. Defensive Traps","",t["claims"][0]["claim"],"",_conf(t["claims"][0]["confidence"]),""]
    if t["outcome_distribution"]:
        lines += ["**Outcomes más frecuentes en traps clasificados como exitosos:**",""]
        for k,v in t["outcome_distribution"].items(): lines.append(f"- {k}: {v}")
        lines.append("")

    sig=s.get("coach_tactical_signature_interpretation",{})
    lines += ["## 9. Coach Tactical Signature","", "CTS es un **vector descriptivo**, no una calificación global del entrenador.","", "| Componente CTS | Valor | Qué representa |","|---|---:|---|"]
    for r in sig.get("components",[]):
        val='N/A' if r['value'] is None else f"{r['value']:.2f}"
        lines.append(f"| {r['component']} | {val} | {r['meaning']} |")
    if sig.get("claims"): lines += ["",_conf(sig["claims"][0]["confidence"]),""]

    pp=s.get("player_participation",{})
    lines += ["## 10. Participación individual en último tercio (LAP)",""]
    if pp.get("claims"): lines += [pp["claims"][0]["claim"],"",_conf(pp["claims"][0]["confidence"]),""]
    if pp.get("players"):
        lines += ["| Jugador | LAP | Acciones críticas | Acciones último tercio | xG | xA |","|---|---:|---:|---:|---:|---:|"]
        for r in pp["players"]:
            lines.append(f"| {r['player']} | {r['LAP']:.1f}% | {r['critical_actions']} | {r['final_third_actions']} | {r['xG']:.3f} | {r['xA']:.3f} |")
        lines += ["","> LAP no es un ranking de calidad; mide participación proporcional dentro de la definición de acciones críticas.",""]

    te=s["temporal_evolution"]
    lines += ["## 11. Evolución dentro de la muestra",""]
    if te.get("phases"):
        order_text="fecha calendario" if te.get("ordering")=="calendar_date" else "orden de aparición del dataset"
        lines += [f"La muestra se divide en tres bloques usando **{order_text}**.","", "| Fase | Partidos | ESI | OC | HPS | RPS | DS | DER |","|---|---:|---:|---:|---:|---:|---:|---:|"]
        for r in te["phases"]:
            lines.append(f"| {r['phase']} | {r['matches']} | {r['ESI']:.2f} | {r['OC']:.2f} | {r['HPS']:.2f} | {r['RPS']:.2f} | {r['DS']:.2f} | {r['DER']:.2f} |")
        lines += ["",te["claims"][0]["claim"],"",_conf(te["claims"][0]["confidence"]),""]
    else: lines += ["No hay suficientes ventanas para describir evolución.",""]

    ts=s.get("tactical_summary",{})
    lines += ["## 12. Resumen estadístico de soporte",""]
    if ts:
        rows=[("Eventos del equipo",ts.get("events")),("Pases de construcción",ts.get("build_up_passes")),("Progresiones profundas",ts.get("deep_progressions")),
              ("Eventos en último tercio",ts.get("final_third_events")),("Pressures",ts.get("pressures")),("X media de Pressure",ts.get("mean_pressure_x")),
              ("Tiros",ts.get("shots")),("Goles",ts.get("goals")),("Under-pressure rate",ts.get("under_pressure_rate"))]
        lines += ["| Variable | Valor |","|---|---:|"]
        for k,v in rows:
            if v is not None: lines.append(f"| {k} | {float(v):.4f} |" if isinstance(v,float) else f"| {k} | {v} |")
        if s.get("transition_response_rate") is not None: lines.append(f"| Respuesta ≤5s tras pérdida | {100*float(s['transition_response_rate']):.2f}% |")
        lines.append("")
    else: lines += ["No hay resumen táctico disponible.",""]

    lines += ["## 13. ¿Qué sistema parece estar construyendo?","",s["conclusion"],""]
    lines += ["## 14. Límites metodológicos",""]
    for x in s["limitations"]: lines.append(f"- {x}")
    lines += ["","## 15. Registro de evidencia","",f"Este reporte contiene **{len(evidence.get('claims',[]))} claims auditables** en `evidence.json`. Cada claim incluye evidencia, fuente, tamaño de muestra, confianza y limitación.",""]
    return "\n".join(lines)
