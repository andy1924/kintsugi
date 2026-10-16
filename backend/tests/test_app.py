import io
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select,update,func
from conftest import account,photo,upload,ready
from kintsugi.main import app
from kintsugi.db import Session
from kintsugi.models import Project,Job,Completion,LoginSession,User
from kintsugi.worker import run_once,claim,reap_exhausted
from kintsugi.imaging import normalize



def complete(client,p,seed=9):
    return client.post(f'/api/v1/projects/{p["id"]}/complete',files={'image':('after.jpg',photo(seed),'image/jpeg')})

def test_auth_session_csrf_logout(client,user):
    assert client.get('/api/v1/auth/me').json()['user']['id']==user['id']
    token=client.headers.pop('X-CSRF-Token')
    assert client.post('/api/v1/auth/logout').status_code==403
    client.headers['X-CSRF-Token']=token
    assert client.post('/api/v1/auth/logout').status_code==204
    assert client.get('/api/v1/projects').status_code==401

@pytest.mark.parametrize('email,password',[('bad','12345678901'),('a@b.c','short')])
def test_registration_validation(client,email,password):
    assert client.post('/api/v1/auth/register',json={'name':'Mender','email':email,'password':password}).status_code==422

def test_login_and_duplicate_account(client,user):
    assert client.post('/api/v1/auth/register',json={'name':'M','email':'MENDER@example.com','password':'long-password'}).status_code==409
    assert client.post('/api/v1/auth/login',json={'email':'mender@example.com','password':'incorrect-password'}).status_code==401
    assert client.post('/api/v1/auth/login',json={'email':'mender@example.com','password':'my-secure-test-pass'}).status_code==200

def test_expired_session(client,user):
    with Session.begin() as db:db.execute(update(LoginSession).values(expires_at=time.time()-1))
    assert client.get('/api/v1/auth/me').status_code==401

def test_origin_and_rate_limit(client):
    data={'name':'M','email':'a@example.com','password':'valid-password'}
    assert client.post('/api/v1/auth/register',json=data,headers={'Origin':'https://evil.example'}).status_code==403
    for i in range(10):
        data['email']=f'a{i}@example.com';assert client.post('/api/v1/auth/register',json=data).status_code==201
    assert client.post('/api/v1/auth/register',json=data).status_code==429

def test_private_assets_and_ownership(client,user):
    p=upload(client)
    with TestClient(app) as other:
        account(other,'other@example.com')
        for suffix in ['', '/image','/pattern.pdf']:
            assert other.get('/api/v1/projects/'+p['id']+suffix).status_code==404
        assert other.post('/api/v1/projects/'+p['id']+'/analyze',json={'box':[.2,.2,.8,.8],'width_mm':30}).status_code==404
    assert client.get('/api/v1/projects/'+p['id']+'/image').headers['cache-control']=='no-store'

def test_bad_upload(client,user):
    assert client.post('/api/v1/projects',files={'image':('fake.jpg',b'not a photo','image/jpeg')}).status_code==422
    assert client.post('/api/v1/projects',files={'image':('big.jpg',b'a'*(13*1024*1024),'image/jpeg')}).status_code==413

def test_small_photo_rejected():
    from PIL import Image
    stream=io.BytesIO();Image.new('RGB',(50,50)).save(stream,'PNG')
    with pytest.raises(ValueError,match='100 pixels'):normalize(stream.getvalue())

def test_pipeline_exports_and_confirmed_geometry(client,user):
    p=ready(client)
    assert p['analysis']['engine'].startswith('OpenCV')
    assert p['plan']['width_mm']==55
    assert 'pdf_key' not in p['plan'] and 'image_key' not in p
    pdf=client.get(f'/api/v1/projects/{p["id"]}/pattern.pdf')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    reader=PdfReader(io.BytesIO(pdf.content))
    assert len(reader.pages)==2
    assert '20 mm calibration bar' in reader.pages[1].extract_text()
    assert abs(float(reader.pages[1].mediabox.width)-595.276)<.01
    svg=client.get(f'/api/v1/projects/{p["id"]}/pattern.svg')
    assert 'width="55.0mm"' in svg.text
    assert '<script' not in svg.text
    assert client.post(f'/api/v1/projects/{p["id"]}/complete',files={'image':('after.jpg',photo(1),'image/jpeg')}).status_code==422

