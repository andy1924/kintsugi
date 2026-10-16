import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,update,func
from conftest import account,upload,photo
from kintsugi.main import app
from kintsugi.db import Session
from kintsugi.models import User,Maker,RepairService,ServiceQuote,Shipment,MakerEarning

ADDRESS={'name':'Test Recipient','phone':'+919999999999','line1':'10 Test Street','city':'Pune','postal_code':'411001','country':'IN'}
APPLICATION={'name':'Test Craft Workroom','about':'Independent textile mending and embroidery for well-loved pieces.','city':'Pune','categories':['textile','ceramic'],'community':'women_led','address':ADDRESS,'consent_to_list':True}

@pytest.fixture
def network(client,user):
    maker_client=TestClient(app);maker_user=account(maker_client,'maker@example.com')
    op=TestClient(app);operator=account(op,'operator@example.com')
    with Session.begin() as db:db.execute(update(User).where(User.id==operator['id']).values(role='operator'))
    result=maker_client.post('/api/v1/network/profile',json=APPLICATION)
    assert result.status_code==201,result.text
    maker=result.json()
    assert op.post(f'/api/v1/network/makers/{maker["id"]}/review',json={'decision':'approved'}).status_code==200
    p=upload(client)
    response=client.post('/api/v1/network/requests',json={'project_id':p['id'],'maker_id':maker['id'],'brief':'Please embroider a branching repair over this tear.','replacement_minor':300000,'consent_to_share':True})
    assert response.status_code==201,response.text
    yield {'customer':client,'maker':maker_client,'operator':op,'profile':maker,'service':response.json(),'project':p}
    maker_client.close();op.close()

def quote(n):
    url='/api/v1/network/requests/'+n['service']['id']
    q=n['maker'].post(url+'/quote',json={'labour_minor':50000,'materials_minor':10000,'days':7,'notes':'Gold running stitch with a matching cotton backing.'})
    assert q.status_code==200,q.text
    version=q.json()['quote']['version']
    q=n['operator'].post(url+'/shipping-price',json={'version':version,'outbound_minor':10000,'return_minor':10000})
    assert q.status_code==200,q.text
    return url,q.json()

def accept(n):
    url,q=quote(n)
    response=n['customer'].post(url+'/accept',json={'version':q['quote']['version'],'address':ADDRESS,'packaging_acknowledged':True})
    assert response.status_code==200,response.text
    return url,response.json()

def shipping(n,url,leg,status):
    return n['operator'].post(url+'/shipments/'+leg,json={'status':status,'courier':'Test Carrier','tracking':'TEST-12345','tracking_url':'https://example.com/tracking/TEST-12345','pickup_at':'2026-10-20T12:00'})

def test_incentive_endpoints_removed(client,user):
    assert client.get('/api/v1/wallet').status_code==404
    assert client.post('/api/v1/rewards/heritage-patterns/redeem').status_code==404


def test_rural_filter_only_lists_approved_matching_workrooms(network):
    n=network;client=n['customer']
    assert client.get('/api/v1/network/makers?community=rural_enterprise').json()==[]
    with Session.begin() as db:
        db.get(Maker,n['profile']['id']).community='rural_enterprise'
    rural=client.get('/api/v1/network/makers?community=rural_enterprise').json()
    assert [maker['id'] for maker in rural]==[n['profile']['id']]
    assert client.get('/api/v1/network/makers?community=women_led').json()==[]

def test_maker_approval_and_private_profile(client,user):
    result=client.post('/api/v1/network/profile',json=APPLICATION);assert result.status_code==201
    assert client.get('/api/v1/network/makers').json()==[]
    assert client.post('/api/v1/network/makers/'+result.json()['id']+'/review',json={'decision':'approved'}).status_code==403
    assert client.get('/api/v1/network/profile').json()['address']==ADDRESS
    assert client.post('/api/v1/network/profile',json=APPLICATION).status_code==409

