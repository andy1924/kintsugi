import base64
import io
import json
import time
from copy import deepcopy

import httpx
import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select
from conftest import account, ready
from kintsugi import config, creative, worker
from kintsugi.db import Session
from kintsugi.models import Project, Job
from kintsugi.storage import store
from kintsugi.vision import VisionError

DESIGN={
    'name':'Peacock in golden thread','story':'A flowing feather follows the split, turning the worn place into an intentional detail.',
    'style':'branch','thread_colour':'muted teal and warm gold',
    'materials':['Compatible fabric backing','Embroidery needle and muted teal floss','Scissors and ruler'],
    'steps':[{'title':title,'body':'Check the garment and use relaxed running stitches through compatible backing. Measure coverage before cutting.', 'tip':'Keep the layers relaxed and check the real garment.'} for title in ['Prepare and measure','Cut the backing','Baste the layers','Practise the stitch','Sew the feather','Finish and inspect']],
    'paths':[[[.05,.05],[.95,.05],[.95,.95],[.05,.95],[.05,.05]],[[.4,.8],[.5,.5],[.6,.2]],[[.5,.5],[.3,.3],[.4,.2],[.5,.3],[.5,.5]]],
}

@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-not-real')
    monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')


def result(project):
    return {'state':'ready','style':'branch','design':deepcopy(DESIGN),'source_revision':project.revision,
            'provider':'openai','model':'mock-only','image_key':store.put(b'not-real-image','png'),'disclaimer':'AI concept.'}


def test_provider_receives_original_mask_and_stitch_guide_and_preserves_other_pixels(client,user,monkeypatch):
    p=ready(client)
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-not-real')
    monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')
    captured=[]
    def handler(request):
        body=json.loads(request.content);captured.append(body)
        assert request.headers['Authorization']=='Bearer test-key-not-real'
        if request.url.path.endswith('/responses'):
            wire=deepcopy(DESIGN);wire['paths']=[[[round(v*1000) for v in point] for point in path] for path in DESIGN['paths']]
            return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(wire)}]}]})
        image=Image.new('RGB',(320,260),(255,0,0));stream=io.BytesIO();image.save(stream,format='PNG')
        return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(stream.getvalue()).decode()}]})
    original_client=httpx.Client
    monkeypatch.setattr(creative.httpx,'Client',lambda **kwargs:original_client(transport=httpx.MockTransport(handler),**kwargs))
    with Session() as db:
        project=db.get(Project,p['id']);project.preview={'requested_style':None}
        original=Image.open(io.BytesIO(store.get(project.image_key))).convert('RGB')
        rectangle=creative.repair_rectangle(original,project.analysis)
        generated=creative.generate_preview(project)
    assert len(captured)==2
    assert captured[0]['store'] is False
    assert captured[1]['n']==1 and len(captured[1]['images'])==2
    mask=Image.open(io.BytesIO(base64.b64decode(captured[1]['mask']['image_url'].split(',')[1])))
    assert mask.size==original.size and mask.getpixel((0,0))[3]==255
    output=Image.open(io.BytesIO(store.get(generated['image_key']))).convert('RGB')
    changed=np.any(np.asarray(output)!=np.asarray(original),axis=2)
    x0,y0,x1,y1=rectangle
    allowed=np.zeros(changed.shape,dtype=bool);allowed[y0:y1+1,x0:x1+1]=True
    assert changed.any() and not changed[~allowed].any()
    assert generated['design']['name']==DESIGN['name']


def test_preview_refresh_compile_and_matching_paths(client,user,monkeypatch):
    p=ready(client)
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-not-real');monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')
    monkeypatch.setattr(worker,'generate_preview',result)
    url='/api/v1/projects/'+p['id']
    response=client.post(url+'/preview',json={})
    assert response.status_code==202,response.text
    first=response.json()['preview']['revision']
    assert client.post(url+'/preview',json={}).status_code==409
    assert client.post(url+'/compile',json={'revision':p['revision'],'confirmed':True,'style':'branch'}).status_code==409
    assert worker.run_once()
    fresh=client.get(url).json()
    assert fresh['status']=='ready' and fresh['preview']['state']=='ready'
    assert 'image_key' not in fresh['preview']
    assert client.get(url+'/preview.png').status_code==200
    assert client.post(url+'/compile',json={'revision':p['revision'],'confirmed':True,'style':'waves'}).status_code==409
    assert client.post(url+'/compile',json={'revision':p['revision'],'confirmed':True,'style':'branch'}).status_code==202
    assert worker.run_once()
    fresh=client.get(url).json()
    assert fresh['plan']['name']==DESIGN['name']
    assert fresh['plan']['design_revision']==first
    assert fresh['plan']['creative_steps']==DESIGN['steps']
    assert fresh['plan']['lines'][1][0]==[round(.4*fresh['plan']['width_mm'],2),round(.8*fresh['plan']['height_mm'],2)]
    assert client.post(url+'/preview',json={}).json()['preview']['revision']==first+1
    assert worker.run_once()


def test_preview_failure_does_not_lose_assessment_or_retry_paid_call(client,user,monkeypatch):
    p=ready(client)
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-not-real');monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')
    calls=[]
    def fail(project):calls.append(1);raise VisionError('Preview timed out. Refresh to try again.')
    monkeypatch.setattr(worker,'generate_preview',fail)
    url='/api/v1/projects/'+p['id']
    assert client.post(url+'/preview',json={}).status_code==202
    assert worker.run_once() and not worker.run_once()
    fresh=client.get(url).json()
    assert calls==[1] and fresh['status']=='ready' and fresh['analysis'] and fresh['plan']
    assert fresh['preview']['state']=='failed'
    assert client.post(url+'/preview',json={}).status_code==202


