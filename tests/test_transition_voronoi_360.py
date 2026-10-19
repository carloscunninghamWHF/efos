"""Voronoi de transiciones con StatsBomb 360: carga, orientación, métricas e invariancia de nombre."""
import json

import numpy as np
import pandas as pd

from intelligence import transition_voronoi_360 as T

VIS = [0, 0, 120, 0, 120, 80, 0, 80]


def _ff(players):
    return [{"teammate": t, "actor": a, "keeper": k, "location": [x, y]} for x, y, t, a, k in players]


def _frames():
    # Recuperación de A en (50, 40): A ataca hacia la derecha; dos atacantes libres por delante, defensa lejos.
    rec = _ff([(50, 40, True, True, False), (65, 20, True, False, False), (66, 60, True, False, False),
               (45, 30, True, False, False), (100, 40, False, False, False), (98, 25, False, False, False),
               (97, 55, False, False, False), (118, 40, False, False, True)])
    # Pérdida de A: pase fallado desde (60, 40) a (80, 40). Fotografía orientada hacia el ataque de A.
    loss = _ff([(60, 40, True, True, False), (78, 42, True, False, False), (75, 36, True, False, False),
                (70, 30, True, False, False), (82, 40, False, False, False), (90, 50, False, False, False),
                (95, 30, False, False, False), (2, 40, True, False, True)])
    # 4 s después: evento del rival (B) con A más compacto alrededor del balón.
    after = _ff([(38, 40, True, True, False), (40, 38, False, False, False), (41, 43, False, False, False),
                 (36, 36, False, False, False), (30, 45, True, False, False), (118, 40, False, False, True)])
    return {"r1": {"visible_area": VIS, "freeze_frame": rec}, "l1": {"visible_area": VIS, "freeze_frame": loss},
            "a1": {"visible_area": VIS, "freeze_frame": after}}


def _events(team="A", rival="B"):
    base = {"match_id": 1, "period": 1, "minute": 10, "second": 0, "possession": 1, "type_name": np.nan,
            "outcome_name": np.nan, "pass_outcome": np.nan, "end_location_x": np.nan, "end_location_y": np.nan,
            "statsbomb_xg": np.nan, "shot_outcome": np.nan, "play_pattern_name": "Regular Play"}
    rows = [
        {**base, "event_id": "r1", "team": team, "player": "Rec", "event_type": "Ball Recovery", "timestamp_seconds": 600.0,
         "location_x": 50, "location_y": 40, "possession": 2},
        {**base, "event_id": "p1", "team": team, "player": "Rec", "event_type": "Pass", "timestamp_seconds": 603.0,
         "location_x": 50, "location_y": 40, "end_location_x": 70, "end_location_y": 60, "possession": 2},
        {**base, "event_id": "s1", "team": team, "player": "Nine", "event_type": "Shot", "timestamp_seconds": 609.0,
         "location_x": 105, "location_y": 40, "statsbomb_xg": 0.3, "shot_outcome": "Goal", "possession": 2},
        {**base, "event_id": "l1", "team": team, "player": "Loser", "event_type": "Pass", "timestamp_seconds": 700.0,
         "location_x": 60, "location_y": 40, "end_location_x": 80, "end_location_y": 40, "pass_outcome": "Incomplete", "possession": 3},
        {**base, "event_id": "a1", "team": rival, "player": "R", "event_type": "Carry", "timestamp_seconds": 704.0,
         "location_x": 38, "location_y": 40, "possession": 4},
    ]
    return pd.DataFrame(rows)


def test_load_frames_from_folder_and_find_dir(tmp_path):
    raw = tmp_path / "data" / "raw"; (raw / "statsbomb").mkdir(parents=True); (raw / "stastbomb_360").mkdir()
    csv = raw / "statsbomb" / "x.csv"; csv.write_text("a\n1\n")
    (raw / "stastbomb_360" / "1.json").write_text(json.dumps([{"event_uuid": "e1", "visible_area": VIS, "freeze_frame": []}]))
    d = T.find_360_dir([csv])
    assert d is not None and d.name == "stastbomb_360"
    fr = T.load_frames(d)
    assert set(fr) == {"e1"} and fr["e1"]["match_id"] == "1"
    assert T.load_frames(d, match_ids=["2"]) == {}


