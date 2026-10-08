"""
synthetic.py
-------------
Genera datos sintéticos con la forma de eventos StatsBomb (+ opcionalmente
360 y PIP One) para que EFOS pueda correr de punta a punta sin
credenciales externas (sección 27, modo --demo obligatorio).

No pretende ser futbolísticamente realista en detalle — pretende ser
estructuralmente válido: mismos campos, mismos tipos, mismas relaciones
(match_id, possession, timestamps crecientes, etc.) que un dataset real.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from config_loader import get_parameters

EVENT_TYPES_WEIGHTED = [
    ("Pass", 0.38),
    ("Carry", 0.22),
    ("Pressure", 0.12),
    ("Ball Recovery", 0.06),
    ("Duel", 0.06),
    ("Interception", 0.04),
    ("Shot", 0.03),
    ("Dribble", 0.04),
    ("Clearance", 0.03),
    ("Substitution", 0.01),
    ("Miscontrol", 0.01),
]

PIP_ONE_EVENT_TYPES = [
    "preventive_cover", "decoy_run", "supporting_movement", "safety_pass",
    "defensive_cover", "coordinated_pressing", "off_ball_support", "recovery_movement",
]


def _weighted_choice(rng: random.Random, options: list[tuple[str, float]]) -> str:
    total = sum(w for _, w in options)
    r = rng.uniform(0, total)
    upto = 0.0
    for name, w in options:
        upto += w
        if upto >= r:
            return name
    return options[-1][0]


def generate_synthetic_match(match_id: str = "SYN_0001", seed: Optional[int] = None) -> dict:
    """
    Devuelve un dict con tres listas: 'events', 'frames_360', 'pip_one',
    listas para escribirse a JSON y ser leídas por los loaders reales
    de ingestion/. Esto garantiza que el modo demo ejercite exactamente
    el mismo código que el modo con datos reales.
    """
    params = get_parameters()["synthetic_data"]
    seed = seed if seed is not None else params["random_seed"]
    rng = random.Random(seed)

    teams = params["teams"]
    n_events = params["n_events_per_match"]
    include_360 = params["include_360"]
    include_pip = params["include_pip_one"]
    pip_rate = params["pip_one_event_rate"]

    events = []
    frames_360 = []
    pip_events = []

    possession = 0
    minute = 0
    second = 0.0
    current_team = rng.choice(teams)
    players = {t: [f"{t} Player {i}" for i in range(1, 12)] for t in teams}

    for i in range(1, n_events + 1):
        # Cambios de posesión ocasionales
        if rng.random() < 0.06:
            possession += 1
            current_team = rng.choice(teams)

        event_type = _weighted_choice(rng, EVENT_TYPES_WEIGHTED)
        player = rng.choice(players[current_team])

        x = round(rng.uniform(0, 120), 1)
        y = round(rng.uniform(0, 80), 1)

        second += rng.uniform(1.0, 4.0)
        if second >= 60:
            minute += int(second // 60)
            second = second % 60

        event_id = f"{match_id}-EVT-{i:05d}"

        event = {
            "match_id": match_id,
            "id": event_id,
            "index": i,
            "possession": possession,
            "possession_team": {"name": current_team},
            "team": {"name": current_team},
            "player": {"name": player},
            "minute": minute,
            "second": round(second, 2),
            "type": {"name": event_type},
            "location": [x, y],
            "under_pressure": rng.random() < 0.25,
            "duration": round(rng.uniform(0.2, 3.0), 2),
        }

        if event_type == "Pass":
            event["pass"] = {
                "outcome": ({"name": "Incomplete"} if rng.random() < 0.22 else None),
                "length": round(rng.uniform(5, 40), 1),
                "angle": round(rng.uniform(-3.14, 3.14), 2),
            }
        elif event_type == "Shot":
            event["shot"] = {
                "outcome": {"name": rng.choice(["Goal", "Saved", "Off T", "Blocked"])}
            }
        elif event_type == "Duel":
            event["duel"] = {
                "outcome": {"name": rng.choice(["Won", "Lost"])}
            }

        events.append(event)

        if include_360 and rng.random() < 0.5:
            opponent_team = [t for t in teams if t != current_team][0]
            frame_players = []
            for p in players[current_team]:
                frame_players.append({
                    "teammate": True,
                    "actor": p == player,
                    "keeper": False,
                    "location": [round(rng.uniform(0, 120), 1), round(rng.uniform(0, 80), 1)],
                })
            for _ in range(rng.randint(3, 8)):
                frame_players.append({
                    "teammate": False,
                    "actor": False,
                    "keeper": False,
                    "location": [round(rng.uniform(0, 120), 1), round(rng.uniform(0, 80), 1)],
                })
            frames_360.append({
                "event_uuid": event_id,
                "visible_area": [[0, 0], [120, 0], [120, 80], [0, 80]],
                "freeze_frame": frame_players,
            })

        if include_pip and rng.random() < pip_rate:
            pip_events.append({
                "match_id": match_id,
                "timestamp": round(minute * 60 + second + rng.uniform(-2, 2), 2),
                "team": current_team,
                "player": player,
                "event_type": rng.choice(PIP_ONE_EVENT_TYPES),
                "zone": rng.choice(["defensive_third", "middle_third", "attacking_third"]),
                "target_player": rng.choice(players[current_team]),
                "context": rng.choice(["build_up", "transition", "set_piece", "open_play"]),
                "confidence": round(rng.uniform(0.6, 1.0), 2),
                "analyst_id": "SYNTH_ANALYST_1",
            })

    return {"events": events, "frames_360": frames_360, "pip_one": pip_events}


def write_synthetic_dataset(output_dir: Path, match_id: str = "SYN_0001") -> dict:
    """
    Genera y escribe a disco events.json, frames_360.json y pip_one.json
    dentro de output_dir (típicamente data/raw/demo/). Devuelve las rutas.
    """
    import json

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = generate_synthetic_match(match_id=match_id)

    paths = {}
    for key, filename in [
        ("events", "events.json"),
        ("frames_360", "frames_360.json"),
        ("pip_one", "pip_one.json"),
    ]:
        path = output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dataset[key], f, indent=2, ensure_ascii=False)
        paths[key] = path

    return paths
