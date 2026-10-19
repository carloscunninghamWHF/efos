from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sprint2.pipeline import load_competition_csvs, validate, add_score_context, build_possessions
from sprint2.objects import build_pre_event_windows, build_loss_responses, build_sequences
from sprint2.tactical import team_match_features, add_transition_features, score_state_features
from sprint2.intelligence import build_cts, build_esi, contextual_esi, dtc_states, candidate_principles
from sprint2.players import lap_table, substitution_impacts


def dtc_transition_matrix(dtc: pd.DataFrame) -> pd.DataFrame:
    # Match-level DTC states have no natural chronological order across season in this export;
    # matrix therefore summarizes adjacent match_id-sorted observations and is explicitly exploratory.
    d=dtc.sort_values('match_id').copy()
    d['next_state']=d.DTC_state.shift(-1)
    x=d.dropna(subset=['next_state'])
    m=pd.crosstab(x.DTC_state,x.next_state,normalize='index').fillna(0)
    return m


def adaptation_score(state_features: pd.DataFrame) -> dict:
    if len(state_features)<2:
        return {'adaptation_score':np.nan,'contextual_spread':np.nan}
    # Standardized spread across available score states for directness, control, pressure rate proxy and xG/event.
    s=state_features.copy()
    s['xg_per_1000_events']=s.xg/s.events.replace(0,np.nan)*1000
    s['pressures_per_1000_events']=s.pressures/s.events.replace(0,np.nan)*1000
    cols=['mean_directness','mean_control','xg_per_1000_events','pressures_per_1000_events']
    spreads=[]
    for c in cols:
        v=pd.to_numeric(s[c],errors='coerce').dropna()
        if len(v)>=2:
            denom=max(abs(v.mean()),1e-9)
            spreads.append(float((v.max()-v.min())/denom))
    spread=float(np.mean(spreads)) if spreads else np.nan
    # Interpretable bounded index: 0=no measurable contextual change; asymptotically approaches 100.
    score=float(100*(1-np.exp(-spread))) if np.isfinite(spread) else np.nan
    return {'adaptation_score':score,'contextual_spread':spread}


def run(paths, output_dir, target_team='América'):
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    raw,events,frames=load_competition_csvs(paths)
    audit=validate(raw,events,frames)
    if not audit['passed']:
        raise RuntimeError(f'Data audit failed: {audit["issues"]}')
    events=add_score_context(events,target_team)
    possessions=build_possessions(events)
    sequences=build_sequences(events)
    shot_windows=build_pre_event_windows(events,n=5,target_types={'Shot'})
    loss_responses=build_loss_responses(events,max_seconds=5.0)
    tm=team_match_features(events)
    agg=(loss_responses.groupby(['match_id','team_name']).agg(losses=('loss_event_id','count'),recoveries_5s=('response_within_5s','sum'),mean_response_s=('response_delta_s','mean')).reset_index())
    agg['recovery_5s_rate']=agg['recoveries_5s']/agg['losses'].replace(0,np.nan)
    tm=tm.merge(agg,on=['match_id','team_name'],how='left')
    tm_scored,cts=build_cts(tm,target_team)
    state=score_state_features(events,target_team)
    adapt=adaptation_score(state)
    cts=pd.concat([cts,pd.DataFrame([{'dimension':'Adaptation','score':adapt['adaptation_score'],'confidence':100.0 if len(state)==3 else 66.7,'matches':int(events.loc[events.team_name.eq(target_team),'match_id'].nunique())}])],ignore_index=True)
    esi_match,esi_summary=build_esi(events,loss_responses,target_team)
    esi_context=contextual_esi(events,loss_responses,target_team)
    dtc=dtc_states(esi_match,tm,target_team)
    dtc_matrix=dtc_transition_matrix(dtc)
    lap=lap_table(events,target_team)
    subs=substitution_impacts(events,target_team,window_minutes=15)
    principles=candidate_principles(tm,cts,target_team)

    exports={
        'events_unique.csv':events,'freeze_frames.csv':frames,'possessions.csv':possessions,'sequences.csv':sequences,
        'shot_pre5_windows.csv':shot_windows,'loss_responses_5s.csv':loss_responses,'team_match_features.csv':tm_scored,
        'cts.csv':cts,'esi_by_match.csv':esi_match,'esi_summary.csv':esi_summary,'esi_by_score_state.csv':esi_context,
        'score_state_features.csv':state,'dtc_by_match.csv':dtc,'lap_players.csv':lap,'substitution_impacts.csv':subs,
        'candidate_principles.csv':principles
    }
    for name,df in exports.items(): df.to_csv(out/name,index=False)
    dtc_matrix.to_csv(out/'dtc_transition_matrix.csv')
    top3=principles.head(3).to_dict(orient='records')
    summary={'target_team':target_team,'audit':audit,'adaptation':adapt,
             'cts':cts.round(3).to_dict(orient='records'),'esi':esi_summary.round(3).to_dict(orient='records'),
             'score_states':state.round(5).to_dict(orient='records'),'top_candidate_principles':top3,
             'objects':{'possessions':len(possessions),'sequences':len(sequences),'shot_pre5_rows':len(shot_windows),
                        'losses_analyzed':len(loss_responses),'players_lap':len(lap),'substitutions':len(subs)}}
    with open(out/'intelligence_summary.json','w',encoding='utf-8') as f: json.dump(summary,f,ensure_ascii=False,indent=2,default=str)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description='EFOS Sprint v2.1 — Intelligence Engine')
    p.add_argument('csv',nargs='+'); p.add_argument('--team',default='América'); p.add_argument('--output',default='outputs/intelligence')
    a=p.parse_args(); print(json.dumps(run(a.csv,a.output,a.team),ensure_ascii=False,indent=2,default=str))
