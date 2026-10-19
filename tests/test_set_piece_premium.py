"""Premium storytelling is evidence-first; 3D never supplies physics or invented chains."""
import pandas as pd
import numpy as np
from intelligence.set_piece_patterns import KIND_CORNER,premium_story_profile
from visualization.set_piece_story_3d import available_views, select_view, spatial_illustration


def make_events(n=36):
    rows=[]
    for i in range(n):
        # Same spatial pattern across 4 matches; 3 real traced chains, rest no documented P1.
        rows.append(dict(kind=KIND_CORNER,side='A favor',flank='Derecha',
            target_zone='Zona central (aprox.)',set_piece_id=str(i),
            match_id=f'm{i%4}',period=1,t0=i+1,executor='Taker',
            first_registered_player='Receiver' if i<4 else None,
            first_shooter='Shooter' if i<4 else None,
            shot_generated=i%2==0,goal=False,shot_zone='Centro del área',
            xg_coverage='COMPLETE' if i%2==0 else 'NO_SHOT',
            xg=.12 if i%2==0 else 0.,
            start_x=120.,start_y=80.,end_x=110.,end_y=40.,
            pass_height_name='High Pass' if i%3==0 else None))
    return pd.DataFrame(rows)


def test_story_uses_actual_repeated_pattern():
    d=make_events()
    p=premium_story_profile(d,KIND_CORNER,'A favor')
    assert p['n']==36 and p['n_matches']==4
    assert p['frequent']['n']==36
    assert p['productive']['n_xg_valid']==36
    assert p['productive']['xg_mean']==.06
    assert p['sequence']['n']==4 and p['sequence']['n_matches']==4
    assert p['headline'].startswith('Derecha →')
    assert p['by_flank'][0]['status']=='insufficient'
    assert p['by_flank'][1]['share_pct']==100


def test_never_fabricate_a_common_sequence_from_independent_modal_players():
    d=make_events()
    d.loc[:, 'first_shooter']=None
    p=premium_story_profile(d,KIND_CORNER,'A favor')
    assert p['sequence'] is None
    assert p['frequent'] is not None


def test_small_sample_is_exploratory():
    d=make_events(3)
    p=premium_story_profile(d,KIND_CORNER,'A favor')
    assert p['frequent'] is None
    assert p['productive'] is None
    assert 'muestra mínima' in p['intro']


def test_3d_is_capped_and_uses_only_verified_input_coordinates():
    d=make_events()
    d.loc[0,'end_x']=np.nan
    p=premium_story_profile(d,KIND_CORNER,'A favor')
    opts=available_views(d,p)
    assert 'Patrón más repetido' in opts
    selected=select_view(d,p,'Patrón más repetido')
    assert len(selected)==36  # Selector conserva eventos; el render valida coordenadas.
    fig,meta=spatial_illustration(selected,max_events=5)
    assert meta['observations_with_coordinates']==35
    assert meta['drawn']==5
    assert meta['method']=='ILLUSTRATIVE_CATEGORICAL_RELIEF_NOT_MEASURED_TRAJECTORY'
    assert fig.layout.scene.zaxis.visible is False  # Sin alturas físicas cuantificadas


def test_views_empty_and_malformed_columns():
    d=make_events().iloc[:0]
    opts=available_views(d,{'frequent':None,'productive':None})
    assert opts==[]
    fig,meta=spatial_illustration(d)
    assert meta['drawn']==0
    assert len(fig.data)>0  # Empty pitch shown, not invented kicks
