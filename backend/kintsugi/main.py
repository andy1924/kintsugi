import hashlib
import logging
import re
import time
import uuid
import tempfile
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update, func, text
from sqlalchemy.exc import IntegrityError
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from . import config
from . import firebase_outbox
from .db import get_db, Session
from .models import User, LoginSession, Project, Job, Completion, WorkerHeartbeat
from .auth import current_user, origin_check, rate_limit, issue_session, hasher, digest, csrf, COOKIE, client_address
from .storage import store
from .imaging import normalize
from .network import router as network_router, lock_account

log=logging.getLogger('kintsugi.api')

@asynccontextmanager
async def lifespan(app):
    if len(config.SECRET)<32:raise RuntimeError('Set KINTSUGI_SECRET to a random secret of at least 32 characters. Run scripts/init_dev.py.')
    yield

app=FastAPI(title='Kintsugi API',version='1.0.0',lifespan=lifespan)
app.include_router(network_router)
from .firebase_auth import router as firebase_auth_router
from .firebase_cloud import router as firebase_cloud_router
app.include_router(firebase_auth_router)
app.include_router(firebase_cloud_router)
from .generations import router as generation_router, GenerationLimit, generation_for
app.include_router(generation_router)

@app.middleware('http')
async def request_metadata(request,call_next):
    request_id=uuid.uuid4().hex
    start=time.monotonic()
    try:
        length=int(request.headers.get('content-length','0'))
    except ValueError:
        return JSONResponse({'detail':'Invalid content length.'},status_code=400)
    if length>config.MAX_BYTES+128_000:
        return JSONResponse({'detail':'Upload is too large. Maximum photo size is 12 MB.'},status_code=413)
    response=await call_next(request)
    response.headers['X-Request-ID']=request_id
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store'
    log.info('%s %s %s %.3fs request_id=%s',request.method,request.url.path,response.status_code,time.monotonic()-start,request_id)
    return response

class StreamLimit:
    """Bound request bytes before multipart parsing; spool large bodies to disk."""
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] in ('GET','HEAD','OPTIONS'):
            return await self.app(scope,receive,send)
        limit=config.MAX_BYTES+128_000
        headers=dict(scope.get('headers',[]))
        try:length=int(headers.get(b'content-length',b'0'))
        except ValueError:
            return await JSONResponse({'detail':'Invalid content length.'},400)(scope,receive,send)
        if length>limit:
            return await JSONResponse({'detail':'Upload is too large. Maximum photo size is 12 MB.'},413)(scope,receive,send)
        with tempfile.SpooledTemporaryFile(max_size=1024*1024) as body:
            total=0
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return
                chunk=message.get('body',b'');total+=len(chunk)
                if total>limit:
                    return await JSONResponse({'detail':'Upload is too large. Maximum photo size is 12 MB.'},413)(scope,receive,send)
                body.write(chunk)
                if not message.get('more_body',False):break
            body.seek(0);finished=False
            async def replay():
                nonlocal finished
                if finished:return await receive()
                chunk=body.read(65536);more=body.tell()<total
                if not more:finished=True
                return {'type':'http.request','body':chunk,'more_body':more}
            await self.app(scope,replay,send)
app.add_middleware(StreamLimit)
app.add_middleware(CORSMiddleware,allow_origins=list(config.ORIGINS),allow_credentials=True,allow_methods=['GET','POST','PUT','OPTIONS'],allow_headers=['Content-Type','X-CSRF-Token'])

