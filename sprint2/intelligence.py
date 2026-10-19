from __future__ import annotations
import numpy as np
import pandas as pd


def _pct_rank(s: pd.Series, ascending=True):
    x=pd.to_numeric(s,errors='coerce')
    return x.rank(pct=True,ascending=ascending,method='average')*100


def build_cts(team_match: pd.DataFrame, target_team='América') -> tuple[pd.DataFrame,pd.DataFrame]:
    d=team_match.copy()
    # Scores relative to all 76 team-match observations in the same competition sample.
    d['construction_score']=( _pct_rank(d.buildup_passes_per_poss) + _pct_rank(d.pass_completion) )/2
    d['progression_score']=( _pct_rank(d.progressions_per_poss) + _pct_rank(d.final_third_actions_per_poss) )/2
    d['attack_score']=( _pct_rank(d.shots_per_poss) + _pct_rank(d.xg_per_shot) )/2
    d['defense_score']=( _pct_rank(d.pressure_events_per_100_opp_passes) + _pct_rank(d.ppda,ascending=False) + _pct_rank(d.high_press_share) )/3
    d['transition_score']=( _pct_rank(d.recovery_5s_rate) + _pct_rank(d.counterpress_share) )/2
    # Adaptation: absolute contextual movement is not 'better'; score is withheld at match level and set from score-state separation later.
    cols=['construction_score','progression_score','attack_score','defense_score','transition_score']
    tgt=d[d.team_name.eq(target_team)]
    rows=[]
    for c in cols:
        vals=tgt[c].dropna()
        mean=float(vals.mean()) if len(vals) else np.nan
        # confidence rewards coverage and cross-match consistency around its own mean.
        coverage=len(vals)/max(tgt.match_id.nunique(),1)
        variability=float(vals.std(ddof=0)) if len(vals)>1 else 50.0
        confidence=max(0.0,min(100.0,100*coverage*(1-variability/100)))
        rows.append({'dimension':c.replace('_score','').title(),'score':mean,'confidence':confidence,'matches':len(vals)})
    return d,pd.DataFrame(rows)


def build_esi(events: pd.DataFrame, loss_responses: pd.DataFrame, target_team='América') -> tuple[pd.DataFrame,pd.DataFrame]:
    t=events[events.team_name.eq(target_team)].copy()
    lr=loss_responses[loss_responses.team_name.eq(target_team)].copy()
    rows=[]
    for mid,m in t.groupby('match_id'):
        passes=m[m.event_type_name.eq('Pass')]
        under=passes[passes.under_pressure.fillna(False).astype(bool)]
        under_ok=~under.outcome_name.isin(['Incomplete','Out','Pass Offside'])
        vuln=m[(m.location_x.lt(40)) & (m.event_type_name.isin(['Pass','Dispossessed','Miscontrol','Dribble']))]
        vuln_losses=vuln[(vuln.event_type_name.isin(['Dispossessed','Miscontrol'])) | (vuln.event_type_name.eq('Dribble') & vuln.outcome_name.eq('Incomplete')) | (vuln.event_type_name.eq('Pass') & vuln.outcome_name.isin(['Incomplete','Out','Pass Offside']))]
        # OC: control_degree winsorized to [0,1] because source includes values outside range.
        oc=float(pd.to_numeric(m.control_degree,errors='coerce').clip(0,1).mean()*100)
        # HPS: completion under pressure, enriched slightly by positive OBV under pressure.
        hps_base=float(under_ok.mean()*100) if len(under) else np.nan
        obv_under=pd.to_numeric(under.obv_total_net,errors='coerce').dropna()
        obv_pos=float((obv_under>0).mean()*100) if len(obv_under) else np.nan
        hps=np.nanmean([hps_base,obv_pos]) if not (np.isnan(hps_base) and np.isnan(obv_pos)) else np.nan
        # RPS: ability to avoid losses in vulnerable zone.
        rps=float((1-len(vuln_losses)/max(len(vuln),1))*100)
        # DS: observed pass success relative to model probability. Map residual [-1,1] to [0,100], 50=as expected.
        pp=passes[pd.to_numeric(passes.pass_success_probability,errors='coerce').notna()].copy()
        if len(pp):
            actual=(~pp.outcome_name.isin(['Incomplete','Out','Pass Offside'])).astype(float)
            resid=(actual-pd.to_numeric(pp.pass_success_probability,errors='coerce')).mean()
            ds=float(np.clip(50+50*resid,0,100))
        else: ds=np.nan
        # DER: share of losses with a target-team recovery/pressure within five seconds.
        mlr=lr[lr.match_id.eq(mid)]
        der=float(mlr.response_within_5s.mean()*100) if len(mlr) else np.nan
        vals={'OC':oc,'HPS':hps,'RPS':rps,'DS':ds,'DER':der}
        esi=float(np.nanmean(list(vals.values())))
        rows.append({'match_id':mid,**vals,'ESI':esi})
    by_match=pd.DataFrame(rows)
    summary=[]
    for c in ['OC','HPS','RPS','DS','DER','ESI']:
        v=by_match[c].dropna()
        summary.append({'metric':c,'score':float(v.mean()) if len(v) else np.nan,'std':float(v.std(ddof=0)) if len(v)>1 else np.nan,'matches':len(v)})
    return by_match,pd.DataFrame(summary)