def test_compile_requires_review_and_current_revision(client,user):
    p=upload(client)
    url=f'/api/v1/projects/{p["id"]}'
    assert client.post(url+'/compile',json={'revision':1,'style':'branch','confirmed':True}).status_code==409
    assert client.post(url+'/analyze',json={'box':[.4,.4,.3,.7],'width_mm':30}).status_code==422
    assert client.post(url+'/analyze',json={'box':[.3,.2,.65,.75],'width_mm':35}).status_code==202
    assert client.post(url+'/analyze',json={'box':[.3,.2,.65,.75],'width_mm':35}).status_code==409
    run_once()
    assert client.post(url+'/compile',json={'revision':99,'style':'branch','confirmed':True}).status_code==409
    assert client.post(url+'/compile',json={'revision':1,'style':'branch','confirmed':False}).status_code==422
    assert client.post(url+'/compile',json={'revision':1,'style':'waves','confirmed':True}).status_code==202





def test_jobs_claim_once_and_recover_lease(client,user):
    p=upload(client);client.post(f'/api/v1/projects/{p["id"]}/analyze',json={'box':[.3,.2,.65,.75],'width_mm':35})
    with ThreadPoolExecutor(2) as pool:claims=list(pool.map(lambda _:claim(),range(2)))
    assert sum(c is not None for c in claims)==1
    with Session.begin() as db:db.execute(update(Job).values(lease_until=time.time()-1))
    assert run_once()
    assert client.get('/api/v1/projects/'+p['id']).json()['status']=='needs_review'

def test_worker_retry_exhaustion(client,user,monkeypatch):
    p=upload(client);client.post(f'/api/v1/projects/{p["id"]}/analyze',json={'box':[.3,.2,.65,.75],'width_mm':35})
    def broken(*_):raise RuntimeError('private implementation detail')
    monkeypatch.setattr('kintsugi.worker.analyze_damage',broken)
    for _ in range(3):
        assert run_once()
        with Session.begin() as db:db.execute(update(Job).values(run_after=0))
    project=client.get('/api/v1/projects/'+p['id']).json()
    assert project['status']=='failed' and 'private implementation' not in project['error']

def test_exhausted_crashed_job_becomes_failed(client,user):
    p=upload(client);client.post(f'/api/v1/projects/{p["id"]}/analyze',json={'box':[.3,.2,.65,.75],'width_mm':35})
    with Session.begin() as db:db.execute(update(Job).values(state='running',attempts=3,lease_until=0))
    reap_exhausted()
    assert client.get('/api/v1/projects/'+p['id']).json()['status']=='failed'

def test_parallel_completion_only_awards_once(client,user):
    p=ready(client);cookie=dict(client.cookies);headers=dict(client.headers)
    def submit(_):
        with TestClient(app,cookies=cookie,headers=headers) as other:return complete(other,p).status_code
    with ThreadPoolExecutor(2) as pool:statuses=list(pool.map(submit,range(2)))
    assert statuses==[200,200]
    assert client.get('/api/v1/projects/'+p['id']).json()['status']=='completed'

def test_metadata_stripped_and_large_image_resized():
    from PIL import Image
    image=Image.new('RGB',(2000,1200),'blue');stream=io.BytesIO();image.save(stream,'JPEG',exif=Image.Exif())
    data,w,h,sha,phash=normalize(stream.getvalue())
    assert (w,h)==(1600,960)
    assert not Image.open(io.BytesIO(data)).getexif()

def test_health_reports_real_worker_status(client):
    result=client.get('/api/v1/health').json()
    assert result['status']=='ok' and result['worker_available'] is False

