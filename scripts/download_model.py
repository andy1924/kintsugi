"""Download the official SAM 2.1 tiny checkpoint; keep weights out of Git."""
import hashlib
from pathlib import Path
import urllib.request
root=Path(__file__).resolve().parents[1]
target=root/'.data/models/sam2.1_hiera_tiny.pt'
target.parent.mkdir(parents=True,exist_ok=True)
expected='7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69'
url='https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt'
if not target.exists():
    temp=target.with_suffix('.download')
    try:
        with urllib.request.urlopen(url,timeout=60) as response,temp.open('wb') as output:
            while chunk:=response.read(1024*1024):output.write(chunk)
        with temp.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected:raise RuntimeError('Checkpoint checksum mismatch.')
        temp.replace(target)
    finally:temp.unlink(missing_ok=True)
with target.open('rb') as stream:
    if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise RuntimeError('Existing checkpoint checksum mismatch.')
print('Checkpoint:',target)
print('SHA256:',hashlib.file_digest(target.open('rb'),'sha256').hexdigest())
print('Set SEGMENTATION_MODEL=sam2, SAM2_CHECKPOINT='+str(target))
