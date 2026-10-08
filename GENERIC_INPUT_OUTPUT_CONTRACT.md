# EFOS v0.4 Sprint 4 — Generic Input/Output Contract

## Regla central

EFOS es **team-agnostic**: ninguna fórmula, umbral, interpretación o salida depende del nombre de un club.
Cambiar el equipo cambia los datos y, por tanto, los valores obtenidos; no cambia el pipeline analítico.

## CSV aceptados

### A. EFOS Normalized / Flat Events
Mínimo obligatorio:
- `team`
- `event_type`

Recomendado:
- `match_id`, `event_id`, `index`
- `possession`, `possession_team`
- `minute`, `second` o `timestamp_seconds`
- `location_x`, `location_y`, `end_location_x`, `end_location_y`
- `under_pressure`, `outcome_name`

Aliases básicos como `x/y`, `end_x/end_y`, `id`, `idx`, `type` se adaptan automáticamente.

### B. StatsBomb Wide CSV
Se detecta automáticamente mediante:
- `team_name`
- `event_type_name`
- `id`
- `match_id`
- `period`

Los campos avanzados disponibles (OBV, xPass, control_degree, DefR, etc.) se conservan.

## Selección del equipo

### Team-centric dataset
```bash
python run_sprint4.py --events club.csv --team auto --out outputs/club
```

`auto` elige el único equipo que aparece en todos los partidos. Si no existe un candidato inequívoco, EFOS se detiene y pide selección explícita; no adivina.

### Equipo explícito
```bash
python run_sprint4.py --events dataset.csv --team "Nombre exacto" --out outputs/team
```

### Dataset multi-equipo
```bash
python run_sprint4.py --events league.csv --all-teams --min-matches 5 --out outputs/league
```

Cada club recibe una subcarpeta y pasa por exactamente el mismo pipeline.

## Número de partidos

EFOS **no supone 38 partidos** ni ninguna longitud de competición. Analiza todos los partidos disponibles para el equipo focal.
`--expected-matches` es opcional y funciona sólo como control de integridad.

## Output garantizado por equipo

- `coach_story.md`
- `coach_story.json`
- `evidence.json`
- `input_profile.json`
- `team_coverage.csv`
- `metrics_summary.csv`
- `esi_overall.csv`
- `esi_by_context.csv`
- `match_windows.csv`
- `dtc_states.csv`
- `dtc_matrix.csv`
- `defensive_traps.csv`
- `trap_metrics.csv`
- `coach_tactical_signature.csv`
- `coach_principle_candidates.csv`
- `lap_players.csv`

Opcionales con `--export-event-tables`:
- `pressure_context_events.csv`
- `hps_actions.csv`

## Invariante metodológico

Para cualquier equipo, el flujo es:

`CSV -> Validation -> Team Scope -> Events/Sequences -> PCI -> HPS v2 -> ESI -> DTC -> Trap Engine -> CTS -> Principles -> Evidence -> Coach Story`

Los mismos pesos y thresholds de `config/` se aplican a todos los equipos. No existen ajustes ocultos por club.
