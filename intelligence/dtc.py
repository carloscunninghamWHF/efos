"""Dynamic Transition Competition (DTC) baseline state model."""
from __future__ import annotations
import pandas as pd
from config_loader import get_thresholds


def classify_state(row):
    th=get_thresholds()['dtc']; esi=float(row.get('ESI',0)); pressure=float(row.get('HPS',0)); der=float(row.get('DER',0))
    if esi>=float(th['stability_esi_min']) and der>=float(th['stability_der_min']): return 'stability'
    if esi>=float(th['adaptation_esi_min']): return 'adaptation'
    if esi>=float(th['tension_esi_min']) or pressure>=float(th['tension_hps_min']): return 'tension'
    if esi>=float(th['fragility_esi_min']): return 'fragility'
    return 'collapse'

def build_dtc(match_metrics:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    if match_metrics.empty:return match_metrics.copy(),pd.DataFrame()
    d=match_metrics.copy().sort_values(['match_id','window_order']); d['state']=d.apply(classify_state,axis=1); d['next_state']=d.groupby('match_id')['state'].shift(-1)
    x=d.dropna(subset=['next_state'])
    return (d,pd.crosstab(x.state,x.next_state,normalize='index').reset_index()) if not x.empty else (d,pd.DataFrame())
