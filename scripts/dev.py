"""Start the complete local app; stop all child processes on Ctrl-C or a failure."""
import os
import argparse
import shutil
from pathlib import Path
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sam2',action='store_true')
parser.add_argument('--preview',action='store_true')
parser.add_argument('--port',type=int,default=5173)
args=parser.parse_args()
if not 1<=args.port<=65535:parser.error('--port must be between 1 and 65535')
root=Path(__file__).resolve().parents[1]
os.chdir(root)
subprocess.run([sys.executable,str(root/'scripts/init_dev.py')],check=True)
load_dotenv(root/'.env')
origins=set(os.environ.get('WEB_ORIGINS','http://localhost:8080').split(','))
origins.update([f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}'])
os.environ['WEB_ORIGINS']=','.join(sorted(origins))
os.environ['PYTHONPATH']=str(root/'backend')
if args.sam2:
    os.environ['SEGMENTATION_MODEL']='sam2'
    os.environ.setdefault('SAM2_CHECKPOINT',str(root/'.data/models/sam2.1_hiera_tiny.pt'))
subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],check=True)
npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
if not npm:raise RuntimeError('Install Node.js and npm before starting the studio.')
web=[npm,'run','preview' if args.preview else 'dev','--','--port',str(args.port),'--strictPort']
if args.preview:subprocess.run([npm,'run','build'],cwd=root,check=True)
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
    print(f'\nKintsugi: http://127.0.0.1:{args.port}/ | API docs: http://127.0.0.1:8000/docs\n',flush=True)
    while True:
        if any(child.poll() is not None for child in children):
            print('A service exited. Stopping the local stack.',flush=True);break
        time.sleep(1)
finally:stop()
