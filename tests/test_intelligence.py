import sys
from pathlib import Path
import pandas as pd
import numpy as np
sys.path.insert(0,str(Path(__file__).parent.parent))
from sprint2.objects import mark_losses, build_loss_responses
from sprint2.intelligence import build_cts


def test_mark_losses_real_names():
    e=pd.DataFrame({'event_type_name':['Pass','Carries','Dispossessed','Dribble'],'outcome_name':['Incomplete',None,None,'Incomplete']})
    r=mark_losses(e)
    assert r.is_loss.tolist()==[True,False,True,True]


def test_loss_response_uses_elapsed_time():
    e=pd.DataFrame({
      'id':['l','p'],'match_id':[1,1],'period':[1,1],'index':[1,2],'minute':[1,1],'second':[0,4],
      'event_type_name':['Dispossessed','Pressure'],'outcome_name':[None,None],'team_name':['A','A'],
      'player_name':['x','y'],'location_x':[50,51],'location_y':[40,40]})
    r=build_loss_responses(e,5)
    assert bool(r.iloc[0].response_within_5s)
    assert r.iloc[0].response_delta_s==4


def test_cts_is_bounded():
    d=pd.DataFrame({
      'match_id':[1,1,2,2],'team_name':['América','B','América','C'],
      'buildup_passes_per_poss':[2,1,3,1],'pass_completion':[.9,.8,.85,.7],
      'progressions_per_poss':[.2,.1,.3,.1],'final_third_actions_per_poss':[2,1,3,1],
      'shots_per_poss':[.1,.05,.2,.05],'xg_per_shot':[.1,.08,.12,.07],
      'pressure_events_per_100_opp_passes':[20,10,21,9],'ppda':[5,10,4,12],'high_press_share':[.4,.2,.5,.1],
      'recovery_5s_rate':[.5,.2,.6,.1],'counterpress_share':[.4,.2,.5,.1]})
    _,c=build_cts(d)
    assert c.score.between(0,100).all()
