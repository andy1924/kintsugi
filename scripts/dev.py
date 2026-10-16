"""Start the complete local app; stop all child processes on Ctrl-C or a failure."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv
root=Path(__file__).resolve().parents[1]
os.chdir(root)
subprocess.run([sys.executable,str(root/'scripts/init_dev.py')],check=True)
load_dotenv(root/'.env')
os.environ['PYTHONPATH']=str(root/'backend')
if '--sam2' in sys.argv:
    os.environ['SEGMENTATION_MODEL']='sam2'
    os.environ.setdefault('SAM2_CHECKPOINT',str(root/'.data/models/sam2.1_hiera_tiny.pt'))
subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],check=True)
web=['npm','run','preview','--','--port','5173','--strictPort'] if '--preview' in sys.argv else ['npm','run','dev']
if '--preview' in sys.argv:subprocess.run(['npm','run','build'],cwd=root,check=True)
commands=[[sys.executable,'-m','uvicorn','kintsugi.main:app','--host','127.0.0.1','--port','8000'],[sys.executable,'-m','kintsugi.worker'],web]
if os.getenv('FIRESTORE_ENABLED','false').lower()=='true':commands.append([sys.executable,'-m','kintsugi.firebase_sync'])
children=[]
def stop(*_):
    for child in children:
        if child.poll() is None:child.terminate()
    for child in children:
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:child.kill()
    sys.exit(0)
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
try:
    for cmd in commands:children.append(subprocess.Popen(cmd,cwd=root))
    print('\nKintsugi: http://127.0.0.1:5173/ | API docs: http://127.0.0.1:8000/docs\n',flush=True)
    while True:
        if any(child.poll() is not None for child in children):
            print('A service exited. Stopping the local stack.',flush=True);break
        time.sleep(1)
finally:stop()
