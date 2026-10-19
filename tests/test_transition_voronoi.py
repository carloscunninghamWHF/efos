"""Voronoi de transiciones: geometría, métricas, invariancia de nombre y ruta 360."""
import numpy as np
import pandas as pd

from intelligence import transition_voronoi as V


def _frame(att, dfn, ball):
    return {"attackers": np.array(att, float), "defenders": np.array(dfn, float), "ball": ball,
            "names_att": np.array([None] * len(att)), "names_def": np.array([None] * len(dfn))}


def test_voronoi_cells_cover_the_pitch():
    pts = np.array([[20, 20], [60, 40], [100, 60], [110, 10]], float)
    polys = V.voronoi_polygons(pts)
    area = sum(0.5 * abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1))) for p in polys)
    assert abs(area - V.LENGTH * V.WIDTH) < 1.0
    o = V.ownership(_frame(pts[:2], pts[2:], (60, 40)))
    assert o["owner"].max() == 3 and o["is_att"].sum() > 0


def test_open_space_and_pressure_metrics():
    # contraataque claro: atacantes libres por delante del balón, defensa lejos
    open_ = V.frame_metrics(_frame([[80, 40], [95, 20], [95, 60]],
                                   [[115, 40], [112, 30], [112, 50], [70, 40], [65, 20]], (80, 40)))
    # jugada cerrada: defensores rodeando al poseedor
    closed = V.frame_metrics(_frame([[80, 40], [70, 30]],
                                    [[83, 40], [82, 44], [82, 36], [90, 40], [100, 40]], (80, 40)))
    assert open_["O1_espacio_propio_pct"] > closed["O1_espacio_propio_pct"]
    assert open_["O5_atacantes_libres"] >= 1 and closed["O5_atacantes_libres"] == 0
    assert closed["D1_defensores_5m"] >= 3 > open_["D1_defensores_5m"]
    assert closed["D1_celda_poseedor_m2"] < open_["D1_celda_poseedor_m2"]
    assert closed["D4_coberturas"] >= 1


def _events(team="A"):
    rows = []

    def r(**k):
        base = {"match_id": 1, "team": team, "period": 1, "minute": 10, "second": 0, "possession": 2, "event_type": "Pass",
                "type_name": np.nan, "location_x": 60.0, "location_y": 40.0, "end_location_x": np.nan, "end_location_y": np.nan,
                "pass_outcome": np.nan, "outcome_name": np.nan, "player": "P", "statsbomb_xg": np.nan, "shot_outcome": np.nan,
                "play_pattern_name": "Regular Play"}
        base.update(k); rows.append(base)

    r(event_id="rec1", event_type="Ball Recovery", timestamp_seconds=100.0, location_x=55, player="Rec")
    r(event_id="shot1", event_type="Shot", timestamp_seconds=108.0, location_x=105, location_y=38, statsbomb_xg=0.3,
      shot_outcome="Goal", player="Shooter")
    r(event_id="rec2", team="B", possession=5, event_type="Ball Recovery", timestamp_seconds=300.0, location_x=60, player="RB")
    r(event_id="shot2", team="B", possession=5, event_type="Shot", timestamp_seconds=306.0, location_x=102, location_y=44,
      statsbomb_xg=0.1, player="SB")
    r(event_id="loss1", event_type="Dispossessed", possession=6, timestamp_seconds=400.0, location_x=70, location_y=40)
    r(event_id="next1", team="B", possession=6, event_type="Pass", timestamp_seconds=403.0, location_x=55, location_y=40)
    return pd.DataFrame(rows)


def _shot_frames():
    rows = []
    for eid in ("shot1", "shot2"):
        for x, y, tm in [(100, 30, True), (98, 50, True), (115, 40, False), (110, 35, False), (110, 45, False),
                         (104, 40, False), (95, 40, False), (106, 30, False)]:
            rows.append({"event_id": eid, "x": x, "y": y, "teammate": tm, "player": None, "position": None})
    return pd.DataFrame(rows)


def test_transitions_from_shot_frames_and_team_name_invariance():
    a = V.analyze_transitions(_events("A"), "A", _shot_frames())
    b = V.analyze_transitions(_events("Manchester City"), "Manchester City", _shot_frames())
    sa, sb = a["situaciones"], b["situaciones"]
    assert set(sa["lado"]) == {"Ofensiva", "Defensiva"} and a["fuente"] == "remate"
    off = sa[sa["lado"].eq("Ofensiva")].iloc[0]
    assert off["recuperador"] == "Rec" and off["seg_desde_recuperacion"] == 8 and off["gol"]
    cols = [k for k in V.METRIC_INFO if k in sa]
    assert np.allclose(sa[cols].to_numpy(float), sb[cols].to_numpy(float))
    reads = V.readings(sa, "A", a["base_organizada"], a["compactacion_360"], a["fuente"])
    assert [r["punto"] for r in reads] == ["O1", "O2", "O3", "O4", "O5", "D1", "D2", "D3", "D4", "D5"]
    assert "360" in reads[-1]["texto"]          # D5 explica que sin 360 no se mide el cambio pérdida → después


def test_360_frames_use_recovery_moment_and_compaction():
    def ff(pts):
        return {"freeze_frame": [{"location": [x, y], "teammate": tm, "actor": act, "keeper": False} for x, y, tm, act in pts]}

    frames360 = {
        "rec1": ff([(55, 40, True, True), (65, 20, True, False), (70, 60, True, False), (80, 40, False, False),
                    (75, 30, False, False), (75, 50, False, False), (90, 40, False, False), (100, 35, False, False),
                    (100, 45, False, False)]),
        "loss1": ff([(70, 40, True, True), (60, 30, True, False), (60, 50, True, False), (50, 20, True, False),
                     (50, 60, True, False), (72, 42, False, False), (80, 30, False, False)]),
        "next1": ff([(55, 40, True, True), (60, 45, False, False), (58, 35, False, False), (62, 40, False, False),
                     (64, 32, False, False), (64, 48, False, False)]),
    }
    out = V.analyze_transitions(_events("A"), "A", None, frames360)
    assert out["fuente"] == "360"
    off = out["situaciones"][out["situaciones"]["lado"].eq("Ofensiva")].iloc[0]
    assert off["momento"] == "recuperacion"
    comp = out["compactacion_360"]
    assert len(comp) == 1 and comp.iloc[0]["D5_area_bloque_m2_despues"] < comp.iloc[0]["D5_area_bloque_m2_perdida"]
    reads = V.readings(out["situaciones"], "A", out["base_organizada"], comp, out["fuente"])
    assert "se compacta" in reads[-1]["texto"]
