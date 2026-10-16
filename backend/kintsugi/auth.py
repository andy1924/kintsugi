import hashlib
import ipaddress
import hmac
import secrets
import time
from fastapi import Depends, HTTPException, Request
from argon2 import PasswordHasher
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from . import config
from .db import get_db
from .models import User, LoginSession, RateBucket

hasher = PasswordHasher(time_cost=2, memory_cost=32768, parallelism=2)
COOKIE = 'kintsugi_session'

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def csrf(token): return hmac.new(config.SECRET.encode(), token.encode(), 'sha256').hexdigest()

def origin_check(request: Request):
    origin = request.headers.get('origin')
    if origin and origin not in config.ORIGINS:
        raise HTTPException(403, 'This origin is not allowed.')

def client_address(request):
    if config.TRUST_PROXY_HEADERS:
        value=request.headers.get('x-real-ip','')
        try:return str(ipaddress.ip_address(value))
        except ValueError:pass
    return request.client.host

def current_user(request: Request, db=Depends(get_db)):
    token = request.cookies.get(COOKIE, '')
    login = db.get(LoginSession, digest(token)) if token else None
    if not login or login.expires_at < time.time(): raise HTTPException(401, 'Please sign in.')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin_check(request)
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), csrf(token)):
            raise HTTPException(403, 'Session protection failed. Refresh and try again.')
    return db.get(User, login.user_id)

def rate_limit(db, key, limit=20, window=900):
    now = time.time()
    bucket = f'{key}:{int(now // window)}'
    insert = sqlite_insert if db.bind.dialect.name == 'sqlite' else pg_insert
    # Database-backed atomic increment works across API replicas.
    value = db.execute(insert(RateBucket).values(key=bucket, hits=1, expires_at=now+window).on_conflict_do_update(index_elements=['key'], set_={'hits': RateBucket.hits+1}).returning(RateBucket.hits)).scalar_one()
    db.commit()
    if value > limit: raise HTTPException(429, 'Too many requests. Please try again later.', headers={'Retry-After':str(window)})

def issue_session(db, user, response):
    token = secrets.token_urlsafe(40)
    db.add(LoginSession(token_hash=digest(token), user_id=user.id, expires_at=time.time()+config.SESSION_DAYS*86400))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=config.SECURE_COOKIE, samesite='lax', max_age=config.SESSION_DAYS*86400, path='/')
    return {'user': {'id':user.id, 'name':user.name, 'email':user.email,'role':user.role}, 'csrf':csrf(token)}