class Credentials(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=10,max_length=128)
    @field_validator('email')
    @classmethod
    def valid_email(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Enter a valid email address.')
        return value

class Registration(Credentials):
    name:str=Field(min_length=1,max_length=80)
    @field_validator('name')
    @classmethod
    def name_not_blank(cls,value):
        if not value.strip():raise ValueError('Name is required.')
        return value.strip()

class AnalysisInput(BaseModel):
    box:list[float] | None=Field(default=None,min_length=4,max_length=4)
    width_mm:float | None=Field(default=None,ge=3,le=150,allow_inf_nan=False)
    fabric:Literal['Denim','Cotton','Linen','Knit','Other'] | None=None
    memory:str=Field(default='',max_length=500)
    @field_validator('box')
    @classmethod
    def valid_box(cls,box):
        if box is None:return box
        if not all(0.005<=v<=.995 for v in box) or box[2]-box[0]<.015 or box[3]-box[1]<.015:raise ValueError('Mark a non-empty area inside the photo.')
        return box

class TutorialInput(BaseModel):
    completed:list[int]=Field(max_length=6)
    @field_validator('completed')
    @classmethod
    def steps(cls,value):
        if any(v<0 or v>5 for v in value):raise ValueError('Tutorial steps must be between 0 and 5.')
        return sorted(set(value))

class CompileInput(BaseModel):
    style:Literal['sashiko','branch','constellation','waves']='sashiko'
    revision:int=Field(ge=1)
    confirmed:Literal[True]

async def photo(upload):
    data=await upload.read(config.MAX_BYTES+1)
    await upload.close()
    try:return await run_in_threadpool(normalize,data)
    except ValueError as exc:raise HTTPException(422,str(exc))

def owned(db,user,project_id,lock=False):
    stmt=select(Project).where(Project.id==project_id,Project.user_id==user.id)
    if lock:stmt=stmt.with_for_update()
    project=db.scalar(stmt)
    if not project:raise HTTPException(404,'Repair not found.')
    return project

def project_json(project):
    plan=None if not project.plan else {k:v for k,v in project.plan.items() if k not in ('pdf_key','svg_key')}
    preview=None if not project.preview else {k:v for k,v in project.preview.items() if k!='image_key'}
    if preview:preview['revision']=project.preview_revision
    return {'preview':preview,'id':project.id,'title':project.title,'category':project.category,'status':project.status,'width':project.width,'height':project.height,'revision':project.revision,'tutorial_steps':project.tutorial_steps,'settings':project.settings,'analysis':project.analysis,'plan':plan,'error':project.error,'created_at':project.created_at,'completed_at':project.completed_at}

@app.get('/api/v1/health')
def health(db=Depends(get_db)):
    db.execute(text('SELECT 1'))
    recent=db.scalar(select(func.max(WorkerHeartbeat.updated_at)))
    alive=bool(recent and recent>time.time()-120)
    return {'status':'ok','service_fee_bps':config.SERVICE_FEE_BPS,'worker_available':alive,'segmentation':config.MODEL,'damage_analysis':config.analysis_provider(),'openai_configured':bool(config.OPENAI_API_KEY),'creative_preview_available':config.preview_enabled(),'generation':'geometry-driven vector compiler','version':'1.0.0'}

@app.post('/api/v1/auth/register',status_code=201)
def register(body:Registration,request:Request,response:Response,db=Depends(get_db)):
    origin_check(request);rate_limit(db,'register:'+digest(client_address(request)),10)
    user=User(email=body.email,name=body.name,password=hasher.hash(body.password));db.add(user)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'An account with this email already exists.')
    return issue_session(db,user,response)

@app.post('/api/v1/auth/login')
def login(body:Credentials,request:Request,response:Response,db=Depends(get_db)):
    origin_check(request);rate_limit(db,'login:'+digest(client_address(request)))
    rate_limit(db,'email:'+digest(body.email))
    user=db.scalar(select(User).where(User.email==body.email))
    valid=False
    # Equal-cost password check for missing accounts as well as incorrect passwords.
    encoded=user.password if user else '$argon2id$v=19$m=32768,t=2,p=2$ZHVtbXlzYWx0MTIzNDU2Nw$qdA9e2m2lHrlJPtZQWK8K23ZMBgXL5P5uHnEZh9cLvU'
    try:valid=hasher.verify(encoded,body.password)
    except (VerifyMismatchError,VerificationError,InvalidHashError):pass
    if not user or not valid:raise HTTPException(401,'Email or password is incorrect.')
    return issue_session(db,user,response)

@app.get('/api/v1/auth/me')
def me(request:Request,user=Depends(current_user)):
    return {'user':{'id':user.id,'name':user.name,'email':user.email,'role':user.role},'csrf':csrf(request.cookies[COOKIE])}

@app.post('/api/v1/auth/logout',status_code=204)
def logout(request:Request,response:Response,user=Depends(current_user),db=Depends(get_db)):
    token=db.get(LoginSession,digest(request.cookies[COOKIE]));db.delete(token);db.commit();response.delete_cookie(COOKIE,path='/')

@app.get('/api/v1/projects')
def projects(user=Depends(current_user),db=Depends(get_db),offset:int=0,limit:int=25):
    limit=max(1,min(limit,50));offset=max(0,offset)
    return [project_json(p) for p in db.scalars(select(Project).where(Project.user_id==user.id).order_by(Project.created_at.desc()).offset(offset).limit(limit))]

