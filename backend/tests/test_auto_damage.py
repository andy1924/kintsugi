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


def test_tear_wins_over_small_marks_and_bottom_banner():
    image=Image.new('RGB',(480,360),(132,141,147))
    draw=ImageDraw.Draw(image)
    draw.ellipse((135,112,310,165),fill=(22,24,26))
    for x in range(140,305,12):
        draw.line((x,108,x+8,121),fill=(223,220,204),width=3)
    for x,y in [(35,175),(410,80),(100,260)]:
        draw.ellipse((x,y,x+10,y+10),outline='white',width=2)
    draw.rectangle((0,338,480,360),fill=(30,100,180))
    box,state=detect_damage(np.array(image))
    assert state=='suggested'
    assert box[0]<135/480 and box[2]>310/480
    assert box[1]<112/360 and box[3]>165/360
    assert box[3]<.8


def test_proposal_precedes_diy_and_matches_printed_guide(client,user):
    from kintsugi.storage import store
    from kintsugi.creative import repair_rectangle
    p=upload(client);url=f'/api/v1/projects/{p["id"]}'
    client.post(url+'/analyze',json={}).raise_for_status()
    assert run_once()
    p=client.get(url).json();preview=p['preview']
    assert p['plan'] is None and preview['provider']=='local'
    assert len(preview['design']['steps'])==6
    before=Image.open(io.BytesIO(client.get(url+'/image').content)).convert('RGB')
    after=Image.open(io.BytesIO(client.get(url+'/preview.png').content)).convert('RGB')
    x0,y0,x1,y1=repair_rectangle(before,p['analysis'])
    changed=np.any(np.array(before)!=np.array(after),axis=2)
    outside=changed.copy();outside[y0:y1,x0:x1]=False
    assert changed.any() and not outside.any()
    client.post(url+'/compile',json={'revision':p['revision'],'style':preview['style'],'confirmed':True}).raise_for_status()
    assert run_once()
    plan=client.get(url).json()['plan']
    assert plan['name']==preview['design']['name']
    assert plan['creative_steps']==preview['design']['steps']
    assert plan['lines']==[[[round(x*plan['width_mm'],2),round(y*plan['height_mm'],2)] for x,y in path] for path in preview['design']['paths']]


def test_uncertain_photo_does_not_invent_a_repair(client,user):
    stream=io.BytesIO();Image.new('RGB',(320,260),'#777777').save(stream,'PNG')
    p=client.post('/api/v1/projects',data={'title':'Unclear piece'},files={'image':('plain.png',stream.getvalue(),'image/png')}).json()
    url=f'/api/v1/projects/{p["id"]}'
    client.post(url+'/analyze',json={}).raise_for_status();assert run_once()
    p=client.get(url).json()
    assert p['analysis']['requires_manual_area'] and not p['preview']
    assert client.post(url+'/compile',json={'revision':p['revision'],'confirmed':True}).status_code==422
