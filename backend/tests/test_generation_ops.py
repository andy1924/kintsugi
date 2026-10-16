from uuid import uuid4
from sqlalchemy import select
from conftest import ready, upload
from test_creative import result, DESIGN
from kintsugi import config,worker,creative
from kintsugi.db import Session
from kintsugi.models import RepairGeneration,Job


def enabled(monkeypatch):
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-only')
    monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')
    monkeypatch.setattr(worker,'generate_preview',result)


def test_idempotent_refresh_budget_and_history(client,user,monkeypatch):
    p=ready(client);enabled(monkeypatch);url='/api/v1/projects/'+p['id']
    request_id=str(uuid4())
    first=client.post(url+'/preview',json={'request_id':request_id})
    assert first.status_code==202
    for _ in range(7):assert client.post(url+'/preview',json={'request_id':request_id}).json()['preview']['revision']==first.json()['preview']['revision']
    assert client.get('/api/v1/generation-usage').json()['used']==1
    assert client.post(url+'/preview',json={'request_id':request_id,'style':'waves'}).status_code==409
    assert worker.run_once()
    history=client.get(url+'/generations').json();assert len(history)==1 and history[0]['state']=='ready'
    assert 'image_key' not in history[0]
    assert client.get(url+f'/generations/{history[0]["version"]}/image').status_code==200
    assert client.get('/api/v1/ops/queue').status_code==403


def test_daily_admission_failure_keeps_existing_plan(client,user,monkeypatch):
    p=ready(client);enabled(monkeypatch);monkeypatch.setattr(config,'GENERATION_USER_DAILY_LIMIT',1)
    url='/api/v1/projects/'+p['id']
    assert client.post(url+'/preview',json={}).status_code==202;assert worker.run_once()
    response=client.post(url+'/preview',json={})
    assert response.status_code==429 and int(response.headers['Retry-After'])>0
    assert client.get(url).json()['plan']
    assert len(client.get(url+'/generations').json())==1


def test_cancellation_is_idempotent_and_does_not_call_provider(client,user,monkeypatch):
    p=ready(client);enabled(monkeypatch);url='/api/v1/projects/'+p['id']
    version=client.post(url+'/preview',json={}).json()['preview']['revision']
    endpoint=url+f'/generations/{version}/cancel'
    assert client.post(endpoint).json()['state']=='cancelled'
    assert client.post(endpoint).json()['state']=='cancelled'
    assert not worker.run_once()
    assert client.get(url).json()['status']=='ready'
    assert any(job['state']=='cancelled' for job in client.get(url+'/jobs').json())


def test_worker_pools_only_claim_their_own_kinds(client,user):
    p=upload(client)
    assert client.post('/api/v1/projects/'+p['id']+'/analyze',json={}).status_code==202
    assert worker.claim(('preview',)) is None
    assert worker.claim(('analyze',)) is not None


def test_design_checkpoint_survives_image_failure(client,user,monkeypatch):
    p=ready(client);enabled(monkeypatch)
    version=client.post('/api/v1/projects/'+p['id']+'/preview',json={}).json()['preview']['revision']
    from kintsugi.models import Project
    with Session() as db:project=db.get(Project,p['id']);db.expunge(project)
    design=creative.RepairDesign.model_validate(DESIGN)
    creative.checkpoint(project,design)
    with Session() as db:
        generation=db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==p['id'],RepairGeneration.version==version))
        assert generation.stage=='image' and generation.design==DESIGN
    assert creative.checkpoint(project).name==DESIGN['name']
