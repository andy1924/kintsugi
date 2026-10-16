"""Generate local secrets once. Never overwrite an existing environment."""
import os
import secrets
from pathlib import Path
root=Path(__file__).resolve().parents[1]
target=root/'.env'
if not target.exists():
    content=f'KINTSUGI_SECRET={secrets.token_hex(32)}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(28)}\nWEB_ORIGINS=http://localhost:8080,http://127.0.0.1:5173,http://localhost:5173\nSECURE_COOKIE=false\nSEGMENTATION_MODEL=grabcut\n'
    descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as f:f.write(content)
    print('Created local .env with random secrets.')
else:print('Existing .env preserved.')
