from __future__ import annotations
import streamlit as st
from config import validate_config, FABRIC_TABLE
from fabric_warehouse import list_tables
from ui.session import init
from ui.styles import CSS
from ui.review import render_review
from ui.dashboard import render_dashboard

st.set_page_config(page_title='Cargo Tonnage Prediction',layout='wide',initial_sidebar_state='expanded')
st.markdown(CSS,unsafe_allow_html=True)
init()
if st.session_state.get('screen') != 'dashboard':
    st.title('Cargo Tonnage Prediction')
selected = FABRIC_TABLE
with st.sidebar:
    st.header('Data source')
    try:
        tables=list_tables()
        if not tables: st.error('No tables or views were returned by the warehouse.'); st.stop()
        default=FABRIC_TABLE if FABRIC_TABLE in tables else tables[0]
        selected=st.selectbox('Warehouse table',tables,index=tables.index(default))
        if st.button('Run pipeline / Re-plan',type='primary',use_container_width=True):
            try:
                validate_config()
                with st.status('Starting analytics pipeline...', expanded=True) as status:
                    st.session_state['active_run']=st.session_state['service'].plan_run(
                        selected,
                        progress=lambda message: status.update(label=message),
                    )
                    status.update(label='Analytics are ready for review.', state='complete', expanded=False)
                st.session_state['screen']='review'; st.rerun()
            except Exception as exc: st.error(str(exc))
    except Exception as exc:
        st.error(f'Warehouse connection failed: {exc}')
        st.caption('Correct the warehouse credentials or authentication, then retry. No local fallback is used.')
if 'active_run' not in st.session_state and not st.session_state.get('startup_attempted'):
    st.session_state['startup_attempted'] = True
    try:
        validate_config()
        with st.status('Starting analytics pipeline...', expanded=True) as status:
            st.session_state['active_run'] = st.session_state['service'].plan_run(
                FABRIC_TABLE or selected,
                progress=lambda message: status.update(label=message),
            )
            status.update(label='Analytics are ready for review.', state='complete', expanded=False)
        st.session_state['screen'] = 'review'
        st.rerun()
    except Exception as exc:
        st.error(f'Pipeline could not start: {exc}')

if 'active_run' in st.session_state and st.session_state['screen']=='review':
    run=st.session_state['active_run']
    if not run.get('review'):
        st.warning('No saved or generated analytics are available yet. You can add an analysis below or re-plan.')
        if run.get('proposal_errors'):
            with st.expander('Why no analytics were generated'):
                for error in run['proposal_errors']:
                    st.write(error.get('reason', str(error)))
    render_review(run)
elif 'dashboard_bundle' in st.session_state and st.session_state['screen']=='dashboard':
    render_dashboard(st.session_state['dashboard_bundle'])
else:
    st.write('Choose a warehouse table and select **Run pipeline / Re-plan** to generate analytics proposals.')
