"""HTTP client for Ollama-compatible and OpenAI-compatible JSON endpoints."""
from __future__ import annotations
import json
import requests
from config import LLM_URL, LLM_MODEL, LLM_TIMEOUT

class LLMError(RuntimeError):
    def __init__(self, message: str, *, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

def _extract_text(payload: dict) -> str:
    # Ollama /api/generate
    value = payload.get('response') or payload.get('text')
    if isinstance(value, str) and value.strip():
        return value.strip()
    # OpenAI Chat Completions
    choices = payload.get('choices')
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get('message') or {}
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip(): return content.strip()
        if isinstance(content, list):
            parts = [p.get('text','') for p in content if isinstance(p,dict)]
            if ''.join(parts).strip(): return ''.join(parts).strip()
        if isinstance(choice.get('text'), str) and choice['text'].strip(): return choice['text'].strip()
    # Some gateways return the JSON object directly.
    if isinstance(payload.get('proposals'), list): return json.dumps(payload)
    return ''

def generate_json(prompt: str) -> dict:
    if not LLM_URL:
        raise LLMError('LLM_URL is missing from .env', diagnostics={'stage':'configuration'})
    url = LLM_URL.rstrip('/')
    if not (url.endswith('/api/generate') or url.endswith('/v1/chat/completions') or url.endswith('/chat/completions')):
        url += '/api/generate'
    body = {'model': LLM_MODEL, 'prompt': prompt, 'stream': False, 'format': 'json'}
    if url.endswith('/chat/completions'):
        body = {'model': LLM_MODEL, 'messages':[{'role':'system','content':'Return only valid JSON.'},{'role':'user','content':prompt}], 'temperature':0.2, 'response_format':{'type':'json_object'}}
    try:
        response = requests.post(url, json=body, timeout=LLM_TIMEOUT)
    except requests.RequestException as exc:
        raise LLMError(f'LLM connection failed: {type(exc).__name__}: {exc}', diagnostics={'stage':'http_request','endpoint':url,'model':LLM_MODEL}) from exc
    response_text = response.text or ''
    if not response.ok:
        raise LLMError(f'LLM HTTP {response.status_code}: {response.reason}', diagnostics={'stage':'http_response','endpoint':url,'model':LLM_MODEL,'http_status':response.status_code,'response_body':response_text[:12000]})
    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMError('LLM endpoint returned a non-JSON HTTP response.', diagnostics={'stage':'response_envelope','endpoint':url,'model':LLM_MODEL,'http_status':response.status_code,'response_body':response_text[:12000]}) from exc
    text = _extract_text(payload) if isinstance(payload,dict) else ''
    if not text:
        raise LLMError('LLM HTTP response did not contain generated text.', diagnostics={'stage':'response_extraction','endpoint':url,'model':LLM_MODEL,'http_status':response.status_code,'response_body':json.dumps(payload,ensure_ascii=False,default=str)[:12000]})
    # Permit a small amount of surrounding markdown while retaining the raw answer for diagnosis.
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('\n',1)[-1]
        if cleaned.rstrip().endswith('```'): cleaned = cleaned.rstrip()[:-3].strip()
    try:
        result = json.loads(cleaned)
    except ValueError as exc:
        raise LLMError('LLM generated text was not valid JSON.', diagnostics={'stage':'json_parse','endpoint':url,'model':LLM_MODEL,'http_status':response.status_code,'raw_generated_text':text[:16000],'response_body':response_text[:4000]}) from exc
    if not isinstance(result,dict):
        raise LLMError('LLM JSON must be an object.', diagnostics={'stage':'json_shape','raw_generated_text':text[:16000]})
    return result
