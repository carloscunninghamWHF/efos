from __future__ import annotations
import numpy as np
import pandas as pd
from .objects import build_loss_responses


def _safe_rate(num,den):
    return float(num/den) if den else np.nan


def team_match_features(events: pd.DataFrame) -> pd.DataFrame:
    e=events.copy()
    rows=[]
    for (mid,team),t in e.groupby(['match_id','team_name'],dropna=False):
        passes=t[t.event_type_name.eq('Pass')]
        completed=passes[~passes.outcome_name.isin(['Incomplete','Out','Pass Offside'])]
        buildup=passes[passes.location_x.lt(36)]
        prog=passes[(passes.location_x.lt(80)) & (passes.end_location_x.gt(80))]
        shots=t[t.event_type_name.eq('Shot')]
        pressures=t[t.event_type_name.eq('Pressure')]
        high_press=pressures[pressures.location_x.ge(72)]
        under=t[t.under_pressure.fillna(False).astype(bool)]
        under_pass=under[under.event_type_name.eq('Pass')]
        under_completed=under_pass[~under_pass.outcome_name.isin(['Incomplete','Out','Pass Offside'])]
        final_actions=t[t.location_x.gt(80)]
        setpieces=t[t.play_pattern_name.isin(['From Corner','From Free Kick','From Throw In'])]
        poss=t[['possession']].drop_duplicates().shape[0]
        # Opponent passes in own/build-up 60% used as PPDA denominator proxy; explicit and reproducible.
        opp=e[(e.match_id.eq(mid)) & (~e.team_name.eq(team))]
        opp_build_pass=opp[(opp.event_type_name.eq('Pass')) & (opp.location_x.lt(72))]
        def_actions=t[t.event_type_name.isin(['Pressure','Duel','Interception','Foul Committed']) & t.location_x.ge(48)]
        ppda=_safe_rate(len(opp_build_pass),len(def_actions))
        rows.append({
            'match_id':mid,'team_name':team,'events':len(t),'possessions':poss,
            'pass_completion':_safe_rate(len(completed),len(passes)),
            'buildup_passes_per_poss':_safe_rate(len(buildup),poss),
            'progressions_per_poss':_safe_rate(len(prog),poss),
            'final_third_actions_per_poss':_safe_rate(len(final_actions),poss),
            'shots_per_poss':_safe_rate(len(shots),poss),
            'xg_total':float(shots.statsbomb_xg.fillna(0).sum()),
            'xg_per_shot':_safe_rate(shots.statsbomb_xg.fillna(0).sum(),len(shots)),
            'pressure_events_per_100_opp_passes':_safe_rate(len(pressures)*100,max(len(opp[opp.event_type_name.eq('Pass')]),1)),
            'high_press_share':_safe_rate(len(high_press),len(pressures)),
            'ppda':ppda,
            'counterpress_share':_safe_rate(t.counterpress.fillna(False).astype(bool).sum(),len(pressures)) if len(pressures) else np.nan,
            'under_pressure_pass_completion':_safe_rate(len(under_completed),len(under_pass)),
            'mean_obv':float(pd.to_numeric(t.obv_total_net,errors='coerce').mean()),
            'mean_control_degree':float(pd.to_numeric(t.control_degree,errors='coerce').mean()),
            'mean_possession_directness':float(pd.to_numeric(t.possession_directness,errors='coerce').mean()),
            'set_piece_events':len(setpieces)
        })
    return pd.DataFrame(rows)


def add_transition_features(events: pd.DataFrame, features: pd.DataFrame, seconds: float=5.0) -> tuple[pd.DataFrame,pd.DataFrame]:
    lr=build_loss_responses(events,max_seconds=seconds)
    agg=(lr.groupby(['match_id','team_name']).agg(
        losses=('loss_event_id','count'),recoveries_5s=('response_within_5s','sum'),
        mean_response_s=('response_delta_s','mean')
    ).reset_index())
    agg['recovery_5s_rate']=agg['recoveries_5s']/agg['losses'].replace(0,np.nan)
    return features.merge(agg,on=['match_id','team_name'],how='left'),lr


def score_state_features(events: pd.DataFrame, target_team='América') -> pd.DataFrame:
    t=events[events.team_name.eq(target_team)].copy()
    rows=[]
    for state,s in t.groupby('score_state'):
        passes=s[s.event_type_name.eq('Pass')]
        shots=s[s.event_type_name.eq('Shot')]
        pressures=s[s.event_type_name.eq('Pressure')]
        rows.append({
            'score_state':state,'events':len(s),'passes':len(passes),'shots':len(shots),
            'xg':float(shots.statsbomb_xg.fillna(0).sum()),'pressures':len(pressures),
            'mean_obv':float(pd.to_numeric(s.obv_total_net,errors='coerce').mean()),
            'mean_directness':float(pd.to_numeric(s.possession_directness,errors='coerce').mean()),
            'mean_control':float(pd.to_numeric(s.control_degree,errors='coerce').mean())
        })
    return pd.DataFrame(rows)
