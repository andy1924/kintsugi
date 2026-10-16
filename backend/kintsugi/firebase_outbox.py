"""Capture cloud documents in the SAME transaction as domain changes."""
import hashlib
import json
from sqlalchemy import event,select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from . import config
from .db import Session,Base

TRACKED={'users','projects','makers','repair_services','service_quotes','shipments','maker_earnings','service_events','completions','repair_generations'}


def enqueue(connection,table,record_id,payload):
    from .models import FirebaseOutbox
    if table=='users' and payload:
        payload={key:value for key,value in payload.items() if key!='password'}
    # Firestore does not support nested arrays: encode JSON-heavy geometry as JSON text.
    encoded=None if payload is None else json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False)
    fingerprint=hashlib.sha256((encoded or 'deleted').encode()).hexdigest()
    if encoded and len(encoded.encode())>800_000:raise ValueError('Cloud record exceeds the Firestore document budget.')
    body=None if payload is None else {'json':encoded,'user_id':payload.get('user_id') or (payload.get('id') if table=='users' else None),**{key:payload[key] for key in ('title','status','category','created_at','updated_at') if key in payload}}
    values={'key':f'{table}/{record_id}','collection':'kintsugi_'+table,'document_id':record_id,'payload':body,'payload_hash':fingerprint,
            'version':1,'synced_version':0,'pending':True,'attempts':0,'next_attempt':0,'lease_until':0,'lock_token':None,'last_error':None}
    insert=sqlite_insert if connection.dialect.name=='sqlite' else pg_insert
    statement=insert(FirebaseOutbox).values(**values)
    connection.execute(statement.on_conflict_do_update(index_elements=['key'],set_={
        'payload':body,'payload_hash':fingerprint,'version':FirebaseOutbox.version+1,'pending':True,'attempts':0,'next_attempt':0,'last_error':None,
    },where=FirebaseOutbox.payload_hash!=fingerprint))


@event.listens_for(Session,'before_flush')
def remember_objects(session,flush_context,instances):
    if not config.FIRESTORE_ENABLED:return
    changed=session.info.setdefault('firebase_objects',{})
    for obj in list(session.new)+list(session.dirty)+list(session.deleted):
        if getattr(obj,'__tablename__',None) in TRACKED:
            changed[id(obj)]=(obj,obj in session.deleted)


@event.listens_for(Session,'do_orm_execute')
def remember_bulk(execution):
    if not config.FIRESTORE_ENABLED or not (execution.is_update or execution.is_delete):return
    mapper=execution.bind_mapper
    if not mapper or mapper.local_table.name not in TRACKED:return
    table=mapper.local_table;pk=list(table.primary_key.columns)[0]
    query=select(pk)
    if execution.statement.whereclause is not None:query=query.where(execution.statement.whereclause)
    ids=execution.session.connection().execute(query).scalars().all()
    touched=execution.session.info.setdefault('firebase_bulk',{})
    for value in ids:touched[(table.name,value)]=(table,execution.is_delete)


@event.listens_for(Session,'before_commit')
def capture(session):
    if not config.FIRESTORE_ENABLED:return
    session.flush()
    touched=session.info.pop('firebase_bulk',{})
    for obj,deleted in session.info.pop('firebase_objects',{}).values():
        table=obj.__table__;pk=list(table.primary_key.columns)[0]
        touched[(table.name,getattr(obj,pk.name))]=(table,deleted)
    connection=session.connection()
    for (name,record_id),(table,deleted) in touched.items():
        pk=list(table.primary_key.columns)[0]
        row=None if deleted else connection.execute(select(table).where(pk==record_id)).mappings().first()
        enqueue(connection,name,record_id,dict(row) if row else None)


@event.listens_for(Session,'after_rollback')
def discard(session):
    session.info.pop('firebase_objects',None);session.info.pop('firebase_bulk',None)


def backfill(db):
    connection=db.connection();count=0
    for table in Base.metadata.sorted_tables:
        if table.name not in TRACKED:continue
        pk=list(table.primary_key.columns)[0]
        for row in connection.execute(select(table)).mappings():
            enqueue(connection,table.name,row[pk.name],dict(row));count+=1
    return count
