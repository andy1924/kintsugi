"""Exercise the real Responses request/validation path using an in-memory transport."""
import json
import time

import httpx
import pytest
from sqlalchemy import update

from conftest import photo, upload
from kintsugi import config, vision
from kintsugi.analysis import analyze_damage
from kintsugi.db import Session
from kintsugi.models import Job
from kintsugi.vision import VisionError
from kintsugi.worker import run_once


ASSESSMENT = {
    'damage_found': True,
    'box': {'left': .3, 'top': .2, 'right': .65, 'bottom': .75},
    'damage_type': 'tear', 'severity': 'moderate', 'fabric': 'Knit',
    'confidence': 'medium', 'summary': 'A ragged tear with fraying along the edge.',
    'repair_advice': 'Support the tear with a compatible stretchy backing before adding stitches.',
    'recommended_style': 'branch', 'warnings': ['Confirm the fabric stretch before selecting a backing.'],
}


def response_body(assessment=None):
    return {'status': 'completed', 'output': [{'type': 'message', 'content': [
        {'type': 'output_text', 'text': json.dumps(assessment or ASSESSMENT)},
    ]}]}


@pytest.fixture
def openai_transport(monkeypatch):
    real_client = httpx.Client
    requests = []
    replies = []
    def handler(request):
        requests.append(request)
        reply = replies.pop(0) if replies else httpx.Response(200, json=response_body())
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(config, 'DAMAGE_ANALYSIS_PROVIDER', 'openai')
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-secret-only')
    monkeypatch.setattr(vision.httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return requests, replies


def test_responses_image_request_and_geometry(openai_transport):
    requests, _ = openai_transport
    result = analyze_damage(photo(), {})
    request = requests[0]
    payload = json.loads(request.content)
    assert str(request.url) == 'https://api.openai.com/v1/responses'
    assert request.headers['authorization'] == 'Bearer test-secret-only'
    assert payload['store'] is False
    assert payload['model'] == config.OPENAI_VISION_MODEL
    assert payload['text']['format']['strict'] is True
    assert payload['text']['format']['schema']['additionalProperties'] is False
    assert payload['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;base64,')
    assert payload['max_output_tokens'] == 1400
    assert result['provider'] == 'openai'
    assert result['box'] == [.3, .2, .65, .75]
    assert result['fabric'] == 'Knit' and result['margin_mm'] == 12
    assert result['recommended_style'] == 'branch'
    assert result['assessment'] == ASSESSMENT['summary']
    assert result['scale_source'] == 'suggested'
    assert result['outlines'] and not result['requires_manual_area']
    assert 'test-secret-only' not in json.dumps(result)


def test_user_adjustments_override_model(openai_transport):
    result = analyze_damage(photo(), {'box': [.2, .3, .7, .8], 'width_mm': 42, 'fabric': 'Cotton'})
    assert result['box'] == [.2, .3, .7, .8]
    assert result['width_mm'] == 42 and result['scale_source'] == 'user'
    assert result['fabric'] == 'Cotton' and result['margin_mm'] == 10
    assert result['detection'] == 'user_adjusted'


def test_missing_key_and_local_provider(monkeypatch):
    monkeypatch.setattr(config, 'OPENAI_API_KEY', '')
    monkeypatch.setattr(config, 'DAMAGE_ANALYSIS_PROVIDER', 'openai')
    with pytest.raises(VisionError, match='server API key'):
        analyze_damage(photo(), {})
    monkeypatch.setattr(config, 'DAMAGE_ANALYSIS_PROVIDER', 'auto')
    assert analyze_damage(photo(), {})['provider'] == 'local'
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-secret-only')
    assert config.analysis_provider() == 'openai'


@pytest.mark.parametrize('status,retryable', [(401, False), (403, False), (400, False), (429, True), (500, True)])
def test_provider_errors_are_sanitized(openai_transport, status, retryable):
    requests, replies = openai_transport
    replies.append(httpx.Response(status, json={'error': {'message': 'private provider detail test-secret-only'}}))
    with pytest.raises(VisionError) as error:
        analyze_damage(photo(), {})
    assert error.value.retryable is retryable
    assert 'test-secret-only' not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize('body', [
    {'status': 'incomplete', 'output': []},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'private provider detail'}]}]},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'not json'}]}]},
    response_body({**ASSESSMENT, 'box': {'left': .8, 'top': .2, 'right': .3, 'bottom': .7}}),
    response_body({**ASSESSMENT, 'box': None}),
    response_body({**ASSESSMENT, 'confidence': 'certain'}),
])
def test_invalid_or_refused_assessments_fail_cleanly(openai_transport, body):
    _, replies = openai_transport
    replies.append(httpx.Response(200, json=body))
    with pytest.raises(VisionError):
        analyze_damage(photo(), {})


