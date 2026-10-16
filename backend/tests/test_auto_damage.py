import io
import numpy as np
from PIL import Image, ImageDraw
from conftest import upload
from kintsugi.imaging import detect_damage, segment
from kintsugi.worker import run_once


def test_detect_local_defect_and_uncertain_photo():
    image=Image.new('RGB',(320,260),(120,140,160))
    ImageDraw.Draw(image).ellipse((140,100,180,150),fill=(10,10,10))
    box,confidence=detect_damage(np.array(image))
    assert confidence=='suggested'
    assert box[0]<140/320 and box[2]>180/320
    assert box[1]<100/260 and box[3]>150/260
    assert detect_damage(np.full((260,320,3),120,np.uint8))[1]=='uncertain'


def test_automatic_analysis_and_optional_correction(client,user):
    project=upload(client)
    url=f'/api/v1/projects/{project["id"]}'
    assert client.post(url+'/analyze',json={}).status_code==202
    assert run_once()
    project=client.get(url).json()
    assert project['status']=='needs_review'
    analysis=project['analysis']
    assert analysis['scale_source']=='suggested'
    assert analysis['damage_width_px']>0 and analysis['outlines']
    assert any('not a measured' in note for note in analysis['warnings'])
    assert client.post(url+'/compile',json={'revision':project['revision'],'confirmed':True}).status_code==202
    assert run_once()
    project=client.get(url).json()
    assert project['plan']['scale_source']=='suggested'
    assert 'Suggested template size' in project['plan']['instructions'][0]
    assert client.post(url+'/analyze',json={'box':[.3,.2,.65,.75],'width_mm':42,'fabric':'Cotton'}).status_code==202
    assert run_once()
    project=client.get(url).json()
    assert project['analysis']['width_mm']==42
    assert project['analysis']['scale_source']=='user'
    assert project['analysis']['detection']=='user_adjusted'


def test_explicit_null_uses_auto_detection(client,user):
    project=upload(client)
    assert client.post(f'/api/v1/projects/{project["id"]}/analyze',json={'box':None,'width_mm':None}).status_code==202
    assert run_once()
    assert client.get(f'/api/v1/projects/{project["id"]}').json()['status']=='needs_review'
