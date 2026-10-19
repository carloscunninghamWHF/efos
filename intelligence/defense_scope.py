"""Same-sample opponent/match filtering for defensive scenario comparisons."""
from __future__ import annotations
import pandas as pd


def opponent_match_scope(summary: pd.DataFrame, events: pd.DataFrame, team: str, opponent: str = 'Todos los rivales',
                         match_id: str = 'Todos los partidos') -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Only includes matches where opponent is explicitly identifiable, preserves all rows for selected possessions."""
    if summary.empty: return summary.copy(), events.iloc[:0].copy(), {}
    teams = events.loc[events.team.ne(team), ['match_id', 'team']].dropna().copy()
    teams['match_id']=teams.match_id.astype(str)
    opponents=teams.groupby('match_id').team.agg(lambda x: sorted(set(map(str, x))))
    mapping={m: names[0] for m,names in opponents.items() if len(names)==1}
    s=summary.copy()
    s['opponent']=s.match_id.astype(str).map(mapping).fillna('Rival no identificado')
    if opponent!='Todos los rivales': s=s[s.opponent.eq(opponent)]
    if match_id!='Todos los partidos': s=s[s.match_id.astype(str).eq(str(match_id))]
    if s.empty: return s,events.iloc[:0].copy(),mapping
    keys=pd.MultiIndex.from_frame(s[['match_id','possession']])
    e=events[events.set_index(['match_id','possession']).index.isin(keys)].copy()
    return s,e,mapping

