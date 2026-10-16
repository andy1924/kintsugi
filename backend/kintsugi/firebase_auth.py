from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .auth import current_user,origin_check,rate_limit,issue_session,digest,client_address
from .db import get_db
from .models import User
from . import firebase_app

router=APIRouter(prefix='/api/v1/auth/firebase',tags=['Google authentication'])

class FirebaseToken(BaseModel):
    id_token:str=Field(min_length=20,max_length=16000,repr=False)

@router.get('/config')
def configuration():return firebase_app.public_config()

@router.post('/session')
def google_session(body:FirebaseToken,request:Request,response:Response,db=Depends(get_db)):
    origin_check(request);rate_limit(db,'google:'+digest(client_address(request)),20,900)
    identity=firebase_app.verify_google_token(body.id_token)
    user=db.scalar(select(User).where(User.firebase_uid==identity['uid']))
    if not user:
        if db.scalar(select(User.id).where(User.email==identity['email'])):
            raise HTTPException(409,'An account with this email already exists. Sign in with its password and link Google from your worktable.')
        user=User(email=identity['email'],name=identity['name'],password='!firebase-only',firebase_uid=identity['uid'])
        db.add(user)
        try:db.flush()
        except IntegrityError:
            db.rollback();user=db.scalar(select(User).where(User.firebase_uid==identity['uid']))
            if not user:raise HTTPException(409,'This email is already registered. Sign in to the existing account first.') from None
    # App cookies expire after one hour; no Google access/refresh token is stored.
    return issue_session(db,user,response,lifetime=3600)

@router.post('/link')
def link_google(body:FirebaseToken,user=Depends(current_user),db=Depends(get_db)):
    rate_limit(db,'google-link:'+user.id,10,900)
    identity=firebase_app.verify_google_token(body.id_token)
    if identity['email']!=user.email:raise HTTPException(409,'Choose the Google account with the same email as your studio account.')
    if user.firebase_uid and user.firebase_uid!=identity['uid']:raise HTTPException(409,'This account is already linked to a different Google identity.')
    user.firebase_uid=identity['uid']
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'That Google identity is already linked to another studio account.') from None
    return {'linked':True}
