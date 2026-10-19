"""EFOS v0.4.25 — shared question navigation for module pages.

A module declares its questions as tuples (id, number, kicker, question, finding_id).
One button per question; only the active question is rendered. Presentation only:
no metric is calculated here.
"""
from __future__ import annotations
import streamlit as st

_NAV_CSS="""
<style>
[class*="st-key-{k}_qnav"] button {{
  min-height:104px; width:100%; border-radius:16px; padding:14px 16px;
  justify-content:flex-start; text-align:left; align-items:flex-start;
  background:rgba(255,255,255,.86); border:1px solid rgba(15,23,42,.10);
  box-shadow:0 3px 14px rgba(15,23,42,.05); transition:all .15s ease;
}}
[class*="st-key-{k}_qnav"] button:hover {{border-color:#C89B3C; transform:translateY(-1px);}}
[class*="st-key-{k}_qnav"] button div,
[class*="st-key-{k}_qnav"] button p {{white-space:normal !important; overflow:visible !important;
  text-overflow:clip !important; max-width:100%;}}
[class*="st-key-{k}_qnav"] button p {{text-align:left; font-size:.98rem; line-height:1.35; color:#0B1220;}}
[class*="st-key-{k}_qnav"] button p strong {{display:block; font-size:.72rem; letter-spacing:.09em;
  text-transform:uppercase; color:#9A7426; margin-bottom:6px; font-weight:700;}}
[class*="st-key-{k}_qnav"] button[kind="primary"] {{background:#0B1220; border-color:#0B1220;
  box-shadow:0 10px 28px rgba(11,18,32,.22);}}
[class*="st-key-{k}_qnav"] button[kind="primary"] p {{color:#FFFFFF;}}
[class*="st-key-{k}_qnav"] button[kind="primary"] p strong {{color:#E3BE6B;}}
.efos-q-head {{margin:22px 0 10px; padding:18px 22px; border-radius:18px; background:#FFFFFF;
  border:1px solid rgba(15,23,42,.08); border-left:5px solid #C89B3C;}}
.efos-q-kicker {{font-size:.74rem; letter-spacing:.1em; text-transform:uppercase; color:#9A7426; font-weight:700;}}
.efos-q-title {{font-size:1.6rem; font-weight:780; letter-spacing:-.03em; color:#0B1220; margin-top:2px;}}
.efos-q-sub {{font-size:.9rem; color:#697586; margin-top:4px;}}
.efos-answer-kicker {{font-size:.72rem; letter-spacing:.1em; color:#9A7426; font-weight:700; margin:4px 0 6px;}}
</style>
"""


def _set_question(state_key,qid):
    st.session_state[state_key]=qid


def question_nav(questions,key_prefix,title='Explorar el juego'):
    """One concise selector replaces five oversized navigation cards."""
    ids=[q[0] for q in questions]
    state_key=key_prefix+'_question'
    if st.session_state.get(state_key) not in ids:
        st.session_state[state_key]=ids[0]
    return st.radio(title,ids,
        format_func=lambda qid: next(f"{q[1]} · {q[2]}" for q in questions if q[0]==qid),
        horizontal=True,key=state_key)



def question_header(questions,qid,subtitle='Respuesta, mapas y evidencia de la muestra seleccionada.'):
    ids=[q[0] for q in questions]
    _,num,kicker,question,_=questions[ids.index(qid)]
    st.markdown(f"<div class='efos-q-head'><div class='efos-q-kicker'>Pregunta {num} de {len(questions)} · {kicker}</div>"
                f"<div class='efos-q-title'>{question}</div>"
                f"<div class='efos-q-sub'>{subtitle}</div></div>",unsafe_allow_html=True)


def question_pager(questions,qid,key_prefix):
    ids=[q[0] for q in questions]
    i=ids.index(qid);state_key=key_prefix+'_question'
    st.write('')
    a,_,b=st.columns([1,2,1])
    if i>0:
        p=questions[i-1]
        a.button(f'← {p[1]} · {p[3]}',key=key_prefix+'_qprev',use_container_width=True,
                 on_click=_set_question,args=(state_key,p[0]))
    if i<len(questions)-1:
        n=questions[i+1]
        b.button(f'{n[1]} · {n[3]} →',key=key_prefix+'_qnext',use_container_width=True,
                 on_click=_set_question,args=(state_key,n[0]))


def question_answer(questions,qid,result,key_prefix,
                    note='La respuesta EFOS usa la muestra principal; los filtros de este módulo modifican sólo los mapas y conteos inferiores.'):
    ids=[q[0] for q in questions]
    ident=questions[ids.index(qid)][4]
    if not ident or result is None:
        return False
    from visualization.reasoning_ui import render_answer
    render_answer(result,ident,f'{key_prefix}_{qid}_answer')
    st.caption(note)
    return True