@app.post('/api/v1/projects',status_code=201)
async def create_project(image:UploadFile=File(...),title:str=Form('My repair',min_length=1,max_length=100),category:Literal['textile','ceramic']=Form('textile'),user=Depends(current_user),db=Depends(get_db)):
    rate_limit(db,'upload:'+user.id,15,3600)
    if db.scalar(select(func.count()).select_from(Project).where(Project.user_id==user.id))>=200:raise HTTPException(409,'Your studio is full. You can save up to 200 repairs.')
    data,w,h,sha,phash=await photo(image)
    key=await run_in_threadpool(store.put,data,'jpg')
    project=Project(user_id=user.id,title=title.strip() or 'My repair',category=category,image_key=key,image_hash=sha,image_phash=phash,width=w,height=h)
    db.add(project)
    try:db.commit()
    except Exception:
        store.delete(key);raise
    return project_json(project)

@app.get('/api/v1/projects/{project_id}')
def get_project(project_id:str,user=Depends(current_user),db=Depends(get_db)):
    return project_json(owned(db,user,project_id))

@app.get('/api/v1/projects/{project_id}/image')
def image(project_id:str,user=Depends(current_user),db=Depends(get_db)):
    return Response(store.get(owned(db,user,project_id).image_key),media_type='image/jpeg')

@app.post('/api/v1/projects/{project_id}/analyze',status_code=202)
def analyze(project_id:str,body:AnalysisInput,user=Depends(current_user),db=Depends(get_db)):
    rate_limit(db,'analyze:'+user.id,20,3600)
    lock_account(db,user)
    project=owned(db,user,project_id,True)
    if project.status in ('analyzing','compiling','completed'):raise HTTPException(409,'This repair cannot be edited while processing or after completion.')
    if body.box is not None:
        x0,y0,x1,y1=body.box
        actual_h=(y1-y0)*project.height/((x1-x0)*project.width)*(body.width_mm or 35)
        if actual_h>400:raise HTTPException(422,'The selected repair is taller than 400 mm. Split it into smaller repairs.')
        if (x1-x0)*project.width<5 or (y1-y0)*project.height<5:raise HTTPException(422,'Mark a larger area so the damage can be analysed.')
    from .models import RepairGeneration
    db.execute(update(RepairGeneration).where(RepairGeneration.project_id==project.id,RepairGeneration.state.in_(['queued','running'])).values(state='cancelled',error='Superseded by a new damage assessment.'))
    db.execute(update(Job).where(Job.project_id==project.id,Job.kind=='preview',Job.state.in_(['queued','running'])).values(state='cancelled',lease_until=0))
    project.settings=body.model_dump();project.revision+=1;project.analysis=None;project.plan=None;project.preview=None;project.preview_revision+=1;project.tutorial_steps=[];project.error=None;project.status='analyzing';project.updated_at=time.time()
    db.add(Job(project_id=project.id,revision=project.revision,kind='analyze'));db.commit()
    return project_json(project)

class PreviewInput(BaseModel):
    request_id:uuid.UUID|None=None
    style:Literal['sashiko','branch','constellation','waves']|None=None

@app.post('/api/v1/projects/{project_id}/preview',status_code=202)
def refresh_preview(project_id:str,body:PreviewInput,user=Depends(current_user),db=Depends(get_db)):
    if not config.preview_enabled():raise HTTPException(503,'Creative previews need a configured server API key and image model access.')
    lock_account(db,user);project=owned(db,user,project_id,True)
    if body.request_id:
        from .models import RepairGeneration
        prior=db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==project.id,RepairGeneration.request_key==str(body.request_id)))
        if prior:
            if prior.requested_style!=body.style:raise HTTPException(409,'This request ID was already used for a different design direction.')
            if prior.version!=project.preview_revision:raise HTTPException(409,f'This request already created generation {prior.version}. Retrieve it from generation history.')
            return project_json(project)
    rate_limit(db,'preview:'+user.id,6,3600)
    db.expire_all()
    # rate_limit commits its counter. Reacquire the account/project locks afterwards.
    lock_account(db,user);project=owned(db,user,project_id,True)
    if project.category!='textile' or project.status not in ('needs_review','ready'):
        raise HTTPException(409,'Finish the damage assessment before generating a repair preview.')
    if not project.analysis or project.analysis.get('requires_manual_area') or project.analysis.get('damage_found') is False:
        raise HTTPException(422,'Adjust the damage area or upload a clearer close-up first.')
    if body.request_id:
        prior=db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==project.id,RepairGeneration.request_key==str(body.request_id)))
        if prior:
            if prior.requested_style!=body.style or prior.version!=project.preview_revision:raise HTTPException(409,'This request ID has already been used. Check generation history.')
            return project_json(project)
    if project.preview and project.preview.get('state') in ('queued','running'):
        raise HTTPException(409,'A preview is already being created for this piece.')
    from .creative import queue_preview
    try:queue_preview(db,project,body.style,str(body.request_id) if body.request_id else None)
    except GenerationLimit as error:raise HTTPException(429,str(error),headers={'Retry-After':str(error.retry_after)}) from None
    db.commit();return project_json(project)

