"""Atomic generation admission, history and cancellation. No provider secrets leave the server."""
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from . import config
from .auth import current_user
from .db import get_db
from .models import Project, RepairGeneration, Job, RateBucket
from .storage import store

router=APIRouter(prefix='/api/v1',tags=['generation operations'])


class GenerationLimit(Exception):
    def __init__(self,message):
        super().__init__(message)
        self.retry_after=max(1,int(86400-time.time()%86400))


def _key(user_id=None):
    return f'generation:{user_id or "global"}:{int(time.time()//86400)}'


def reserve(db,user_id):
    insert=sqlite_insert if db.bind.dialect.name=='sqlite' else pg_insert
    for key,limit,message in [(_key(user_id),config.GENERATION_USER_DAILY_LIMIT,'Your daily creative generation allowance is used. Your saved repairs are still available.'),
                              (_key(),config.GENERATION_GLOBAL_DAILY_LIMIT,'The studio’s daily image generation capacity is used. Your assessment is saved; try again tomorrow.')]:
        allowed=db.execute(insert(RateBucket).values(key=key,hits=1,expires_at=time.time()+86400)
            .on_conflict_do_update(index_elements=['key'],set_={'hits':RateBucket.hits+1},where=RateBucket.hits<limit)
            .returning(RateBucket.hits)).scalar_one_or_none()
        if allowed is None:raise GenerationLimit(message)


def generation_for(db,project_id,version):
    return db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==project_id,RepairGeneration.version==version))


def safe_generation(g):
    return {'id':g.id,'version':g.version,'source_revision':g.source_revision,'state':g.state,'stage':g.stage,
            'design':g.design,'has_image':bool(g.image_key),'error':g.error,'created_at':g.created_at,'updated_at':g.updated_at}


def owner_project(db,user,project_id,lock=False):
    query=select(Project).where(Project.id==project_id,Project.user_id==user.id)
    if lock:query=query.with_for_update()
    project=db.scalar(query)
    if not project:raise HTTPException(404,'Repair not found.')
    return project


@router.get('/generation-usage')
def usage(user=Depends(current_user),db=Depends(get_db)):
    bucket=db.get(RateBucket,_key(user.id));used=bucket.hits if bucket else 0
    return {'used':used,'limit':config.GENERATION_USER_DAILY_LIMIT,'remaining':max(0,config.GENERATION_USER_DAILY_LIMIT-used),
            'resets_at':(int(time.time()//86400)+1)*86400,'unit':'generation attempts'}


@router.get('/projects/{project_id}/generations')
def history(project_id:str,user=Depends(current_user),db=Depends(get_db),offset:int=0):
    owner_project(db,user,project_id)
    return [safe_generation(g) for g in db.scalars(select(RepairGeneration).where(RepairGeneration.project_id==project_id).order_by(RepairGeneration.version.desc()).offset(max(0,offset)).limit(50))]


@router.get('/projects/{project_id}/generations/{version}/image')
def historical_image(project_id:str,version:int,user=Depends(current_user),db=Depends(get_db)):
    from fastapi import Response
    owner_project(db,user,project_id);generation=generation_for(db,project_id,version)
    if not generation or generation.state!='ready' or not generation.image_key:raise HTTPException(404,'This generation has no finished image.')
    return Response(store.get(generation.image_key),media_type='image/png')


@router.post('/projects/{project_id}/generations/{version}/cancel')
def cancel(project_id:str,version:int,user=Depends(current_user),db=Depends(get_db)):
    # Match API lock order: user, project, generation/job.
    from .network import lock_account
    lock_account(db,user);project=owner_project(db,user,project_id,True)
    generation=generation_for(db,project_id,version)
    if not generation:raise HTTPException(404,'Generation not found.')
    if generation.state=='cancelled':return safe_generation(generation)
    if generation.state not in ('queued','running'):raise HTTPException(409,'This generation has already finished.')
    generation.state='cancelled';generation.error='Generation cancelled. A provider request already in progress may still incur usage.';generation.updated_at=time.time()
    db.execute(update(Job).where(Job.project_id==project_id,Job.kind=='preview',Job.revision==version,Job.state.in_(['queued','running'])).values(state='cancelled',lease_until=0))
    if project.preview_revision==version:
        project.preview={**(project.preview or {}),'state':'cancelled','error':generation.error}
    db.commit();return safe_generation(generation)


@router.get('/projects/{project_id}/jobs')
def project_jobs(project_id:str,user=Depends(current_user),db=Depends(get_db)):
    owner_project(db,user,project_id)
    return [{'id':j.id,'kind':j.kind,'revision':j.revision,'state':j.state,'attempts':j.attempts,'error':j.error,'retry_at':j.run_after if j.state=='queued' else None}
            for j in db.scalars(select(Job).where(Job.project_id==project_id).order_by(Job.run_after.desc()).limit(100))]


@router.get('/ops/queue')
def queue_status(user=Depends(current_user),db=Depends(get_db)):
    from .models import WorkerHeartbeat
    from .network import operator
    operator(user)
    counts=db.execute(select(Job.kind,Job.state,func.count()).group_by(Job.kind,Job.state)).all()
    active=db.scalars(select(WorkerHeartbeat).where(WorkerHeartbeat.updated_at>time.time()-120)).all()
    return {'jobs':[{'kind':kind,'state':state,'count':count} for kind,state,count in counts],
            'workers':[{'id':worker.id,'queues':worker.queues,'model':worker.model,'last_seen':worker.updated_at} for worker in active],
            'recent_failures':[{'project_id':g.project_id,'version':g.version,'stage':g.stage,'error':g.error} for g in db.scalars(select(RepairGeneration).where(RepairGeneration.state=='failed').order_by(RepairGeneration.updated_at.desc()).limit(30))]}
