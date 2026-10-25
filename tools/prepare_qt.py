"""Fetch pinned official Qt wheels, verify hashes, and unpack locally."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.tools/qt-probe';OUT=WORK/'packages';WHEELS=WORK/'wheels'
PINNED={'PySide6-Essentials':('pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl','c9a95102aa23c1f86516a30d5a9be37552d324eee7e567eb7508973f1218cb42'),
 'shiboken6':('shiboken6-6.12.0-cp310-abi3-win_amd64.whl','a1906cb8116869178c64b6bab52623bbc8b4ceed7b30bfc3c9aa0f6e67f6438e')}
OUT.mkdir(parents=True,exist_ok=True);WHEELS.mkdir(exist_ok=True);rows=[]
for project,(filename,digest) in PINNED.items():
 path=WHEELS/filename
 if not path.exists():
  metadata=json.loads(urllib.request.urlopen(f'https://pypi.org/pypi/{project}/6.12.0/json',timeout=30).read())
  item=next(item for item in metadata['urls'] if item['filename']==filename)
  assert item['digests']['sha256']==digest
  with urllib.request.urlopen(item['url'],timeout=60) as response,path.open('wb') as target:
   while chunk:=response.read(1024*1024):target.write(chunk)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,filename
 with zipfile.ZipFile(path) as archive:
  assert all((OUT/member).resolve().is_relative_to(OUT.resolve()) for member in archive.namelist())
  archive.extractall(OUT)
 rows.append({'file':filename,'sha256':digest})
(WORK/'provenance.json').write_text(json.dumps({'version':'6.12.0','source':'https://pypi.org/project/PySide6-Essentials/6.12.0/','artifacts':rows},indent=2),'utf-8')
print('Official Qt wheels prepared',flush=True)
