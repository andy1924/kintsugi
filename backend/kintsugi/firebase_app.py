"""Firebase Admin credentials are server-only and loaded through ADC."""
import re
import time
import threading
from functools import lru_cache
from fastapi import HTTPException
from . import config


def public_config():
    enabled=bool(config.FIREBASE_PROJECT_ID and config.FIREBASE_WEB_API_KEY and config.FIREBASE_WEB_APP_ID and config.FIREBASE_AUTH_DOMAIN)
    return {'enabled':enabled,'config':{'apiKey':config.FIREBASE_WEB_API_KEY,'projectId':config.FIREBASE_PROJECT_ID,
            'appId':config.FIREBASE_WEB_APP_ID,'authDomain':config.FIREBASE_AUTH_DOMAIN} if enabled else None}


_admin_lock=threading.Lock()

@lru_cache(maxsize=1)
def admin_app():
    import firebase_admin
    from firebase_admin import credentials
    if not config.FIREBASE_PROJECT_ID:raise HTTPException(503,'Firebase is not configured on this server.')
    # ADC uses GOOGLE_APPLICATION_CREDENTIALS locally or the attached cloud service account.
    from google.auth.exceptions import DefaultCredentialsError
    with _admin_lock:
        try:return firebase_admin.get_app('kintsugi')
        except ValueError:pass
        try:return firebase_admin.initialize_app(credentials.ApplicationDefault(),{'projectId':config.FIREBASE_PROJECT_ID},name='kintsugi')
        except (DefaultCredentialsError,ValueError):raise HTTPException(503,'Firebase server credentials are missing or invalid.') from None


@lru_cache(maxsize=1)
def firestore_client():
    from firebase_admin import firestore
    if not config.FIRESTORE_ENABLED:raise HTTPException(503,'Cloud Firestore is not enabled on this server.')
    return firestore.client(app=admin_app())


def verify_google_token(token):
    from firebase_admin import auth
    from firebase_admin.exceptions import FirebaseError
    try:
        claims=auth.verify_id_token(token,app=admin_app(),check_revoked=True,clock_skew_seconds=5)
    except (auth.InvalidIdTokenError,auth.RevokedIdTokenError,auth.UserDisabledError,ValueError):
        raise HTTPException(401,'Google sign-in expired or could not be verified. Please sign in again.') from None
    except (FirebaseError,OSError):
        raise HTTPException(503,'Google sign-in verification is temporarily unavailable.') from None
    uid=claims.get('uid');email=claims.get('email','').strip().lower()
    provider=(claims.get('firebase') or {})
    auth_time=claims.get('auth_time',0)
    if (provider.get('sign_in_provider')!='google.com' or provider.get('tenant') or
        claims.get('email_verified') is not True or not isinstance(uid,str) or not 1<=len(uid)<=128 or
        not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254):
        raise HTTPException(401,'Use a verified Google account to sign in.')
    if not isinstance(auth_time,(int,float)) or not time.time()-600<=auth_time<=time.time()+30:
        raise HTTPException(401,'Please authenticate with Google again before creating a studio session.')
    return {'uid':uid,'email':email,'name':str(claims.get('name') or email.split('@')[0])[:80]}
