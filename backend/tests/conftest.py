import os
import sys
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
_tmp=tempfile.TemporaryDirectory(prefix='kintsugi-tests-')
os.environ['DATA_DIR']=_tmp.name
os.environ['DATABASE_URL']='sqlite:///'+_tmp.name+'/test.db'
os.environ['KINTSUGI_SECRET']='test-only-secret-never-use-for-deployment-123456789'
os.environ['SEGMENTATION_MODEL']='grabcut'
os.environ['DAMAGE_ANALYSIS_PROVIDER']='local'  # Tests never call a paid external API.
import io
import numpy as np
from PIL import Image,ImageDraw
import pytest
from fastapi.testclient import TestClient
from kintsugi.main import app
from kintsugi.db import Base,engine

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    yield

@pytest.fixture
def client():
    with TestClient(app) as client:yield client

def account(client,email='mender@example.com'):
    response=client.post('/api/v1/auth/register',json={'email':email,'password':'my-secure-test-pass','name':'Mender'})
    assert response.status_code==201,response.text
    client.headers['X-CSRF-Token']=response.json()['csrf']
    return response.json()['user']

@pytest.fixture
def user(client):return account(client)

def photo(seed=1):
    rng=np.random.default_rng(seed)
    pixels=rng.integers(40,160,(260,320,3),dtype=np.uint8)
    image=Image.fromarray(pixels)
    draw=ImageDraw.Draw(image);draw.polygon([(130,70),(170,90),(155,170),(125,150)],fill=(10,10,10))
    stream=io.BytesIO();image.save(stream,'JPEG');return stream.getvalue()

def upload(client,seed=1):
    response=client.post('/api/v1/projects',data={'title':'Travel jacket'},files={'image':('photo.jpg',photo(seed),'image/jpeg')})
    assert response.status_code==201,response.text
    return response.json()

def ready(client,seed=1,style='branch'):
    from kintsugi.worker import run_once
    p=upload(client,seed)
    response=client.post('/api/v1/projects/'+p['id']+'/analyze',json={'box':[.3,.2,.65,.75],'width_mm':35,'fabric':'Denim','memory':'Everywhere with me.'})
    assert response.status_code==202,response.text
    assert run_once()
    p=client.get('/api/v1/projects/'+p['id']).json()
    assert p['status']=='needs_review',p
    response=client.post('/api/v1/projects/'+p['id']+'/compile',json={'revision':p['revision'],'style':style,'confirmed':True})
    assert response.status_code==202,response.text
    assert run_once()
    p=client.get('/api/v1/projects/'+p['id']).json()
    assert p['status']=='ready',p
    return p
