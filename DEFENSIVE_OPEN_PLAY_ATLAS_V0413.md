# EFOS v0.4.13 — Smart Defensive Atlas (integrated)

This increment integrates the user-provided **EFOS_Smart_Defensive_v0_4_13** visualization into the full EFOS v0.4.12 codebase without replacing the existing full-situation Smart Defensive Tactics engine or the Set Piece Story module.

## Changes

- `intelligence/defensive_open_play.py`: three operational **open-play-only** defensive scenarios, sequence-anchored to rival possessions; set-piece-origin possessions excluded.
- `visualization/defensive_open_play_maps.py`: comparative three-pitch atlas, real passes/carries and intervention mapping, defensive co-participation graph, chronological drill-down, 360 snapshots where supplied.
- `visualization/defensive_open_play_app.py`: editorial **story first**, three compact indicators, scenario atlas, then optional drilldowns and evidence.
- `run_sprint4.py`: precomputes open-play sequences and exposes them to the dashboard; exports `defensive_open_play_possessions.csv`. When 360 is provided, snapshot data is passed through unchanged.
- `visualization/efos_dashboard.py`: shows atlas as the primary organized-defense view and keeps v0.4.12 **full opposition attack (including corners, free kicks and throw-ins)** in an expandable secondary section.
- `tests/test_defensive_open_play_v0413.py`: adapted synthetic regression tests.

## Critical distinction

The two existing modules deliberately use different units and scenario definitions. The v0.4.13 atlas covers ONLY open play, while the earlier integrated engine includes restart possessions as distinct categories. Do **not** add denominators across these datasets or claim direct comparability without a matching sample.

3D flight/continuous player trajectories, fixed formations, marking types and off-ball runs are not reconstructed from event data. 360 can display **only** actual visible player coordinates at specific event snapshots when those frames are explicitly supplied.

## Run

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run visualization/efos_dashboard.py
```

No additional dependencies are necessary beyond the existing Plotly, pandas and Streamlit packages.

## Verification gates

- All existing regression tests and new open-play tests must pass.
- Compare situational and restart exclusion counts against the official matches.
- Inspect the 360 orientation and source metadata on at least one real possession before using the diagrams in a final presentation.
- Validate overall Streamlit UI and reports in your Mac environment.
