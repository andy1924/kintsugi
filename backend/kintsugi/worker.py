"""Durable leased jobs. Run separately from the HTTP process; scale on PostgreSQL."""
import logging
import signal
import threading
import time
import uuid
from sqlalchemy import select, update, or_, and_
from .db import Session, transaction
from .models import Job, Project, WorkerHeartbeat, RepairGeneration, User
from .storage import store
from .imaging import validate_model
from .analysis import analyze_damage
from .vision import VisionError
from .compiler import make_plan
from .creative import generate_preview, queue_preview
from . import config
from . import firebase_outbox

log=logging.getLogger('kintsugi.worker')
LEASE_SECONDS=900
running=True

def claim(kinds=None):
    kinds=kinds or config.WORKER_JOB_KINDS
    now=time.time()
    with transaction() as db:
        eligible=or_(and_(Job.state=='queued',Job.run_after<=now),and_(Job.state=='running',Job.lease_until<now,Job.kind!='preview'))
        job=db.scalar(select(Job).where(eligible,Job.attempts<3,Job.kind.in_(kinds)).order_by(Job.run_after).with_for_update(skip_locked=True).limit(1))
        if not job:return None
        token=uuid.uuid4().hex
        # Conditional update also protects single-host SQLite against competing claimers.
        got=db.execute(update(Job).where(Job.id==job.id,eligible,Job.attempts<3).values(state='running',lock_token=token,lease_until=now+LEASE_SECONDS,attempts=Job.attempts+1).returning(Job.id)).scalar_one_or_none()
        return (got,token) if got else None

def lock_project(db,project_id):
    user_id=db.scalar(select(Project.user_id).where(Project.id==project_id))
    if user_id:db.execute(update(User).where(User.id==user_id).values(name=User.name))
    return db.scalar(select(Project).where(Project.id==project_id).with_for_update())

def run_once():
    claimed=claim()
    if not claimed:return False
    job_id,token=claimed
    result=None
    local_preview=None
    try:
        with Session() as db:
            job=db.get(Job,job_id);project=db.get(Project,job.project_id)
            version=project.preview_revision if job.kind=='preview' else project.revision
            if version!=job.revision:raise VisionError('This job was superseded by a newer revision.')
            # Release the database connection before CPU inference or remote calls.
            db.expunge(job);db.expunge(project)
        if job.kind=='preview':
            with transaction() as db:
                current=db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==project.id,RepairGeneration.version==job.revision).with_for_update())
                if current and current.state not in ('queued','running'):raise VisionError('This generation was cancelled.')
                if current:current.state='running';current.updated_at=time.time()
            result=generate_preview(project)
        elif job.kind=='analyze':
            result=analyze_damage(store.get(project.image_key),project.settings)
            if not config.preview_enabled() and not result.get('requires_manual_area') and result.get('damage_found') is not False:
                from .suggestions import illustrated_preview
                local_preview=illustrated_preview(project,result)
        else:result=make_plan(project)
        with transaction() as db:
            locked=lock_project(db,job.project_id)
            owned=db.execute(update(Job).where(Job.id==job_id,Job.lock_token==token,Job.state=='running',Job.lease_until>time.time()).values(state='succeeded',lease_until=0)).rowcount
            applied=False
            if owned:
                version=(locked.preview_revision if job.kind=='preview' else locked.revision) if locked else None
                current=locked if version==job.revision else None
                if current:
                    applied=True
                    if job.kind=='preview':
                        current.preview=result
                        generation=db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==project.id,RepairGeneration.version==job.revision).with_for_update())
                        if generation:
                            generation.state='ready';generation.stage='complete';generation.design=result['design'];generation.image_key=result['image_key'];generation.updated_at=time.time()
                    elif job.kind=='analyze':
                        current.analysis=result;current.status='needs_review';current.error=None
                        if local_preview:
                            current.preview_revision+=1
                            current.preview=local_preview
                        if config.preview_enabled() and not result.get('requires_manual_area') and result.get('damage_found') is not False:
                            from .generations import GenerationLimit
                            try:queue_preview(db,current)
                            except GenerationLimit as error:current.preview={'state':'limited','error':str(error),'source_revision':current.revision}
                    else:current.plan=result;current.status='ready';current.error=None
                    current.updated_at=time.time()
            if job.kind=='preview' and not applied and result and result.get('image_key'):store.delete(result['image_key'])
            if local_preview and not applied:store.delete(local_preview['image_key'])
    except Exception as error:
        log.warning('Job %s failed (%s)',job_id,type(error).__name__)
        with transaction() as db:
            lock_project(db,job.project_id)
            job=db.get(Job,job_id)
            if job.lock_token==token and job.state=='running':
                job.error=str(error) if isinstance(error,VisionError) else 'Processing failed. Please retry with a clear photo or contact the studio.'
                permanent=isinstance(error,VisionError) and not error.retryable
                job.state='failed' if job.kind=='preview' or permanent or job.attempts>=3 else 'queued';job.run_after=time.time()+min(60,2**job.attempts);job.lease_until=0
                if job.state=='failed':
                    if job.kind=='preview':
                        current=db.scalar(select(Project).where(Project.id==job.project_id,Project.preview_revision==job.revision).with_for_update())
                        if current:current.preview={**(current.preview or {}),'state':'failed','error':job.error}
                        generation=db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==job.project_id,RepairGeneration.version==job.revision).with_for_update())
                        if generation and generation.state not in ('ready','cancelled'):
                            generation.state='failed';generation.error=job.error;generation.updated_at=time.time()
                    else:db.execute(update(Project).where(Project.id==job.project_id,Project.revision==job.revision).values(status='failed',error=job.error,updated_at=time.time()))
    return True

