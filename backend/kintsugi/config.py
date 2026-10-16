import os
from pathlib import Path

DATA = Path(os.getenv('DATA_DIR', '.data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "kintsugi.db"}')
SECRET = os.getenv('KINTSUGI_SECRET', '')
ORIGINS = set(os.getenv('WEB_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173,http://localhost:8080').split(','))
SECURE_COOKIE = os.getenv('SECURE_COOKIE', 'false').lower() == 'true'
MAX_BYTES = 12 * 1024 * 1024
MODEL = os.getenv('SEGMENTATION_MODEL', 'grabcut')
DAMAGE_ANALYSIS_PROVIDER = os.getenv('DAMAGE_ANALYSIS_PROVIDER', 'auto').lower()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '').strip()
OPENAI_VISION_MODEL = os.getenv('OPENAI_VISION_MODEL', 'gpt-5.6-terra')
if DAMAGE_ANALYSIS_PROVIDER not in ('auto', 'local', 'openai'):
    raise RuntimeError('DAMAGE_ANALYSIS_PROVIDER must be auto, local or openai.')

def analysis_provider():
    if DAMAGE_ANALYSIS_PROVIDER == 'auto':
        return 'openai' if OPENAI_API_KEY else 'local'
    return DAMAGE_ANALYSIS_PROVIDER

SESSION_DAYS = 14

TRUST_PROXY_HEADERS = os.getenv('TRUST_PROXY_HEADERS', 'false').lower() == 'true'
SERVICE_FEE_BPS = int(os.getenv('SERVICE_FEE_BPS', '500'))
if not 0 <= SERVICE_FEE_BPS <= 2500:
    raise RuntimeError('SERVICE_FEE_BPS must be between 0 and 2500.')

# Image edits remain on the server; never expose the API key to Vite.
OPENAI_IMAGE_MODEL = os.getenv('OPENAI_IMAGE_MODEL','gpt-image-2.5-sunburst')
REPAIR_PREVIEW_PROVIDER = os.getenv('REPAIR_PREVIEW_PROVIDER','auto').lower()
if REPAIR_PREVIEW_PROVIDER not in ('auto','openai','off'):
    raise RuntimeError('REPAIR_PREVIEW_PROVIDER must be auto, openai or off.')

def preview_enabled():
    return REPAIR_PREVIEW_PROVIDER != 'off' and bool(OPENAI_API_KEY)

# Admission limits count generation attempts, not estimated currency amounts.
GENERATION_USER_DAILY_LIMIT = int(os.getenv('GENERATION_USER_DAILY_LIMIT','12'))
GENERATION_GLOBAL_DAILY_LIMIT = int(os.getenv('GENERATION_GLOBAL_DAILY_LIMIT','300'))
if not 1 <= GENERATION_USER_DAILY_LIMIT <= 1000 or not 1 <= GENERATION_GLOBAL_DAILY_LIMIT <= 100000:
    raise RuntimeError('Generation limits must be positive and within supported bounds.')
WORKER_JOB_KINDS = tuple(dict.fromkeys(os.getenv('WORKER_JOB_KINDS','analyze,compile,preview').split(',')))
if not WORKER_JOB_KINDS or any(kind not in ('analyze','compile','preview') for kind in WORKER_JOB_KINDS):
    raise RuntimeError('WORKER_JOB_KINDS must contain analyze, compile and/or preview.')

FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID','').strip()
FIREBASE_WEB_API_KEY = os.getenv('FIREBASE_WEB_API_KEY','').strip()
FIREBASE_WEB_APP_ID = os.getenv('FIREBASE_WEB_APP_ID','').strip()
FIREBASE_AUTH_DOMAIN = os.getenv('FIREBASE_AUTH_DOMAIN','').strip()
FIRESTORE_ENABLED = os.getenv('FIRESTORE_ENABLED','false').lower() == 'true'
FIREBASE_EMULATORS_ALLOWED = os.getenv('FIREBASE_EMULATORS_ALLOWED','false').lower() == 'true'
if FIRESTORE_ENABLED and not FIREBASE_PROJECT_ID:
    raise RuntimeError('FIRESTORE_ENABLED requires FIREBASE_PROJECT_ID.')
if any(os.getenv(key) for key in ('FIREBASE_AUTH_EMULATOR_HOST','FIRESTORE_EMULATOR_HOST')) and not FIREBASE_EMULATORS_ALLOWED:
    raise RuntimeError('Firebase emulators require explicit FIREBASE_EMULATORS_ALLOWED=true in development only.')
