import streamlit as st

def init():
    if 'service' not in st.session_state:
        from bi_pipeline.container import get_service
        st.session_state['service']=get_service()
    st.session_state.setdefault('screen','review')
