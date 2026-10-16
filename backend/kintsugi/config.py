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
