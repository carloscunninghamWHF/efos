import pandas as pd
import pytest
from intelligence.organized_defense_story import action_samples, build_defensive_story
from visualization.defense_story_maps import defensive_map


def sample(matches=4):
    rows=[]
    for i in range(matches):
        mid=f'M{i}'
        for j in range(12):
            rows.append(dict(match_id=mid,team='A',event_type='Pressure' if j%2 else 'Ball Recovery',location_x=87,location_y=35))
        for j in range(4):
            rows.append(dict(match_id=mid,team='A',event_type='Interception',location_x=25,location_y=45))
            rows.append(dict(match_id=mid,team='B',event_type='Pressure',location_x=55,location_y=10))
    return pd.DataFrame(rows)


def test_zone_summary_has_real_denominator():
    story=build_defensive_story(sample(),'A')
    assert story['matches']==4
    assert story['actions_with_coordinates']==64
    assert sum(z['n'] for z in story['zones'])==64
    assert story['zones'][2]['n']==48
    assert story['high_pressure_share']==100.0
    assert story['confidence']=='DESCRIPTIVE'
    assert story['claims'][0]['n']==64


def test_limited_sample_not_overstated():
    story=build_defensive_story(sample(1),'A')
    assert story['confidence']=='INSUFFICIENT'
    assert 'insuficiente' in story['summary']


def test_reject_missing_schema():
    with pytest.raises(ValueError):
        action_samples(pd.DataFrame({'team':['A']}),'A')


def test_missing_coordinates_not_miscounted():
    df=sample();df.loc[0,'location_x']=None
    assert len(action_samples(df,'A'))==63


def test_plot():
    fig=defensive_map(sample(),'A','Presiones')
    assert fig is not None