@app.get('/api/v1/projects/{project_id}/preview.png')
def preview_image(project_id:str,user=Depends(current_user),db=Depends(get_db)):
    project=owned(db,user,project_id)
    if not project.preview or project.preview.get('state')!='ready':raise HTTPException(404,'Preview is not ready yet.')
    return Response(store.get(project.preview['image_key']),media_type='image/png')

@app.post('/api/v1/projects/{project_id}/compile',status_code=202)
def compile_project(project_id:str,body:CompileInput,user=Depends(current_user),db=Depends(get_db)):
    lock_account(db,user)
    project=owned(db,user,project_id,True)
    if project.status not in ('needs_review','ready') or project.revision!=body.revision:raise HTTPException(409,'Review the latest analysis before creating a pattern.')
    if project.status=='ready' and project.plan and project.plan.get('design_revision')==project.preview_revision:
        raise HTTPException(409,'This design already has a pattern. Refresh its concept to create another.')
    if project.category=='ceramic':raise HTTPException(422,'Ceramics need a specialist assessment. Request help from a maker instead of a stitch pattern.')
    if not project.analysis:raise HTTPException(409,'Analyse the damage before creating a pattern.')
    if project.analysis.get('requires_manual_area'):raise HTTPException(422,'No clear damage was detected. Adjust the damage area or upload a clearer photo first.')
    if project.preview and project.preview.get('state') in ('queued','running'):raise HTTPException(409,'Wait for the creative preview before preparing its pattern.')
    preview_style=project.preview.get('style') if project.preview and project.preview.get('state')=='ready' else None
    if preview_style and preview_style!=body.style and project.preview.get('provider')=='openai':raise HTTPException(409,'Choose the preview’s design or generate a preview in your new direction first.')
    project.settings={**project.settings,'style':body.style};project.status='compiling';project.updated_at=time.time();project.tutorial_steps=[]
    job=db.scalar(select(Job).where(Job.project_id==project.id,Job.revision==project.revision,Job.kind=='compile'))
    if job:
        job.state='queued';job.attempts=0;job.run_after=time.time();job.lock_token=None;job.lease_until=0
    else:db.add(Job(project_id=project.id,revision=project.revision,kind='compile'))
    db.commit();return project_json(project)

@app.post('/api/v1/projects/{project_id}/tutorial')
def tutorial_progress(project_id:str,body:TutorialInput,user=Depends(current_user),db=Depends(get_db)):
    lock_account(db,user);project=owned(db,user,project_id,True)
    if project.category=='textile' and not project.plan:raise HTTPException(409,'Create a repair pattern before saving its guided steps.')
    project.tutorial_steps=body.completed;project.updated_at=time.time();db.commit()
    return project_json(project)

@app.get('/api/v1/projects/{project_id}/pattern.{kind}')
def pattern(project_id:str,kind:Literal['pdf','svg'],user=Depends(current_user),db=Depends(get_db)):
    project=owned(db,user,project_id)
    if not project.plan or project.status not in ('ready','completed'):raise HTTPException(409,'Your pattern is not ready yet.')
    return Response(store.get(project.plan[kind+'_key']),media_type='application/pdf' if kind=='pdf' else 'image/svg+xml',headers={'Content-Disposition':f'attachment; filename="kintsugi-{project.id[:8]}.{kind}"','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; sandbox"})

@app.post('/api/v1/projects/{project_id}/complete')
async def complete(project_id:str,image:UploadFile=File(...),user=Depends(current_user),db=Depends(get_db)):
    rate_limit(db,'completion:'+user.id,10,3600)
    lock_account(db,user)
    project=owned(db,user,project_id,True)
    if project.status=='completed':return {'project':project_json(project),'recorded':False}
    if project.status!='ready' and not (project.category=='ceramic' and len(project.tutorial_steps)==6):raise HTTPException(409,'Finish your repair guide before submitting an after-photo.')
    result=await photo(image)
    if result[3]==project.image_hash:raise HTTPException(422,'Use a new photo of the finished repair.')
    if db.scalar(select(Completion).where(Completion.image_hash==result[3])):raise HTTPException(409,'This photo is already attached to a completed repair.')
    key=await run_in_threadpool(store.put,result[0],'jpg');now=time.time()
    db.add(Completion(project_id=project.id,user_id=user.id,image_key=key,image_hash=result[3],image_phash=result[4],created_at=now))
    project.status='completed';project.completed_at=now;project.updated_at=now
    try:db.commit()
    except IntegrityError:
        db.rollback();store.delete(key);raise HTTPException(409,'This completion has already been recorded.')
    return {'project':project_json(project),'recorded':True}