def contextual_esi(events: pd.DataFrame, loss_responses: pd.DataFrame, target_team='América') -> pd.DataFrame:
    # Reuse same component logic by filtering each score state; score-state sample sizes are explicit.
    rows=[]
    for state in ['winning','drawing','losing']:
        s=events[events.score_state.eq(state)]
        if s.empty: continue
        # synthetic match identifiers preserve match separation while filtering events
        bm,sm=build_esi(s, loss_responses[loss_responses.loss_event_id.isin(s.id)], target_team)
        r={'score_state':state,'event_count':int((s.team_name.eq(target_team)).sum()),'matches':int(s.loc[s.team_name.eq(target_team),'match_id'].nunique())}
        for _,x in sm.iterrows(): r[x.metric]=x.score
        rows.append(r)
    return pd.DataFrame(rows)


def dtc_states(esi_by_match: pd.DataFrame, team_match: pd.DataFrame, target_team='América') -> pd.DataFrame:
    t=team_match[team_match.team_name.eq(target_team)][['match_id','xg_total','pass_completion','recovery_5s_rate']]
    d=esi_by_match.merge(t,on='match_id',how='left').copy()
    # Operational states derived from within-sample quartiles; labels describe system condition, not psychology.
    q25=d.ESI.quantile(.25); q50=d.ESI.quantile(.50); q75=d.ESI.quantile(.75)
    xg_med=d.xg_total.median()
    conditions=[
        d.ESI>=q75,
        (d.ESI>=q50)&(d.ESI<q75)&(d.xg_total>=xg_med),
        (d.ESI>=q50)&(d.ESI<q75)&(d.xg_total<xg_med),
        (d.ESI>=q25)&(d.ESI<q50),
        d.ESI<q25
    ]
    d['DTC_state']=np.select(conditions,['Stability','Adaptation','Tension','Fragility','Collapse'],default='Tension')
    return d


def candidate_principles(team_match: pd.DataFrame, cts: pd.DataFrame, target_team='América') -> pd.DataFrame:
    t=team_match[team_match.team_name.eq(target_team)].copy()
    opp=team_match[~team_match.team_name.eq(target_team)].copy()
    # Dataset contains one opponent row per América match; attach direct opponent as the reference.
    opp_cols=['match_id','team_name']
    candidates=[]
    def add(name,metric,direction='high',interpretation=''):
        vals=t[['match_id',metric]].rename(columns={metric:'target'}).merge(
            opp[['match_id','team_name',metric]].rename(columns={metric:'opponent','team_name':'opponent_name'}),on='match_id',how='inner')
        vals=vals.dropna(subset=['target','opponent'])
        if not len(vals): return
        if direction=='high': wins=vals.target>=vals.opponent
        else: wins=vals.target<=vals.opponent
        consistency=float(wins.mean())
        coverage=len(vals)/max(t.match_id.nunique(),1)
        effect=float((vals.target-vals.opponent).mean()) if direction=='high' else float((vals.opponent-vals.target).mean())
        candidates.append({
            'candidate':name,'metric':metric,'mean':float(vals.target.mean()),'opponent_mean':float(vals.opponent.mean()),
            'mean_difference':effect,'match_consistency':consistency,'coverage':coverage,
            'evidence_strength':100*consistency*coverage,'matches_supporting':int(wins.sum()),'matches_compared':len(vals),
            'interpretation':interpretation})
    add('Construcción paciente desde campo propio','buildup_passes_per_poss','high','Frecuencia relativa de pases de construcción por posesión.')
    add('Progresión recurrente hacia último tercio','progressions_per_poss','high','Frecuencia de pases que cruzan hacia X>80.')
    add('Presión territorial alta','high_press_share','high','Proporción de presiones iniciadas en X≥72.')
    add('Reacción inmediata tras pérdida','recovery_5s_rate','high','Proporción de pérdidas con presión/recuperación en ≤5 s.')
    add('Ataque de alto volumen','shots_per_poss','high','Frecuencia de tiros por posesión.')
    add('Ataque de alta calidad','xg_per_shot','high','Calidad media de tiro por xG.')
    add('Juego directo','mean_possession_directness','high','Directness media de posesión.')
    return pd.DataFrame(candidates).sort_values(['evidence_strength','coverage','mean_difference'],ascending=False).reset_index(drop=True)