def test_registration_cannot_choose_operator(client):
    response=client.post('/api/v1/auth/register',json={'name':'Tester','email':'role@example.com','password':'long-password','role':'operator'})
    assert response.json()['user']['role']=='customer'

def test_empty_network_keeps_request_unmatched(client,user):
    p=upload(client)
    request={'project_id':p['id'],'brief':'Please mend this garment with a gold design.','consent_to_share':True}
    response=client.post('/api/v1/network/requests',json=request)
    assert response.status_code==201 and response.json()['status']=='awaiting_match'
    assert response.json()['shipments']==[]
    assert client.post('/api/v1/network/requests',json=request).status_code==409
    request['consent_to_share']=False
    assert client.post('/api/v1/network/requests',json=request).status_code==422

def test_quote_price_and_maker_pay_are_separate(network):
    url,result=quote(network);q=result['quote']
    assert q['maker_earns_minor']==60000
    assert q['fee_minor']==3000 and q['total_minor']==83000
    assert q['saving_minor']==217000
    assert result['status']=='quoted'
    assert 'address' not in result['maker']
    assert network['maker'].get(url).json().get('return_address') is None

def test_customer_cannot_quote_or_approve_payment(network):
    url='/api/v1/network/requests/'+network['service']['id']
    response=network['customer'].post(url+'/quote',json={'labour_minor':10000,'materials_minor':0,'days':3,'notes':'Repair with visible running stitches.'})
    assert response.status_code==403
    assert network['customer'].post(url+'/payment',json={'reference':'fake-reference'}).status_code==403
    with TestClient(app) as other:
        account(other,'other@example.com')
        assert other.get(url).status_code==404 and other.get(url+'/image').status_code==404

def test_acceptance_is_idempotent_and_versioned(network):
    url,q=quote(network);body={'version':q['quote']['version']-1,'address':ADDRESS,'packaging_acknowledged':True}
    assert network['customer'].post(url+'/accept',json=body).status_code==409
    body['version']+=1
    assert network['customer'].post(url+'/accept',json=body).status_code==200
    assert network['customer'].post(url+'/accept',json=body).status_code==200
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Shipment))==2
        assert db.scalar(select(func.count()).select_from(MakerEarning))==1
        assert db.scalar(select(MakerEarning.amount_minor))==60000
    view=network['maker'].get(url).json();assert 'return_address' not in view
    assert network['operator'].get(url).json()['return_address']==ADDRESS

def test_expired_quote_requires_repricing(network):
    url,q=quote(network)
    with Session.begin() as db:db.execute(update(ServiceQuote).values(expires_at=time.time()-1))
    assert network['customer'].post(url+'/accept',json={'version':q['quote']['version'],'address':ADDRESS,'packaging_acknowledged':True}).status_code==409

def test_full_two_way_fulfilment_and_payout(network):
    n=network;url,result=accept(n)
    assert result['payment_status']=='awaiting_payment'
    assert shipping(n,url,'outbound','scheduled').status_code==409
    assert n['operator'].post(url+'/payment',json={'reference':'TEST-RECEIVED-001'}).status_code==200
    assert shipping(n,url,'outbound','delivered').status_code==409
    assert shipping(n,url,'return','scheduled').status_code==409
    for state in ['scheduled','in_transit','delivered']:assert shipping(n,url,'outbound',state).status_code==200
    assert n['maker'].post(url+'/progress',json={'status':'repairing'}).status_code==200
    assert n['maker'].post(url+'/progress',json={'status':'ready_for_return'}).status_code==200
    for state in ['scheduled','in_transit','delivered']:assert shipping(n,url,'return',state).status_code==200
    earnings=n['maker'].get('/api/v1/network/earnings').json();assert earnings[0]['status']=='payable'
    assert earnings[0]['amount_minor']==60000
    assert n['customer'].post(url+'/payout',json={'reference':'FAKE-PAYOUT'}).status_code==403
    assert n['operator'].post(url+'/payout',json={'reference':'TEST-TRANSFER-001'}).status_code==200
    assert n['operator'].post(url+'/payout',json={'reference':'TEST-TRANSFER-001'}).status_code==200
    assert n['maker'].get('/api/v1/network/earnings').json()[0]['status']=='paid'

