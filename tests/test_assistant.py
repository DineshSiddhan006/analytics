import pandas as pd
import pytest

import bi_pipeline.assistant as assistant
from llm_client import LLMError


def test_answer_uses_profile_and_dashboard_results(monkeypatch):
    observed = {}

    def fake_generate_json(prompt):
        observed['prompt'] = prompt
        return {'answer': 'Revenue is higher in the North region.'}

    monkeypatch.setattr(assistant, 'generate_json', fake_generate_json)
    source = {
        'table': 'sales.orders',
        'profile': {'rows': 3, 'columns': [{'name': 'Revenue', 'sum': 45}]},
        'context': 'Regional revenue analysis.',
        'outputs': [{
            'spec': {'title': 'Revenue by region'},
            'data': pd.DataFrame({'category': ['North'], 'value': [45]}),
        }],
    }

    answer = assistant.answer_dataset_question(
        'Which region had higher revenue?', source, [{'role': 'user', 'content': 'Summarize sales.'}],
    )

    assert answer == 'Revenue is higher in the North region.'
    assert 'sales.orders' in observed['prompt']
    assert 'Regional revenue analysis.' in observed['prompt']
    assert '"value": 45' in observed['prompt']
    assert 'Summarize sales.' in observed['prompt']


def test_answer_reports_empty_llm_answer(monkeypatch):
    monkeypatch.setattr(assistant, 'generate_json', lambda prompt: {'answer': '  '})
    source = {'table': 'sales.orders', 'profile': {'rows': 1}, 'review': []}

    with pytest.raises(LLMError, match='returned no answer'):
        assistant.answer_dataset_question('What is in this dataset?', source)


def test_answer_rejects_empty_question():
    source = {'table': 'sales.orders', 'profile': {'rows': 1}, 'review': []}

    with pytest.raises(ValueError, match='Enter a question'):
        assistant.answer_dataset_question(' ', source)
