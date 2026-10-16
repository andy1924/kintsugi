"""Owner-scoped Firestore reads and operator sync diagnostics."""
import json
import time
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,func
from . import config
from .auth import current_user
from .db import get_db
from .models import FirebaseOutbox
from .firebase_app import firestore_client

router=APIRouter(prefix='/api/v1/firebase',tags=['Cloud Firestore'])

def public_project(document):
    project=json.loads(document['data']['json'])
    for key in ('image_key','image_hash','image_phash'):project.pop(key,None)
    for field in ('plan','preview'):
        if project.get(field):project[field]={key:value for key,value in project[field].items() if key not in ('image_key','pdf_key','svg_key')}
    return {'version':document['version'],'project':project}

@router.get('/projects')
def cloud_projects(user=Depends(current_user),limit:int=Query(default=25,ge=1,le=50),after:str|None=Query(default=None,pattern=r'^[0-9a-f]{32}$')):
    if not config.FIRESTORE_ENABLED:raise HTTPException(503,'Cloud Firestore is not configured yet.')
    from google.cloud.firestore_v1.base_query import FieldFilter
    try:
        collection=firestore_client().collection('kintsugi_projects')
        query=collection.where(filter=FieldFilter('data.user_id','==',user.id)).order_by('__name__').limit(limit)
        if after:query=query.start_after({'__name__':collection.document(after)})
        snapshots=list(query.stream(timeout=10));results=[]
        for snapshot in snapshots:
            document=snapshot.to_dict()
            if not document.get('deleted') and document.get('data',{}).get('user_id')==user.id:results.append(public_project(document))
        return {'items':results,'next_cursor':snapshots[-1].id if len(snapshots)==limit else None}
    except Exception:raise HTTPException(503,'Cloud data is temporarily unavailable; your local repairs remain saved.') from None

@router.get('/projects/{project_id}')
def cloud_project(project_id:str,user=Depends(current_user)):
    if not config.FIRESTORE_ENABLED:raise HTTPException(503,'Cloud Firestore is not configured yet.')
    try:snapshot=firestore_client().collection('kintsugi_projects').document(project_id).get(timeout=10)
    except Exception:raise HTTPException(503,'Cloud data is temporarily unavailable; your local repair remains saved.') from None
    document=snapshot.to_dict() if snapshot.exists else {}
    data=document.get('data') or {}
    if document.get('deleted') or data.get('user_id')!=user.id:raise HTTPException(404,'Repair not found in cloud storage.')
    return public_project(document)

@router.get('/sync-status')
def sync_status(user=Depends(current_user),db=Depends(get_db)):
    from .network import operator
    operator(user)
    pending=db.scalar(select(func.count()).select_from(FirebaseOutbox).where(FirebaseOutbox.pending.is_(True)))
    errors=db.scalar(select(func.count()).select_from(FirebaseOutbox).where(FirebaseOutbox.last_error.is_not(None)))
    return {'enabled':config.FIRESTORE_ENABLED,'pending':pending,'retrying':errors,'last_synced_at':db.scalar(select(func.max(FirebaseOutbox.synced_at)))}