def test_maker_can_decline_or_pause_without_penalty(network):
    n=network;url='/api/v1/network/requests/'+n['service']['id']
    assert n['maker'].post(url+'/progress',json={'status':'declined'}).json()['status']=='awaiting_match'
    assert n['maker'].post('/api/v1/network/profile/availability',json={'accepting_work':False}).status_code==200
    assert n['customer'].get('/api/v1/network/makers').json()==[]
    assert n['operator'].post(url+'/assign',json={'maker_id':n['profile']['id']}).status_code==409

def test_quote_cannot_be_changed_after_acceptance(network):
    url,_=accept(network)
    assert network['maker'].post(url+'/quote',json={'labour_minor':900000,'materials_minor':0,'days':3,'notes':'A different price after accepting.'}).status_code==409
    assert network['customer'].post(url+'/cancel').status_code==409

def test_unsafe_tracking_urls_rejected(network):
    url,_=accept(network)
    response=network['operator'].post(url+'/shipments/outbound',json={'status':'scheduled','courier':'Test','tracking':'TEST-1','tracking_url':'javascript:alert(1)','pickup_at':'tomorrow'})
    assert response.status_code==422

def test_parallel_acceptance_creates_one_earning_and_two_legs(network):
    n=network;url,q=quote(n);cookies=dict(n['customer'].cookies);headers=dict(n['customer'].headers)
    def send(_):
        with TestClient(app,cookies=cookies,headers=headers) as client:return client.post(url+'/accept',json={'version':q['quote']['version'],'address':ADDRESS,'packaging_acknowledged':True}).status_code
    with ThreadPoolExecutor(2) as pool:assert list(pool.map(send,range(2)))==[200,200]
    with Session() as db:assert db.scalar(select(func.count()).select_from(MakerEarning))==1

def test_ceramics_saved_for_specialist_not_stitch_compilation(client,user):
    response=client.post('/api/v1/projects',data={'title':'A chipped vase','category':'ceramic'},files={'image':('vase.jpg',photo(),'image/jpeg')})
    assert response.status_code==201 and response.json()['category']=='ceramic'
    pid=response.json()['id']
    with Session.begin() as db:
        p=db.get(__import__('kintsugi.models',fromlist=['Project']).Project,pid);p.status='needs_review';p.revision=1
    assert client.post('/api/v1/projects/'+pid+'/compile',json={'style':'branch','confirmed':True,'revision':1}).status_code==422

def test_shared_design_is_snapshot_not_mutable_project(network):
    from conftest import ready
    n=network;p=ready(n['customer'],seed=42)
    response=n['customer'].post('/api/v1/network/requests',json={'project_id':p['id'],'maker_id':n['profile']['id'],'brief':'Please execute this exact branching repair design.','consent_to_share':True})
    assert response.status_code==201,response.text
    service=response.json();assert service['design']['name']==p['plan']['name']
    assert 'pdf_key' not in service['design']
    n['customer'].post('/api/v1/projects/'+p['id']+'/analyze',json={'box':[.2,.2,.7,.7],'width_mm':40})
    shared=n['maker'].get('/api/v1/network/requests/'+service['id']+'/pattern.pdf')
    assert shared.status_code==200 and shared.content.startswith(b'%PDF')

def test_diy_progress_is_shared_on_maker_handoff(network):
    from conftest import ready
    n=network;p=ready(n['customer'],seed=44)
    n['customer'].post('/api/v1/projects/'+p['id']+'/tutorial',json={'completed':[0,1,2]})
    response=n['customer'].post('/api/v1/network/requests',json={'project_id':p['id'],'maker_id':n['profile']['id'],'brief':'I completed the first three steps and need help stitching.','consent_to_share':True})
    assert response.status_code==201,response.text
    assert response.json()['design']['tutorial_completed_steps']==[0,1,2]
    assert response.json()['design']['has_pattern'] is True