def test_model_misconfiguration_fails_explicitly(monkeypatch):
    from kintsugi import config
    from kintsugi.imaging import validate_model
    monkeypatch.setattr(config,'MODEL','pretend-model')
    with pytest.raises(RuntimeError):validate_model()


def test_chunked_upload_limit(client,user):
    def body():
        yield b'--limit-test\r\nContent-Disposition: form-data; name="image"; filename="large.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'
        for _ in range(14):yield b'a'*(1024*1024)
        yield b'\r\n--limit-test--\r\n'
    response=client.post('/api/v1/projects',content=body(),headers={'Content-Type':'multipart/form-data; boundary=limit-test'})
    assert response.status_code==413

def test_tiled_pattern_preserves_large_dimensions():
    from kintsugi.compiler import pdf_bytes,lines_for
    plan={'name':'Golden branch','width_mm':170,'height_mm':320,'margin_mm':10,'lines':lines_for('branch',170,320,10,'seed'),'estimated_minutes':60,'materials':['Needle, thread and compatible backing'],'instructions':['Measure the calibration bar.'],'disclaimer':'User-measured scale.'}
    reader=PdfReader(io.BytesIO(pdf_bytes(plan,'Large repair')))
    assert len(reader.pages)==3

def test_branch_geometry_uses_damage_not_only_photo_seed():
    from kintsugi.compiler import damage_paths
    base={'margin_mm':10,'width_mm':40,'height_mm':40,'box':[.2,.2,.8,.8]}
    vertical={**base,'outlines':[[[.45,.23],[.55,.23],[.55,.77],[.45,.77]]]}
    horizontal={**base,'outlines':[[[.23,.45],[.77,.45],[.77,.55],[.23,.55]]]}
    a=damage_paths(vertical);b=damage_paths(horizontal)
    assert a and b and a!=b
    assert all(0<=x<=60 and 0<=y<=60 for path in a+b for x,y in path)

def test_tutorial_progress_saved_privately(client,user):
    p=ready(client)
    response=client.post('/api/v1/projects/'+p['id']+'/tutorial',json={'completed':[3,0,1,1]})
    assert response.status_code==200,response.text
    assert response.json()['tutorial_steps']==[0,1,3]
    assert client.get('/api/v1/projects/'+p['id']).json()['tutorial_steps']==[0,1,3]
    assert client.post('/api/v1/projects/'+p['id']+'/tutorial',json={'completed':[7]}).status_code==422
    with TestClient(app) as other:
        account(other,'guide-other@example.com')
        assert other.post('/api/v1/projects/'+p['id']+'/tutorial',json={'completed':[0]}).status_code==404

def test_textile_tutorial_requires_pattern(client,user):
    p=upload(client)
    assert client.post('/api/v1/projects/'+p['id']+'/tutorial',json={'completed':[0]}).status_code==409

def test_ceramic_tutorial_can_record_a_finished_piece(client,user):
    p=client.post('/api/v1/projects',data={'title':'Decorative vase','category':'ceramic'},files={'image':('vase.jpg',photo(),'image/jpeg')}).json()
    url='/api/v1/projects/'+p['id']
    assert client.post(url+'/complete',files={'image':('after.jpg',photo(90),'image/jpeg')}).status_code==409
    assert client.post(url+'/tutorial',json={'completed':[0,1,2,3,4,5]}).status_code==200
    assert client.post(url+'/complete',files={'image':('after.jpg',photo(90),'image/jpeg')}).json()['recorded'] is True

def test_new_geometry_resets_guide_progress(client,user):
    p=ready(client);url='/api/v1/projects/'+p['id']
    client.post(url+'/tutorial',json={'completed':[0,1]})
    response=client.post(url+'/analyze',json={'box':[.25,.25,.7,.75],'width_mm':40})
    assert response.status_code==202
    assert response.json()['tutorial_steps']==[]
