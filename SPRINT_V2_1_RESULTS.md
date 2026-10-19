# EFOS Sprint v2.1 — Intelligence Engine

## Status
Competition-data execution completed on the two supplied América CSV files.

### Data audit
- Raw rows: 140,414
- Unique analytical events: 124,353
- Expanded freeze-frame rows separated: 13,781
- Matches: 38
- Audit issues: 0
- Automated tests: 31/31 passed

## New objects
- Possessions/sequences: 7,684
- N-5 rows preceding shots: 4,101
- Loss events evaluated for <=5s response: 8,101
- LAP players: 29
- América substitutions evaluated: 186

## Coach Tactical Signature — current implementation
Scores are percentiles against all 76 team-match observations (América + its direct opponent in each match).

- Construction: 57.93
- Progression: 65.29
- Attack: 57.69
- Defense: 59.22
- Transition: 55.98
- Adaptation: 17.24 (degree of contextual change, NOT quality)

IMPORTANT: Adaptation is a magnitude index. A low value means the measured tactical vector changes less across score states; it is not a negative performance grade.

## ESI
- OC: 77.05
- HPS: 65.93
- RPS: 80.89
- DS: 50.72
- DER: 39.81
- ESI: 62.88

The ESI weights are currently equal (0.20 each). They are an explicit modeling assumption, not an empirically learned truth.

## First candidate principles
These are candidates generated from predefined, testable hypotheses; they are not yet the final three Coach Story principles.

1. Progresión recurrente hacia último tercio
   - América: 0.294 progressions/possession
   - Opponents: 0.234
   - América >= direct opponent in 27/38 matches (71.1%)

2. Ataque de alto volumen
   - América: 0.082 shots/possession
   - Opponents: 0.055
   - América >= direct opponent in 26/38 matches (68.4%)

3. Ataque de alta calidad
   - América: 0.093 xG/shot
   - Opponents: 0.087
   - América >= direct opponent in 25/38 matches (65.8%)

Additional candidates:
- High territorial pressure: 24/38 matches
- <=5s reaction after loss: 23/38 matches
- Build-up frequency from own field: 20/38 matches

## Player system — LAP
Top current final-third participation shares:
- Brian Rodríguez: 14.45%; xG+xA 13.46
- Alejandro Zendejas: 10.76%; xG+xA 13.40
- Kevin Álvarez: 9.80%; xG+xA 3.75
- Álvaro Fidalgo: 6.94%; xG+xA 1.75
- Cristian Borja: 6.81%; xG+xA 3.32

LAP currently measures share of critical actions in X>80 (Pass, Carries, Dribble, Shot, Ball Receipt*). This definition is explicit and can be refined before final submission.

## Context
When drawing / losing / winning, América's mean possession directness is approximately:
- Drawing: 0.500
- Losing: 0.533
- Winning: 0.493

This suggests a more direct profile while losing, but it must be treated as a descriptive association until tested match-by-match and controlled for opponent/context.

## Methodological safeguards
- One EVENT row per unique event id.
- 360/freeze-frame kept as a one-to-many child table.
- <=5 second response is based on elapsed event timestamps, not event duration.
- Own goals count only the `Own Goal For` representation, avoiding double count of paired rows.
- Candidate principles compare América to the direct opponent in the same match.
- DTC labels are operational states, not psychological descriptions.

## Not final yet
Before freezing the three Coach Story principles, Sprint v2.2 should add:
1. automatic N-5 sequence/pattern mining rather than only predefined hypotheses;
2. within-match DTC windows instead of relying on match-level state alone;
3. set-piece P0/P1 features + CatBoost/SHAP;
4. final visualizations and uncertainty/sample-size annotations.
