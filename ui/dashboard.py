from __future__ import annotations

import streamlit as st

from bi_pipeline.charts import make_dashboard_pngs


def render_dashboard(bundle):
    pages = make_dashboard_pngs(bundle['outputs'])
    if not pages:
        st.info('No dashboard visuals are available for the selected analytics. Return to review to include an analysis or choose a different grouping.')
        if st.button('Return to analytics review', type='primary'):
            st.session_state['screen'] = 'review'
            st.rerun()
        return
    for page in pages:
        st.image(page, use_container_width=True)
