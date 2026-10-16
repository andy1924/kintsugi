"""Expire old session, limiter and worker-liveness rows; run daily."""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
root=Path(__file__).resolve().parents[1]
load_dotenv(root/'.env');sys.path.insert(0,str(root/'backend'))
from sqlalchemy import delete
from kintsugi.db import transaction
from kintsugi.models import LoginSession,RateBucket,WorkerHeartbeat
with transaction() as db:
    now=time.time()
    for model,condition in [(LoginSession,LoginSession.expires_at<now),(RateBucket,RateBucket.expires_at<now),(WorkerHeartbeat,WorkerHeartbeat.updated_at<now-86400)]:
        count=db.execute(delete(model).where(condition)).rowcount
        print(f'{model.__tablename__}: removed {count} expired rows')