def test_expired_preview_lease_surfaces_manual_retry(client,user,monkeypatch):
    p=ready(client)
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-not-real');monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')
    assert client.post('/api/v1/projects/'+p['id']+'/preview',json={}).status_code==202
    with Session.begin() as db:
        job=db.scalar(select(Job).where(Job.kind=='preview'))
        job.state='running';job.attempts=1;job.lock_token='expired';job.lease_until=time.time()-1
    assert not worker.run_once()
    worker.reap_exhausted()
    fresh=client.get('/api/v1/projects/'+p['id']).json()
    assert fresh['status']=='ready' and fresh['preview']['state']=='failed'


@pytest.mark.parametrize('status',[401,403,429,500,400])
def test_provider_errors_are_safe_and_not_automatically_replayed(monkeypatch,status):
    client_type=httpx.Client
    calls=[]
    def handler(request):calls.append(1);return httpx.Response(status,text='SECRET PROVIDER DETAILS')
    monkeypatch.setattr(creative.httpx,'Client',lambda **kwargs:client_type(transport=httpx.MockTransport(handler),**kwargs))
    with pytest.raises(VisionError) as failure:creative._request('https://api.openai.com/v1/images/edits',{},300)
    assert len(calls)==1 and not failure.value.retryable and 'SECRET' not in str(failure.value)


def test_invalid_or_unbounded_design_is_rejected():
    for paths in [[[[0,0],[1,1]]], [[[.2,.2],[float('nan'),.4]],[[.2,.2],[.3,.3]]]]:
        with pytest.raises(ValueError):creative.RepairDesign.model_validate({**DESIGN,'paths':paths})


def test_preview_disabled_and_private_ownership(client,user):
    p=ready(client)
    assert client.post('/api/v1/projects/'+p['id']+'/preview',json={}).status_code==503
    assert client.get('/api/v1/projects/'+p['id']+'/preview.png').status_code==404
    from fastapi.testclient import TestClient
    from kintsugi.main import app
    with TestClient(app) as other:
        account(other,'preview-other@example.com')
        assert other.get('/api/v1/projects/'+p['id']+'/preview.png').status_code==404


def test_finished_assessment_automatically_queues_creative_job(client,user,enabled,monkeypatch):
    from conftest import upload
    p=upload(client)
    analysis={'box':[.3,.2,.65,.75],'width_mm':35,'height_mm':40,'margin_mm':10,'fabric':'Denim','outlines':[],'scale_source':'suggested'}
    monkeypatch.setattr(worker,'analyze_damage',lambda data,settings:analysis)
    monkeypatch.setattr(worker,'generate_preview',result)
    url='/api/v1/projects/'+p['id']
    assert client.post(url+'/analyze',json={}).status_code==202
    assert worker.run_once()
    fresh=client.get(url).json()
    assert fresh['status']=='needs_review' and fresh['preview']['state']=='queued'
    assert worker.run_once()
    assert client.get(url).json()['preview']['state']=='ready'


def test_superseded_preview_cannot_replace_newer_design(client,user,monkeypatch):
    p=ready(client)
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-not-real');monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')
    url='/api/v1/projects/'+p['id']
    assert client.post(url+'/preview',json={}).status_code==202
    stale_key=[]
    def supersede(project):
        old=result(project);stale_key.append(old['image_key'])
        with Session.begin() as db:
            current=db.get(Project,project.id);current.preview_revision+=1;current.preview={'state':'ready','design':{'name':'Newer design'}}
        return old
    monkeypatch.setattr(worker,'generate_preview',supersede)
    assert worker.run_once()
    assert client.get(url).json()['preview']['design']['name']=='Newer design'
    with pytest.raises(FileNotFoundError):store.get(stale_key[0])


def test_maker_request_keeps_an_immutable_private_preview_snapshot(client,user,monkeypatch):
    p=ready(client)
    with Session.begin() as db:
        project=db.get(Project,p['id']);project.preview=result(project);old_key=project.preview['image_key']
    response=client.post('/api/v1/network/requests',json={'project_id':p['id'],'brief':'Please make this creative feather repair for me.','consent_to_share':True})
    assert response.status_code==201,response.text
    service=response.json()
    assert service['design']['has_preview'] and 'preview_key' not in service['design']
    with Session.begin() as db:
        project=db.get(Project,p['id']);project.preview=result(project)
        assert project.preview['image_key']!=old_key
    assert client.get('/api/v1/network/requests/'+service['id']+'/preview.png').content==store.get(old_key)


def test_precise_edit_mask_preserves_weave_between_motif_strokes(client,user):
    p=ready(client)
    with Session() as db:
        project=db.get(Project,p['id'])
        original=Image.open(io.BytesIO(store.get(project.image_key))).convert('RGB')
        mask=np.asarray(creative.edit_region(original,project.analysis,creative.RepairDesign.model_validate(DESIGN)))
        x0,y0,x1,y1=creative.repair_rectangle(original,project.analysis)
    assert not mask[:y0].any() and not mask[y1:].any()
    assert not mask[:,:x0].any() and not mask[:,x1:].any()
    assert np.any(mask[y0:y1,x0:x1]==0)
