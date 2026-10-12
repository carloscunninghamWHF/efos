"""Regression tests for EFOS corner sequence engine."""
import math
import numpy as np
import pandas as pd
from intelligence.corner_engine import analyze_corners, build_corner_sequences

def event(**kw):
    row=dict(match_id="m1",period=1,possession=7,event_type="Pass",team="America",
             type_name=None,timestamp_seconds=0,index=0,location_x=110,location_y=0,
             end_location_x=112,end_location_y=34,statsbomb_xg=np.nan,shot_outcome=None,
             pass_outcome=None,player="J1",event_id=None,minute=10,pass_recipient_name=None)
    row.update(kw)
    return row

def sample():
    return pd.DataFrame([
        event(index=1,event_id="C1",timestamp_seconds=600,type_name="Corner",player="Taker",
              pass_recipient_name="Declared"),
        event(index=2,event_id="R1",timestamp_seconds=601,event_type="Ball Receipt*",player="Receiver"),
        event(index=3,event_id="S1",timestamp_seconds=604,event_type="Shot",player="A2",statsbomb_xg=.12),
        event(index=4,event_id="S2",timestamp_seconds=607,event_type="Shot",player="A3",statsbomb_xg=.08,
              shot_outcome="Goal"),
        event(index=5,event_id="C2",timestamp_seconds=650,type_name="Corner",team="Rival",
              possession=9,location_y=80,end_location_y=39),
        event(index=6,event_id="A2",timestamp_seconds=652,event_type="Clearance",team="America",possession=9),
        event(index=7,event_id="C3",timestamp_seconds=720,type_name="Corner",possession=11),
        event(index=8,event_id="S4",timestamp_seconds=722,event_type="Shot",possession=11,statsbomb_xg=np.nan),
        event(index=9,event_id="NO",timestamp_seconds=606,event_type="Shot",possession=8,statsbomb_xg=.9),
        event(index=10,event_id="OTHER",timestamp_seconds=605,event_type="Shot",match_id="m2",statsbomb_xg=.9)
    ])

def test_sequence_and_evidence():
    d,s,claims=analyze_corners(sample(),"America")
    assert len(d)==3
    c=d.set_index("corner_id").loc["C1"]
    assert c["first_registered_player"]=="Receiver"
    assert c["recipient_declared"]=="Declared"
    assert c["shot_count"]==2
    assert abs(c["corner_xg"]-.20)<1e-12
    assert c["goal"]
    assert len(claims)==2
    assert s["sides"]["A favor"]["n_corners"]==2

def test_missing_xg_never_zeroed():
    d,summary,_=analyze_corners(sample(),"America")
    c=d.set_index("corner_id").loc["C3"]
    assert c["shot_generated"]
    assert math.isnan(c["corner_xg"])
    assert c["xg_coverage"]=="MISSING_SHOT_XG"
    assert summary["sides"]["A favor"]["xg_coverage_pct"]==50.0

def test_defensive_intervention_and_360():
    frames={"C1":{"freeze_frame":[
        {"teammate":True,"location":[109,34]},
        {"teammate":False,"location":[104,37]},
        {"teammate":False,"location":[80,30]}
    ]}}
    d=build_corner_sequences(sample(),"America",frames).set_index("corner_id")
    assert d.loc["C1","has_360_snapshot"]
    assert d.loc["C1","attackers_visible_in_box"]==1
    assert d.loc["C1","defenders_visible_in_box"]==1
    assert d.loc["C2","first_registered_team"]=="America"
    assert not d.loc["C2","p1_team_matches_attacker"]

def test_two_corners_in_same_possession_do_not_share_shot():
    d=build_corner_sequences(pd.DataFrame([
        event(event_id="a",index=1,timestamp_seconds=1,type_name="Corner"),
        event(event_id="b",index=2,timestamp_seconds=4,type_name="Corner"),
        event(event_id="shot",index=3,timestamp_seconds=6,event_type="Shot",statsbomb_xg=.2),
    ]),"America").set_index("corner_id")
    assert d.loc["a","shot_count"]==0
    assert d.loc["b","shot_count"]==1

def test_missing_required_columns_fails():
    try:
        build_corner_sequences(pd.DataFrame({"team":["America"]}),"America")
    except ValueError as err:
        assert "period" in str(err)
    else:
        raise AssertionError("Missing columns must raise ValueError")
