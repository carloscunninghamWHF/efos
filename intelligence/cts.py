"""EFOS v0.4 Coach Tactical Signature.
All scores are descriptive hypotheses, not validated truths.
"""
from __future__ import annotations
import numpy as np

def _clip(x): return float(np.clip(x,0,100))

def compute_adaptation_score(states):
    """Recuperación observable tras ventanas de tensión/fragilidad/colapso.

    100 = todas las ventanas de desajuste con transición conocida vuelven en la
    siguiente ventana a adaptación o estabilidad. No se calcula si no hay
    oportunidades observables.
    """
    if states is None or len(states) == 0 or 'state' not in states or 'next_state' not in states:
        return None
    x=states[states['state'].isin(['tension','fragility','collapse']) & states['next_state'].notna()]
    if len(x)==0:
        return None
    return _clip(100*x['next_state'].isin(['adaptation','stability']).mean())


def compute_cts(summary:dict,transition_rate:float|None=None,trap_metrics:dict|None=None,hps:float|None=None,pressure_summary:dict|None=None,adaptation_score:float|None=None)->dict:
    ev=max(summary.get('events',0),1); trap_metrics=trap_metrics or {}; pressure_summary=pressure_summary or {}
    scores={
      'construction':_clip(100*summary.get('build_up_passes',0)/max(ev*0.25,1)),
      'progression':_clip(100*summary.get('deep_progressions',0)/max(ev*0.04,1)),
      'attack':_clip(100*summary.get('final_third_events',0)/max(ev*0.30,1)),
      'defense':_clip(100*summary.get('pressures',0)/max(ev*0.12,1)),
      'transition':_clip(100*(transition_rate or 0)),
      'adaptation':None if adaptation_score is None else _clip(adaptation_score),
      'trap_efficiency':_clip(trap_metrics.get('DTE',0.0)),
      'pressure_resistance':_clip(hps or 0.0),
      'mean_pressure_context':_clip(100*pressure_summary.get('mean_pci',0.0)),
    }
    scores['confidence']=_clip(100*min(1.0,ev/1000.0))
    return scores