def test_timeout_is_retryable(openai_transport):
    _, replies = openai_transport
    replies.append(httpx.ReadTimeout('private provider detail'))
    with pytest.raises(VisionError) as error:
        analyze_damage(photo(), {})
    assert error.value.retryable
    assert 'private provider detail' not in str(error.value)


def test_no_damage_requires_adjustment_before_compile(client, user, openai_transport):
    _, replies = openai_transport
    replies.append(httpx.Response(200, json=response_body({**ASSESSMENT, 'damage_found': False, 'box': None, 'confidence': 'low'})))
    project = upload(client)
    url = f'/api/v1/projects/{project["id"]}'
    assert client.post(url+'/analyze', json={}).status_code == 202
    assert run_once()
    project = client.get(url).json()
    assert project['status'] == 'needs_review'
    assert project['analysis']['requires_manual_area']
    assert client.post(url+'/compile', json={'revision': project['revision'], 'confirmed': True}).status_code == 422
    assert client.post(url+'/analyze', json={'box': [.3, .2, .65, .75]}).status_code == 202
    assert run_once()
    project = client.get(url).json()
    assert project['analysis']['detection'] == 'user_adjusted'
    assert not project['analysis']['requires_manual_area']


def test_queue_to_openai_to_printable_plan(client, user, openai_transport):
    requests, _ = openai_transport
    project = upload(client)
    url = f'/api/v1/projects/{project["id"]}'
    assert client.post(url+'/analyze', json={}).status_code == 202
    assert run_once()
    project = client.get(url).json()
    assert project['status'] == 'needs_review'
    assert client.post(url+'/compile', json={'revision': project['revision'], 'style': project['analysis']['recommended_style'], 'confirmed': True}).status_code == 202
    assert run_once()
    project = client.get(url).json()
    assert project['status'] == 'ready'
    assert project['plan']['style'] == 'branch'
    assert any('knit' in material.lower() for material in project['plan']['materials'])
    assert client.get(url+'/pattern.pdf').content.startswith(b'%PDF')
    assert len(requests) == 1  # Compiling uses saved assessment, not another paid call.
    health = client.get('/api/v1/health').json()
    assert health['damage_analysis'] == 'openai' and health['openai_configured']
    assert 'test-secret-only' not in json.dumps(health)


@pytest.mark.parametrize('status,expected', [(401, 'failed'), (429, 'analyzing')])
def test_queue_classifies_failures(client, user, openai_transport, status, expected):
    _, replies = openai_transport
    replies.append(httpx.Response(status, json={'error': 'private provider detail'}))
    project = upload(client)
    url = f'/api/v1/projects/{project["id"]}'
    client.post(url+'/analyze', json={})
    assert run_once()
    project = client.get(url).json()
    assert project['status'] == expected
    if status == 401:
        assert 'OpenAI access was rejected' in project['error']
    else:
        with Session.begin() as db:
            db.execute(update(Job).values(run_after=time.time()-1))
        assert run_once()
        assert client.get(url).json()['status'] == 'needs_review'
