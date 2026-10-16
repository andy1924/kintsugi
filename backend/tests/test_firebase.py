import json
import time
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import select,update,func
from conftest import account,upload
from kintsugi import config,firebase_app,firebase_sync,firebase_outbox
from kintsugi.db import Session
from kintsugi.models import User,Project,FirebaseOutbox

TOKEN='synthetic-token-for-tests-only'
IDENTITY={'uid':'firebase-google-test-uid','email':'google@example.com','name':'Google Mender'}

@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(firebase_app,'verify_google_token',lambda token:IDENTITY)


def test_google_session_creates_customer_and_private_cookie(client,google):
    response=client.post('/api/v1/auth/firebase/session',json={'id_token':TOKEN,'role':'operator'})
    assert response.status_code==200,response.text
    assert response.json()['user']['role']=='customer'
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Max-Age=3600' in response.headers['set-cookie']
    assert client.get('/api/v1/auth/me').status_code==200
    response2=client.post('/api/v1/auth/firebase/session',json={'id_token':TOKEN})
    assert response2.json()['user']['id']==response.json()['user']['id']
    with Session() as db:assert db.scalar(select(func.count()).select_from(User))==1


def test_existing_account_requires_authenticated_explicit_link(client,google):
    user=account(client,'google@example.com')
    assert client.post('/api/v1/auth/firebase/session',json={'id_token':TOKEN}).status_code==409
    assert client.post('/api/v1/auth/firebase/link',json={'id_token':TOKEN}).json()['linked']
    result=client.post('/api/v1/auth/firebase/session',json={'id_token':TOKEN})
    assert result.json()['user']['id']==user['id']


def test_google_cannot_link_another_email_or_bypass_csrf(client,user,google):
    assert client.post('/api/v1/auth/firebase/link',json={'id_token':TOKEN}).status_code==409
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/v1/auth/firebase/link',json={'id_token':TOKEN}).status_code==403


def test_google_origin_and_token_failures(client,monkeypatch):
    def invalid(token):raise HTTPException(401,'Invalid token')
    monkeypatch.setattr(firebase_app,'verify_google_token',invalid)
    assert client.post('/api/v1/auth/firebase/session',json={'id_token':TOKEN}).status_code==401
    assert client.post('/api/v1/auth/firebase/session',json={'id_token':TOKEN},headers={'Origin':'https://evil.example'}).status_code==403
    with Session() as db:assert db.scalar(select(func.count()).select_from(User))==0


@pytest.mark.parametrize('changes',[
    {'email_verified':False},{'firebase':{'sign_in_provider':'password'}},
    {'auth_time':0},{'auth_time':time.time()+3600},{'uid':''},
    {'firebase':{'sign_in_provider':'google.com','tenant':'unconfigured-tenant'}},
])
def test_admin_verification_rejects_untrusted_identity(monkeypatch,changes):
    from firebase_admin import auth
    claims={'uid':'google-123','email':'a@example.com','name':'Mender','email_verified':True,'firebase':{'sign_in_provider':'google.com'},'auth_time':time.time(),**changes}
    monkeypatch.setattr(firebase_app,'admin_app',lambda:object())
    def verify(token,**kwargs):
        assert kwargs['check_revoked'] is True
        return claims
    monkeypatch.setattr(auth,'verify_id_token',verify)
    with pytest.raises(HTTPException) as failure:firebase_app.verify_google_token(TOKEN)
    assert failure.value.status_code==401


def test_public_configuration_never_contains_server_credentials(client,monkeypatch):
    monkeypatch.setattr(config,'FIREBASE_PROJECT_ID','demo-kintsugi')
    monkeypatch.setattr(config,'FIREBASE_WEB_API_KEY','public-web-key')
    monkeypatch.setattr(config,'FIREBASE_WEB_APP_ID','public-app-id')
    monkeypatch.setattr(config,'FIREBASE_AUTH_DOMAIN','demo-kintsugi.firebaseapp.com')
    body=client.get('/api/v1/auth/firebase/config').json()
    assert body['enabled'] and set(body['config'])=={'apiKey','projectId','appId','authDomain'}


@pytest.fixture
def cloud(monkeypatch):monkeypatch.setattr(config,'FIRESTORE_ENABLED',True)


def test_outbox_is_atomic_coalesced_and_excludes_passwords(client,user,cloud):
    p=upload(client)
    with Session.begin() as db:
        firebase_outbox.backfill(db)
    with Session() as db:
        row=db.get(FirebaseOutbox,'users/'+user['id'])
        assert 'password' not in json.loads(row.payload['json'])
        assert TOKEN not in row.payload['json']
        project=db.get(FirebaseOutbox,'projects/'+p['id']);version=project.version
    with Session.begin() as db:
        project=db.get(Project,p['id']);project.title='Updated title'
    with Session() as db:
        row=db.get(FirebaseOutbox,'projects/'+p['id'])
        assert row.version==version+1 and json.loads(row.payload['json'])['title']=='Updated title'
    with Session() as db:
        project=db.get(Project,p['id']);project.title='Never committed';db.flush();db.rollback()
    with Session() as db:assert json.loads(db.get(FirebaseOutbox,'projects/'+p['id']).payload['json'])['title']=='Updated title'


