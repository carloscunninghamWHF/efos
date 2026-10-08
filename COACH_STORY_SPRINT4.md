# EFOS Sprint 4 — Coach Story Layer

Sprint 4 termina en un producto analítico, no sólo en métricas. `run_sprint4.py` genera automáticamente:

- `metrics_summary.csv`: resumen numérico de ESI, dimensiones, PCI y traps.
- `coach_story.json`: narrativa estructurada para dashboard/RAG/API.
- `coach_story.pdf`: reporte ejecutivo visual del entrenador/equipo (entregable principal).
- `coach_story.md`: anexo textual/metodológico.
- `evidence.json`: registro auditable de cada claim con evidencia, fuente, N, confianza y limitación.

## Arquitectura

`Data -> Metrics -> Interpretation -> Evidence -> Coach Story`

La capa `interpretation/` nunca modifica los cálculos. Traduce resultados a significado futbolístico con límites explícitos.

## Secciones del reporte

1. Identidad general del sistema (ESI + OC/HPS/RPS/DS/DER)
2. Comportamiento bajo presión (PCI + HPS v2 y componentes)
3. Estructura y respuesta defensiva
4. Modelo de presión y principios candidatos
5. Defensive Traps (DTE experimental)
6. Coach Tactical Signature
7. Evolución dentro de la muestra (early/middle/late)
8. Síntesis del sistema observado
9. Límites metodológicos
10. Registro de evidencia

## Regla epistemológica

EFOS describe patrones observados. No convierte correlación en intención del entrenador. Si no hay tracking, no afirma TTI real. Si no hay fecha de partido, la evolución se presenta como orden del dataset, no cronología calendario.

## Cobertura analítica final

El reporte también describe ESI por estado del marcador, estados/transiciones DTC, CTS componente por componente, LAP de participación individual, evolución por bloques de muestra y el resumen táctico base. El objetivo es que cada output calculado tenga una lectura futbolística y un caveat metodológico correspondiente.


## Extensión v0.4.4 — Marco táctico derivado de video

El Coach Story incorpora una capa adicional de mecanismos tácticos observables/proxy: altura de intervención defensiva, counterpress, offside rival, presión al pasador, Fishing, liberación posterior, half-spaces, tercer hombre, intervalo central-lateral, centros a zona peligrosa, xG y OBV.

Los conceptos que event data no observa directamente se marcan como `EVENT_PROXY` o `SEQUENCE_PROXY`. La planificación semanal se presenta como hipótesis de foco técnico-táctico y no como prescripción de carga.
