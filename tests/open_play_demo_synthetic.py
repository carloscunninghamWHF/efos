"""DEMO VISUAL ÚNICAMENTE · Genera un dataset explícitamente sintético."""
import random
import pandas as pd


def make_demo(seed=25):
    rng=random.Random(seed); rows=[]; index=0
    opp='Rival de demostración'; me='América'; players=['Israel Reyes','Cristian Borja','Álvaro Fidalgo','Alejandro Zendejas','Ramón Juárez']
    poss=0
    for mid in ['DEMO-01','DEMO-02','DEMO-03']:
      index=0;poss=0
      for j in range(90):
        minute=2+j*.94;period=1 if minute<=45 else 2;style=j%3
        # América possession immediately prior to opponent's open-play possession.
        poss+=1;index+=1
        rows.append(dict(match_id=mid,period=period,index=index,possession=poss,team=me,possession_team=me,
            event_type='Pass',player=players[j%5],minute=minute-.02,second=0,play_pattern_name='Regular Play',
            type_name='',outcome_name='Incomplete' if style != 2 else 'Complete',location_x=75,location_y=32,end_location_x=69,end_location_y=35))
        poss+=1
        pattern=['From Ball Recovery','From Counter','Regular Play'][style]
        startx,starty=(62,30) if style==0 else ((25,60) if style==1 else (19,24))
        for k in range([3,3,7][style]):
          index+=1
          x=min(113,startx+k*(10 if style!=2 else 6)+rng.uniform(-5,5)); y=min(75,max(5,starty+rng.uniform(-14,14)))
          rows.append(dict(match_id=mid,period=period,index=index,possession=poss,team=opp,possession_team=opp,
             event_type='Pass',player='Rival '+str((k%5)+1),minute=minute+k*.015,second=0,
             play_pattern_name=pattern,type_name='',outcome_name='',location_x=x,location_y=y,
             end_location_x=min(118,x+8),end_location_y=min(78,y+rng.uniform(-8,8))))
          if rng.random()<.45:
            index+=1
            rows.append(dict(match_id=mid,period=period,index=index,possession=poss,team=me,possession_team=opp,
               event_type=rng.choice(['Pressure','Duel','Interception','Ball Recovery']),
               player=rng.choice(players),minute=minute+k*.015+.004,second=0,
               play_pattern_name=pattern,type_name='',outcome_name='',location_x=x+rng.uniform(-3,3),location_y=y+rng.uniform(-3,3)))
        if rng.random()<(.26 if style==1 else .10):
          index+=1
          rows.append(dict(match_id=mid,period=period,index=index,possession=poss,team=opp,possession_team=opp,
             event_type='Shot',player='Rival 9',minute=minute+.12,second=0,
             play_pattern_name=pattern,type_name='',outcome_name='Off T',shot_outcome='Off T',
             location_x=105,location_y=40,statsbomb_xg=.08))
    return pd.DataFrame(rows)
