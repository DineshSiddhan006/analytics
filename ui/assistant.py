from __future__ import annotations

import streamlit as st

from bi_pipeline.assistant import answer_dataset_question
from llm_client import LLMError


def render_assistant(source: dict) -> None:
    conversation_id = source.get('run_id', source['table'])
    history_key = f'cargo_chat_history_{conversation_id}'
    history = st.session_state.setdefault(history_key, [])

    with st.expander('Cargo Intelligence conversation', expanded=bool(history)):
        for message in history:
            with st.chat_message(message['role']):
                st.markdown(message['content'])

    question = st.chat_input(
        'Ask AI Cargo Intelligence about this dataset or its analytics',
        key=f'cargo_chat_input_{conversation_id}',
    )
    if not question:
        return

    history.append({'role': 'user', 'content': question})
    try:
        with st.spinner('Cargo Intelligence is reviewing the dataset context...'):
            answer = answer_dataset_question(question, source, history[:-1])
    except LLMError as exc:
        history.pop()
        st.error(f'Cargo Intelligence could not answer: {exc}')
        if exc.diagnostics:
            with st.expander('Assistant diagnostics'):
                st.json(exc.diagnostics)
        return

    history.append({'role': 'assistant', 'content': answer})
    st.rerun()