def reap_exhausted():
    # Same lock order as customer cancellation and publishing: account, project, job.
    with Session() as db:
        candidates=db.execute(select(Job.id,Job.project_id).where(Job.state=='running',Job.lease_until<time.time(),or_(Job.attempts>=3,Job.kind=='preview')).limit(100)).all()
    for job_id,project_id in candidates:
        with transaction() as db:
            current=lock_project(db,project_id)
            job=db.scalar(select(Job).where(Job.id==job_id).with_for_update())
            if not job or job.state!='running' or job.lease_until>=time.time() or (job.kind!='preview' and job.attempts<3):continue
            job.state='failed';job.error='The worker was interrupted repeatedly. Please retry the repair.'
            if job.kind=='preview':
                if current and current.preview_revision==job.revision:current.preview={**(current.preview or {}),'state':'failed','error':'Preview interrupted. Refresh to try a new design.'}
                generation=db.scalar(select(RepairGeneration).where(RepairGeneration.project_id==job.project_id,RepairGeneration.version==job.revision).with_for_update())
                if generation and generation.state not in ('ready','cancelled'):
                    generation.state='failed';generation.error='Preview interrupted. Refresh to try a new design.';generation.updated_at=time.time()
            elif current and current.revision==job.revision:current.status='failed';current.error=job.error

def main():
    global running
    logging.basicConfig(level=logging.INFO)
    if 'analyze' in config.WORKER_JOB_KINDS:validate_model() # Image-only workers do not load SAM/Torch.
    identity=uuid.uuid4().hex
    def stop(*_):
        global running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    from .config import MODEL
    heartbeat_stop=threading.Event()
    def heartbeat():
        while not heartbeat_stop.is_set():
            try:
                with transaction() as db:db.merge(WorkerHeartbeat(id=identity,updated_at=time.time(),model=MODEL,queues=list(config.WORKER_JOB_KINDS)))
            except Exception:log.exception('Worker heartbeat failed')
            heartbeat_stop.wait(15)
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        while running:
            reap_exhausted()
            if not run_once():time.sleep(1)
    finally:
        heartbeat_stop.set();thread.join(timeout=5)
        with transaction() as db:
            row=db.get(WorkerHeartbeat,identity)
            if row:db.delete(row)

if __name__=='__main__':main()
