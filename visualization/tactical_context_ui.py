"""Conceptual explanations are explicitly separate from measured observations."""
import streamlit as st
from knowledge.tactical_context import context_for

def render_context(concept):
    c=context_for(concept)
    with st.expander('Lectura táctica · '+c['title']):
        st.markdown('**Cómo interpretar lo observado**');st.write(c['reading'])
        st.markdown('**Otra explicación posible**');st.write(c['alternative'])
        st.markdown('**Qué revisar con el entrenador**');st.write(c['question'])
        st.caption(c['limit'])
        st.caption('Marco conceptual de EFOS. No añade mediciones ni confirma intenciones tácticas.')
