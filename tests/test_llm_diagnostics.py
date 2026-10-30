import json
import pandas as pd
import pytest
import llm_client
from llm_client import LLMError
from bi_pipeline.llm import propose_analytics, propose_user_analytics

class FakeResponse:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code=status; self.reason='OK' if status==200 else 'Forbidden'
        self.ok=status < 400; self._payload=payload; self.text=text if text is not None else json.dumps(payload)
    def json(self):
        if isinstance(self._payload, Exception): raise self._payload
        return self._payload

def test_ollama_json_response(monkeypatch):
    monkeypatch.setattr(llm_client, 'LLM_URL', 'http://localhost:11434')
    monkeypatch.setattr(llm_client, 'LLM_MODEL', 'test-model')
    monkeypatch.setattr(llm_client.requests, 'post', lambda *a, **k: FakeResponse(payload={'response':'{"proposals":[]}'}))
    assert llm_client.generate_json('prompt') == {'proposals': []}

def test_openai_chat_completion_response(monkeypatch):
    monkeypatch.setattr(llm_client, 'LLM_URL', 'https://example.test/v1/chat/completions')
    monkeypatch.setattr(llm_client, 'LLM_MODEL', 'test-model')
    monkeypatch.setattr(llm_client.requests, 'post', lambda *a, **k: FakeResponse(payload={'choices':[{'message':{'content':'{"proposals": []}'}}]}))
    assert llm_client.generate_json('prompt') == {'proposals': []}

def test_http_error_preserves_body(monkeypatch):
    monkeypatch.setattr(llm_client, 'LLM_URL', 'https://example.test')
    monkeypatch.setattr(llm_client.requests, 'post', lambda *a, **k: FakeResponse(status=403, payload={'error':'denied'}))
    with pytest.raises(LLMError) as err: llm_client.generate_json('prompt')
    assert err.value.diagnostics['http_status'] == 403
    assert 'denied' in err.value.diagnostics['response_body']

def test_invalid_proposal_returns_specific_validation_error(monkeypatch):
    monkeypatch.setattr('bi_pipeline.llm.generate_json', lambda prompt: {'business_context':'test','proposals':[{'title':'Bad metric','metric':'Missing','aggregation':'sum'}]})
    _, valid, errors = propose_analytics(pd.DataFrame({'Revenue':[1,2]}), {}, 'sales', [], [])
    assert valid == []
    assert errors[0]['stage'] == 'spec_validation'
    assert 'Unknown metric column: Missing' in errors[0]['reason']

def test_empty_proposals_array_has_diagnostic(monkeypatch):
    monkeypatch.setattr('bi_pipeline.llm.generate_json', lambda prompt: {'business_context':'test','proposals':[]})
    _, valid, errors = propose_analytics(pd.DataFrame({'Revenue':[1,2]}), {}, 'sales', [], [])
    assert valid == []
    assert errors[0]['stage'] == 'response_validation'
    assert 'empty proposals array' in errors[0]['reason']

def test_common_schema_mistakes_are_repaired_into_usable_analytics(monkeypatch):
    df = pd.DataFrame({
        'cargo_route_id': ['R1', 'R1', 'R2'],
        'Weight_KG': [10.0, 20.0, 5.0],
        'shipment_timestamp': pd.to_datetime(['2026-01-02', '2026-01-15', '2026-02-01']),
        'day_of_week': ['Friday', 'Thursday', 'Sunday'],
    })
    monkeypatch.setattr('bi_pipeline.llm.generate_json', lambda prompt: {
        'business_context': 'Cargo operations analysis.',
        'proposals': [
            {'business_question': 'How many shipments use each route?', 'metric': 'count',
             'aggregation': 'nunique', 'group_by': 'cargo_route_id', 'chart': 'bar'},
            {'business_question': 'What is the average weight by route?', 'metric': 'mean',
             'aggregation': 'mean', 'group_by': 'cargo_route_id', 'chart': 'barh'},
            {'business_question': 'How does cargo weight trend monthly?', 'metric': 'mean',
             'aggregation': 'mean', 'group_by': None, 'chart': 'line', 'period': 'month',
             'filters': ['Weight_KG']},
            {'business_question': 'How does weight vary by weekday?', 'metric': 'mean',
             'aggregation': 'mean', 'group_by': ['day_of_week'], 'chart': 'bar'},
            {'business_question': 'What is the cargo weight distribution?', 'metric': None,
             'aggregation': None, 'group_by': None, 'chart': 'histogram'},
        ],
    })

    _, valid, diagnostics = propose_analytics(df, {}, 'cargo.shipments', [], [])

    assert len(valid) == 5, (valid, diagnostics)
    by_question = {item['business_question']: item for item in valid}
    assert by_question['How many shipments use each route?']['metric'] == 'cargo_route_id'
    assert by_question['How many shipments use each route?']['aggregation'] == 'count'
    assert by_question['What is the average weight by route?']['metric'] == 'Weight_KG'
    assert by_question['How does cargo weight trend monthly?']['group_by'] == 'shipment_timestamp'
    assert by_question['How does cargo weight trend monthly?']['filters'] == []
    assert by_question['How does weight vary by weekday?']['group_by'] == 'day_of_week'
    assert by_question['What is the cargo weight distribution?']['chart'] == 'histogram'
    assert any(item['stage'] == 'proposal_repair' for item in diagnostics)

