import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from conftest import account
from kintsugi.main import app
from kintsugi.db import Session
from kintsugi.models import Maker, User
from test_network import APPLICATION


def seed_maker(db, latitude, longitude, *, status='approved', accepting=True, consent=True, categories=None, name='Workroom'):
    user=User(email=f'{latitude}-{longitude}-{name}@example.com',name='Maker',password='unused')
    db.add(user);db.flush()
    maker=Maker(user_id=user.id,name=name,about='Independent mending workroom for clothes and decorative pieces.',city='Pune',categories=categories or ['textile'],address={'line1':'PRIVATE ADDRESS','phone':'PRIVATE PHONE'},latitude=latitude,longitude=longitude,status=status,accepting_work=accepting,consent_to_list=consent)
    db.add(maker);db.flush()
    return maker.id


def test_nearby_filters_and_distance_order(client):
    with Session.begin() as db:
        far=seed_maker(db,18.8,73.86,name='Further')
        near=seed_maker(db,18.52,73.86,name='Nearby')
        seed_maker(db,19.5,73.86,name='Outside radius')
        seed_maker(db,18.53,73.86,status='pending',name='Pending')
        seed_maker(db,18.54,73.86,accepting=False,name='Paused')
        seed_maker(db,18.55,73.86,consent=False,name='Private')
        seed_maker(db,None,None,name='No pin')
        ceramic=seed_maker(db,18.56,73.86,categories=['ceramic'],name='Ceramic')
    url='/api/v1/network/makers?latitude=18.52&longitude=73.86&radius_km=50&category=textile'
    rows=client.get(url).json()
    assert [m['id'] for m in rows]==[near,far]
    assert rows[0]['distance_km']==0
    assert 30 < rows[1]['distance_km'] < 32
    assert all('address' not in m and 'phone' not in str(m) for m in rows)
    assert [m['id'] for m in client.get(url+'&offset=1').json()]==[far]
    assert [m['id'] for m in client.get(url.replace('textile','ceramic')).json()]==[ceramic]
    all_makers=client.get('/api/v1/network/makers').json()
    assert len(all_makers)==5
    assert any(m['public_location'] is None for m in all_makers)


@pytest.mark.parametrize('query',[
    'latitude=10','longitude=10','latitude=nan&longitude=10',
    'latitude=91&longitude=10','latitude=10&longitude=181',
    'latitude=10&longitude=10&radius_km=201','offset=-1',
])
def test_invalid_nearby_search(client,query):
    assert client.get('/api/v1/network/makers?'+query).status_code==422


def test_opt_in_location_rounding_removal_and_ownership(client,user):
    result=client.post('/api/v1/network/profile',json={**APPLICATION,'public_location':{'latitude':18.52345,'longitude':73.85678}})
    assert result.status_code==201,result.text
    assert result.json()['public_location']=={'latitude':18.52,'longitude':73.86}
    assert 'address' not in result.json()
    assert client.get('/api/v1/network/makers?latitude=18.52&longitude=73.86').json()==[]
    other=TestClient(app)
    account(other,'other@example.com')
    assert other.put('/api/v1/network/profile/location',json={'public_location':None}).status_code==404
    assert client.put('/api/v1/network/profile/location',json={'public_location':{'latitude':-91,'longitude':0}}).status_code==422
    with Session.begin() as db:
        db.execute(update(Maker).where(Maker.user_id==user['id']).values(status='approved'))
    assert len(client.get('/api/v1/network/makers?latitude=18.52&longitude=73.86').json())==1
    assert client.put('/api/v1/network/profile/location',json={'public_location':None}).status_code==200
    assert client.get('/api/v1/network/makers?latitude=18.52&longitude=73.86').json()==[]
    assert len(client.get('/api/v1/network/makers').json())==1
    other.close()


def test_category_filter_before_pagination(client):
    with Session.begin() as db:
        for index in range(51):seed_maker(db,18.52,73.86,categories=['ceramic'],name=f'Ceramic{index}')
        textile=seed_maker(db,18.53,73.86,categories=['ceramic','textile'],name='Textile')
    assert [m['id'] for m in client.get('/api/v1/network/makers?category=textile').json()]==[textile]
    assert [m['id'] for m in client.get('/api/v1/network/makers?category=textile&latitude=18.52&longitude=73.86').json()]==[textile]


def test_dateline_and_pole_search(client):
    with Session.begin() as db:
        across=seed_maker(db,0,-179.99,name='Across dateline')
        pole=seed_maker(db,90,0,name='Pole')
    assert [m['id'] for m in client.get('/api/v1/network/makers?latitude=0&longitude=179.99&radius_km=25').json()]==[across]
    assert [m['id'] for m in client.get('/api/v1/network/makers?latitude=90&longitude=180&radius_km=25').json()]==[pole]


def test_tile_config_can_be_switched_without_rebuild(client,monkeypatch):
    monkeypatch.setenv('OSM_TILE_URL','https://tiles.example.org/{z}/{x}/{y}.png')
    assert client.get('/api/v1/network/map-config').json()['tile_url']=='https://tiles.example.org/{z}/{x}/{y}.png'
def test_public_location_update_cors_preflight(client):
    from kintsugi import config
    origin=sorted(config.ORIGINS)[0]
    response=client.options('/api/v1/network/profile/location',headers={
        'Origin':origin,'Access-Control-Request-Method':'PUT',
        'Access-Control-Request-Headers':'Content-Type,X-CSRF-Token',
    })
    assert response.status_code==200
    assert response.headers['access-control-allow-origin']==origin
    assert 'PUT' in response.headers['access-control-allow-methods']
