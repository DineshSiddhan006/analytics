from __future__ import annotations

import streamlit as st

from bi_pipeline.llm import propose_user_analytics
from bi_pipeline.specs import CHARTS, validate_spec
from llm_client import LLMError

_CHART_LABELS = {
    chart: chart.replace('_', ' ').title()
    for chart in sorted(CHARTS)
}


def _is_time_analysis(spec, df):
    group = spec.get('group_by')
    if not isinstance(group, str) or group not in df.columns:
        return False
    name = str(group).lower()
    return bool(
        spec.get('period')
        or any(part in name for part in ('date', 'time', 'timestamp'))
        or name in {'month', 'quarter', 'year'}
    )


def _add_user_request(run, request):
    with st.spinner('Turning your request into a dataset-based analysis...'):
        proposals, diagnostics = propose_user_analytics(
            request, run['df'], run['profile'], run['table'],
        )

    existing = {item['spec'].get('identity') for item in run['review']}
    added = 0
    for spec in proposals:
        if spec['identity'] in existing:
            continue
        run['review'].append({
            'status': 'User suggestion',
            'include': True,
            'spec': spec,
            'error': '',
        })
        existing.add(spec['identity'])
        added += 1

    if added:
        st.success(f'Added {added} analysis suggestion(s) to your review.')
    elif not diagnostics:
        st.info('That analysis is already in the review list.')
    if diagnostics:
        if not added:
            st.warning('That request could not be matched to an analysis supported by the available data. Try describing a metric and how you want to compare it.')


def render_review(run):
    st.subheader('Review business analytics')
    st.caption('Choose what to include and how to display it, or describe another analysis you need.')

    with st.form(f"user_analytics_form_{run.get('run_id', 'initial')}", clear_on_submit=True):
        request = st.text_input(
            'What would you like to analyze?',
            placeholder='For example: Compare average cargo weight across routes',
        )
        submitted = st.form_submit_button('Add analysis')
    if submitted:
        if not request.strip():
            st.warning('Describe the analysis you want to add.')
        else:
            try:
                _add_user_request(run, request.strip())
            except LLMError as exc:
                st.error('Could not interpret that request. Check the LLM connection and try again.')

    selections = []
    for index, item in enumerate(run['review']):
        spec = item['spec']
        identity = spec.get('identity') or f'new_{index}'
        with st.container(border=True):
            include_col, description_col, chart_col = st.columns([0.08, 0.62, 0.30])
            with include_col:
                include = st.checkbox(
                    'Include',
                    value=item.get('include', True),
                    key=f"include_{run.get('run_id', 'initial')}_{identity}",
                    label_visibility='collapsed',
                )
            with description_col:
                st.caption('WHAT IT WILL SHOW')
                st.write(spec.get('business_question') or spec.get('title') or 'Business analysis')
            with chart_col:
                current_chart = spec.get('chart', 'bar')
                chart_options = sorted(
                    CHARTS if _is_time_analysis(spec, run['df'])
                    else CHARTS - {'line', 'area'}
                )
                group = spec.get('group_by')
                category_count = (
                    int(run['df'][group].nunique(dropna=True))
                    if isinstance(group, str) and group in run['df'].columns else 0
                )
                if not 2 <= category_count <= 8:
                    chart_options = [
                        chart for chart in chart_options if chart not in {'pie', 'donut'}
                    ]
                selected_chart = st.selectbox(
                    'HOW TO DISPLAY IT',
                    chart_options,
                    index=chart_options.index(current_chart) if current_chart in chart_options else chart_options.index('barh'),
                    format_func=lambda value: _CHART_LABELS[value],
                    key=f"chart_{run.get('run_id', 'initial')}_{identity}",
                )
        updated_spec = dict(spec)
        updated_spec['chart'] = selected_chart
        selections.append({
            'include': include,
            'status': item.get('status', 'User suggestion'),
            'spec': updated_spec,
            'original_spec': spec,
        })

    if st.button('Proceed to dashboard', type='primary', use_container_width=True):
        final = []
        for row in selections:
            if not row['include']:
                final.append({
                    'include': False,
                    'status': row['status'],
                    'spec': row['spec'],
                })
                continue
            try:
                row['spec'] = validate_spec(row['spec'], run['df'])
            except Exception as exc:
                st.error(f"{row['spec'].get('title', 'Business analysis')}: {exc}")
                return
            final.append(row)

        try:
            st.session_state['dashboard_bundle'] = st.session_state['service'].proceed(run, final)
        except Exception as exc:
            st.error(f'Could not build the dashboard: {exc}')
            return
        st.session_state['screen'] = 'dashboard'
        st.rerun()

    if st.button('Re-plan with latest warehouse data'):
        try:
            with st.spinner('Loading latest warehouse data and generating fresh suggestions...'):
                st.session_state['active_run'] = st.session_state['service'].plan_run(run['table'])
            st.rerun()
        except Exception as exc:
            st.error(str(exc))