def test_invalid_proposal_gets_one_schema_correction_attempt(monkeypatch):
    calls = []

    def fake_generate_json(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return {'proposals': [{'metric': 'Missing', 'aggregation': 'sum'}]}
        return {'proposals': [{
            'title': 'Revenue by region',
            'metric': 'Revenue',
            'aggregation': 'sum',
            'group_by': 'Region',
            'chart': 'bar',
        }]}

    monkeypatch.setattr('bi_pipeline.llm.generate_json', fake_generate_json)
    _, valid, diagnostics = propose_analytics(
        pd.DataFrame({'Revenue': [1, 2], 'Region': ['N', 'S']}),
        {'columns': [{'name': 'Revenue'}, {'name': 'Region'}]},
        'sales.orders', [], [],
    )

    assert len(calls) == 2
    assert 'INVALID PROPOSALS' in calls[1]
    assert len(valid) == 1
    assert valid[0]['metric'] == 'Revenue'
    assert not diagnostics


def test_analytics_prompt_includes_visual_semantics_and_quality_rules(monkeypatch):
    observed = {}

    def fake_generate_json(prompt):
        observed['prompt'] = prompt
        return {'business_context': 'Cargo operations.', 'proposals': []}

    monkeypatch.setattr('bi_pipeline.llm.generate_json', fake_generate_json)
    propose_analytics(
        pd.DataFrame({'Weight_KG': [1.0, 2.0], 'Route_display_name': ['A', 'B']}),
        {'columns': [
            {'name': 'Weight_KG', 'dtype': 'float64', 'unique': 2},
            {'name': 'Route_display_name', 'dtype': 'object', 'unique': 2},
        ]},
        'cargo.features', [], [],
    )

    prompt = observed['prompt']
    assert 'Never use nunique on continuous/high-cardinality numeric measures' in prompt
    assert 'at least two distinct values' in prompt
    assert 'Prefer readable *_display_name columns' in prompt
    assert 'Use histogram for the distribution of a numeric measure' in prompt
    assert 'horizontal gridlines only' in prompt

def test_user_analytics_request_is_converted_to_a_validated_proposal(monkeypatch):
    observed = {}

    def fake_generate_json(prompt):
        observed['prompt'] = prompt
        return {'proposals': [{
            'title': 'Average weight by route',
            'metric': 'Weight_KG',
            'aggregation': 'mean',
            'group_by': 'cargo_route_id',
            'chart': 'barh',
            'filters': [],
        }]}

    monkeypatch.setattr('bi_pipeline.llm.generate_json', fake_generate_json)
    df = pd.DataFrame({'Weight_KG': [10, 20], 'cargo_route_id': ['R1', 'R2']})
    profile = {'rows': 2, 'columns': [{'name': 'Weight_KG'}, {'name': 'cargo_route_id'}]}

    proposals, diagnostics = propose_user_analytics(
        'Compare average cargo weight across routes', df, profile, 'cargo.features',
    )

    assert not diagnostics
    assert len(proposals) == 1
    assert proposals[0]['metric'] == 'Weight_KG'
    assert proposals[0]['business_question'] == 'Compare average cargo weight across routes'
    assert 'cargo.features' in observed['prompt']
    assert 'Compare average cargo weight across routes' in observed['prompt']