def test_loss_snapshot_is_flipped_and_loser_excluded():
    fr = _frames()["l1"]
    s = T.snapshot(fr, (80, 40), actor_team_attacks=False)
    # el rival (B) pasa a atacar hacia x = 120: el balón en (80, 40) queda en (40, 40)
    assert np.allclose(s["ball"], [40, 40])
    assert len(s["att"]) == 3 and len(s["dfn"]) == 5
    m, L = T.analyze_snapshot(s)
    # tras girar: compañeros a 2,8 / 6,4 / 14,1 yd del balón → 1 a < 5 m y 2 a < 10 m; el que pierde y el portero no cuentan
    assert m["def_10m"] == 2 and m["def_5m"] == 1


def test_build_moments_and_readings():
    res = T.build_moments(_events(), "A", _frames())
    mom = res["momentos"]
    o = mom[(mom["fase"] == "Ofensiva") & (mom["quien"] == "equipo")].iloc[0]
    assert o["acaba_en_tiro"] and o["gol_siguiente"] and abs(o["xg_siguiente"] - 0.3) < 1e-9
    assert o["atac_libres"] >= 2 and o["carril_progresion"] == "Interior derecho"
    d = mom[(mom["fase"] == "Defensiva") & (mom["quien"] == "equipo")].iloc[0]
    assert d["seg_despues"] == 4 and not np.isnan(d["bloque_m2_despues"])
    R = T.readings(mom, "A")
    assert set(R) == {"O1", "O2", "O3", "O4", "O5", "D1", "D2", "D3", "D4", "D5"}
    assert all(R[k]["texto"] for k in R)


def test_team_name_invariance():
    a = T.build_moments(_events("A", "B"), "A", _frames())["momentos"]
    b = T.build_moments(_events("Manchester City", "Arsenal"), "Manchester City", _frames())["momentos"]
    cols = ["esp_atac_pct", "libre_pct", "apoyos_20m", "atac_libres", "def_10m", "coberturas", "bloque_m2"]
    assert np.allclose(a[cols].to_numpy(float), b[cols].to_numpy(float), equal_nan=True)


def test_grid_rate_shapes():
    res = T.build_moments(_events(), "A", _frames())
    keys = list(res["momentos"]["clave"])
    rate, n = T.grid_rate(keys, res["capas"], "own_att", "ahead", min_n=1)
    assert rate.shape == T.GX.shape and np.nanmax(rate) <= 1 and np.nanmin(rate) >= 0


def test_animation_sequence_orientation_and_outputs():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "visualization"))
    import transition_animation as A
    ev = _events()
    steps = A.build_sequence(ev, _frames(), "A", "r1")
    # solo la recuperación tiene fotografía 360 (el pase y el remate no): un único paso
    assert [s["event_type"] for s in steps] == ["Ball Recovery"]
    assert steps[0]["is_team"].sum() == 4 and (~steps[0]["is_team"]).sum() == 4
    # pérdida de A: el rival B ataca hacia la izquierda en la vista (A siempre ataca a la derecha)
    d = A.build_sequence(ev, _frames(), "A", "l1")
    # la foto del rival viene orientada hacia su ataque: se gira para que A siga atacando a la derecha
    assert d[0]["ball_end"] == (80.0, 40.0) and d[1]["ball"] == (82.0, 40.0)
    assert d[1]["is_team"].sum() == 4            # en la foto del rival, los «no compañeros» son de A
    path = A.ball_path(d, sub=4)
    assert path[0][1:] == (60.0, 40.0) and len(path) > len(d)
    fig = A.plotly_animation(d, "A", "t", sub_frames=4)
    assert len(fig.frames) == len(path)
    gif = A.gif_bytes(d, "A", "t", sub_frames=2, fps=4)
    assert gif[:3] == b"GIF"


def test_animation_is_continuous_without_jumps():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "visualization"))
    import transition_animation as A
    d = A.build_sequence(_events(), _frames(), "A", "l1")
    tl = A.timeline(d, fps=10)
    t = np.array([f["t"] for f in tl])
    # tiempo uniforme: ningún fotograma se repite ni se detiene en el evento
    assert np.all(np.diff(t) > 0) and np.ptp(np.diff(t)) < 0.05
    # el balón avanza sin saltos (máx. ~ velocidad de un pase por fotograma)
    b = np.array([f["ball"] for f in tl])
    assert np.max(np.linalg.norm(np.diff(b, axis=0), axis=1)) < 8
    # los jugadores emparejados se desplazan de forma continua; quien no se empareja aparece/desaparece con alpha
    k0 = [f for f in tl if f["k"] == 0]
    assert len(k0) >= 2 and all(len(f["xy"]) == len(k0[0]["xy"]) for f in k0)
    assert np.max(np.abs(np.diff([f["xy"] for f in k0], axis=0))) < 3
    assert k0[0]["alpha"].min() >= 0 and k0[0]["alpha"].max() <= 1
