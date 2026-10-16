"""Independent Firestore sync worker: leased, idempotent, version-ordered writes."""
import argparse
import signal
import time
import uuid
from sqlalchemy import select,update,case,func
from . import config
from .db import Session,transaction
from .models import FirebaseOutbox
from .firebase_app import firestore_client
from . import firebase_outbox


def write_document(collection,document_id,payload,version):
    from google.cloud import firestore
    client=firestore_client();reference=client.collection(collection).document(document_id)
    @firestore.transactional
    def apply(tx):
        snapshot=reference.get(transaction=tx,timeout=10)
        existing=snapshot.to_dict() if snapshot.exists else {}
        if existing.get('version',0)>=version:return
        tx.set(reference,{'version':version,'deleted':payload is None,'data':payload,'synced_at':firestore.SERVER_TIMESTAMP})
    apply(client.transaction(max_attempts=3))


def run_once():
    if not config.FIRESTORE_ENABLED:return False
    now=time.time();token=uuid.uuid4().hex
    with transaction() as db:
        row=db.scalar(select(FirebaseOutbox).where(FirebaseOutbox.pending.is_(True),FirebaseOutbox.next_attempt<=now,FirebaseOutbox.lease_until<now).order_by(FirebaseOutbox.next_attempt).with_for_update(skip_locked=True).limit(1))
        if not row:return False
        claimed=db.execute(update(FirebaseOutbox).where(FirebaseOutbox.key==row.key,FirebaseOutbox.lease_until<now).values(lock_token=token,lease_until=now+90)).rowcount
        if not claimed:return False
        key=row.key;collection=row.collection;document_id=row.document_id;payload=row.payload;version=row.version
    try:
        write_document(collection,document_id,payload,version)
        with transaction() as db:
            db.execute(update(FirebaseOutbox).where(FirebaseOutbox.key==key,FirebaseOutbox.lock_token==token).values(
                synced_version=case((FirebaseOutbox.synced_version<version,version),else_=FirebaseOutbox.synced_version),
                pending=FirebaseOutbox.version>version,lease_until=0,lock_token=None,attempts=0,next_attempt=0,last_error=None,synced_at=time.time()))
    except Exception:
        with transaction() as db:
            current=db.get(FirebaseOutbox,key)
            if current and current.lock_token==token:
                current.attempts+=1;current.next_attempt=time.time()+min(300,2**min(current.attempts,8));current.lease_until=0;current.lock_token=None
                current.last_error='Firestore sync unavailable. Check the project, credentials and Firestore API; the change remains queued.'
    return True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backfill',action='store_true');parser.add_argument('--once',action='store_true');args=parser.parse_args()
    if not config.FIRESTORE_ENABLED:raise SystemExit('Set FIRESTORE_ENABLED=true and configure Firebase credentials first.')
    if args.backfill:
        with transaction() as db:count=firebase_outbox.backfill(db)
        print(f'Queued {count} existing records for Firestore.')
    if args.once:run_once();return
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    while not stopping:
        if not run_once():time.sleep(1)

if __name__=='__main__':main()
