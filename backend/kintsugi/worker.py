"""Durable leased jobs. Run separately from the HTTP process; scale on PostgreSQL."""
import logging
import signal
import threading
import time
import uuid
from sqlalchemy import select, update, or_, and_
from .db import Session, transaction
from .models import Job, Project, WorkerHeartbeat
from .storage import store
from .imaging import validate_model
from .analysis import analyze_damage
from .vision import VisionError
from .compiler import make_plan

log=logging.getLogger('kintsugi.worker')
LEASE_SECONDS=900
running=True

def claim():
    now=time.time()
    with transaction() as db:
        eligible=or_(and_(Job.state=='queued',Job.run_after<=now),and_(Job.state=='running',Job.lease_until<now))
        job=db.scalar(select(Job).where(eligible,Job.attempts<3).order_by(Job.run_after).with_for_update(skip_locked=True).limit(1))
        if not job:return None
        token=uuid.uuid4().hex
        # Conditional update also protects single-host SQLite against competing claimers.
        got=db.execute(update(Job).where(Job.id==job.id,eligible,Job.attempts<3).values(state='running',lock_token=token,lease_until=now+LEASE_SECONDS,attempts=Job.attempts+1).returning(Job.id)).scalar_one_or_none()
        return (got,token) if got else None

def run_once():
    claimed=claim()
    if not claimed:return False
    job_id,token=claimed
    try:
        with Session() as db:
            job=db.get(Job,job_id);project=db.get(Project,job.project_id)
            if project.revision!=job.revision:raise ValueError('This job was superseded by a newer revision.')
            result=analyze_damage(store.get(project.image_key),project.settings) if job.kind=='analyze' else make_plan(project)
        with transaction() as db:
            owned=db.execute(update(Job).where(Job.id==job_id,Job.lock_token==token,Job.state=='running',Job.lease_until>time.time()).values(state='succeeded',lease_until=0)).rowcount
            if owned:
                field='analysis' if job.kind=='analyze' else 'plan'
                db.execute(update(Project).where(Project.id==job.project_id,Project.revision==job.revision).values(**{field:result,'status':'needs_review' if job.kind=='analyze' else 'ready','error':None,'updated_at':time.time()}))
    except Exception as error:
        log.exception('Job %s failed',job_id)
        with transaction() as db:
            job=db.get(Job,job_id)
            if job.lock_token==token and job.state=='running':
                job.error=str(error) if isinstance(error,VisionError) else 'Processing failed. Please retry with a clear photo or contact the studio.'
                permanent=isinstance(error,VisionError) and not error.retryable
                job.state='failed' if permanent or job.attempts>=3 else 'queued';job.run_after=time.time()+min(60,2**job.attempts);job.lease_until=0
                if job.state=='failed':
                    db.execute(update(Project).where(Project.id==job.project_id,Project.revision==job.revision).values(status='failed',error=job.error,updated_at=time.time()))
    return True

def reap_exhausted():
    with transaction() as db:
        for job in db.scalars(select(Job).where(Job.state=='running',Job.lease_until<time.time(),Job.attempts>=3).with_for_update(skip_locked=True)):
            job.state='failed';job.error='The worker was interrupted repeatedly. Please retry the repair.'
            db.execute(update(Project).where(Project.id==job.project_id,Project.revision==job.revision).values(status='failed',error=job.error))

def main():
    global running
    logging.basicConfig(level=logging.INFO)
    validate_model() # Missing SAM weights fail startup, never silently pretend to use SAM.
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
                with transaction() as db:db.merge(WorkerHeartbeat(id=identity,updated_at=time.time(),model=MODEL))
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