def test_bulk_changes_are_not_lost(client,user,cloud):
    p=upload(client)
    with Session.begin() as db:db.execute(update(Project).where(Project.id==p['id']).values(status='failed'))
    with Session() as db:assert json.loads(db.get(FirebaseOutbox,'projects/'+p['id']).payload['json'])['status']=='failed'


def test_firestore_outage_keeps_retryable_change(client,user,cloud,monkeypatch):
    p=upload(client)
    def offline(*args):raise OSError('private credentials must not be logged')
    monkeypatch.setattr(firebase_sync,'write_document',offline)
    assert firebase_sync.run_once()
    with Session() as db:
        row=db.get(FirebaseOutbox,'projects/'+p['id'])
        assert row.pending and row.attempts==1 and row.next_attempt>time.time()
        assert 'private credentials' not in row.last_error
    assert not firebase_sync.run_once()


def test_newer_update_during_sync_stays_pending(client,user,cloud,monkeypatch):
    p=upload(client);calls=[]
    def write(collection,document_id,payload,version):
        calls.append(version)
        if len(calls)==1:
            with Session.begin() as db:db.get(Project,p['id']).title='Changed during network write'
    monkeypatch.setattr(firebase_sync,'write_document',write)
    assert firebase_sync.run_once()
    with Session() as db:
        row=db.get(FirebaseOutbox,'projects/'+p['id']);assert row.pending and row.synced_version<row.version
    assert firebase_sync.run_once()
    with Session() as db:
        row=db.get(FirebaseOutbox,'projects/'+p['id']);assert not row.pending and row.synced_version==row.version
    assert calls==[1,2]


def test_firestore_reads_enforce_owner_and_hide_storage_keys(client,user,cloud,monkeypatch):
    doc={'version':3,'deleted':False,'data':{'user_id':user['id'],'json':json.dumps({'id':'test','image_key':'private.jpg','plan':{'pdf_key':'private.pdf','name':'Golden branch'}})}}
    reference=SimpleNamespace(get=lambda **kwargs:SimpleNamespace(exists=True,to_dict=lambda:doc))
    fake=SimpleNamespace(collection=lambda name:SimpleNamespace(document=lambda key:reference))
    import kintsugi.firebase_cloud as module
    monkeypatch.setattr(module,'firestore_client',lambda:fake)
    response=client.get('/api/v1/firebase/projects/test');assert response.status_code==200
    assert 'private' not in response.text
    doc['data']['user_id']='other-user'
    assert client.get('/api/v1/firebase/projects/test').status_code==404
    assert client.get('/api/v1/firebase/sync-status').status_code==403


def test_generation_savepoints_also_commit_cloud_changes(client,user,cloud,monkeypatch):
    from conftest import ready
    from kintsugi import worker
    from test_creative import result
    p=ready(client)
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-key-not-real')
    monkeypatch.setattr(config,'REPAIR_PREVIEW_PROVIDER','openai')
    monkeypatch.setattr(worker,'generate_preview',result)
    assert client.post('/api/v1/projects/'+p['id']+'/preview',json={}).status_code==202
    assert worker.run_once()
    with Session() as db:
        rows=db.scalars(select(FirebaseOutbox).where(FirebaseOutbox.collection=='kintsugi_repair_generations')).all()
        assert len(rows)==1 and json.loads(rows[0].payload['json'])['state']=='ready'
        project=db.get(FirebaseOutbox,'projects/'+p['id'])
        assert json.loads(project.payload['json'])['preview']['state']=='ready'


def test_firestore_transaction_rejects_an_out_of_order_write(monkeypatch):
    from google.cloud import firestore
    stored={'version':4};writes=[]
    reference=SimpleNamespace(get=lambda **kwargs:SimpleNamespace(exists=True,to_dict=lambda:stored))
    tx=SimpleNamespace(set=lambda reference,data:writes.append(data))
    client=SimpleNamespace(collection=lambda name:SimpleNamespace(document=lambda id:reference),transaction=lambda **kwargs:tx)
    monkeypatch.setattr(firebase_sync,'firestore_client',lambda:client)
    monkeypatch.setattr(firestore,'transactional',lambda fn:fn)
    firebase_sync.write_document('kintsugi_projects','test',{'json':'{}'},3)
    assert writes==[]
    firebase_sync.write_document('kintsugi_projects','test',{'json':'{}'},5)
    assert len(writes)==1 and writes[0]['version']==5 and not writes[0]['deleted']
