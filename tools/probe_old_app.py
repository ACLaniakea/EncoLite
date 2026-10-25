"""Try current production UI/controller with an isolated older Slint runtime."""
from pathlib import Path
import os,shutil,subprocess,json,sys
ROOT=Path(__file__).resolve().parents[1]
VERSION=sys.argv[1] if len(sys.argv)>1 else '1.16.1b1'
STAGE=ROOT/'.install-test/old-app'/VERSION
if STAGE.exists():shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)
for name in ('encolite','ui'):
    shutil.copytree(ROOT/name,STAGE/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copy2(ROOT/'main.py',STAGE/'main.py')
shutil.copytree(ROOT/'.tools/slint-candidates'/VERSION/'package',STAGE/'.build-deps',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
# _native was introduced in newer bindings; this is only a Python compatibility shim.
shim=STAGE/'.build-deps/slint/_native.py'
if not shim.exists():shim.write_text('from . import native\n','utf-8')
from compat_ui import backport
backport(STAGE, VERSION)
host=ROOT/'.tools/python-3.13.17-embed-amd64/python.exe'
# The embeddable runtime ignores environment paths; bootstrap the app explicitly.
bootstrap=STAGE/'run.py'
bootstrap.write_text('import sys,runpy\nfrom pathlib import Path\nroot=Path(__file__).resolve().parent\nsys.path.insert(0,str(root))\nrunpy.run_path(str(root/"main.py"),run_name="__main__")\n','utf-8')
report=ROOT/'verification'/f'old-app-{VERSION}.json';report.unlink(missing_ok=True)
env={**os.environ,'PYTHONIOENCODING':'utf-8'}
try:
    p=subprocess.run([str(host),str(bootstrap),'--smoke-test','--no-tray','--test-report',str(report)],capture_output=True,env=env,timeout=30)
    data={'version':VERSION,'exit':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
    if report.exists():data['smoke']=json.loads(report.read_text('utf-8'))
    print(json.dumps(data,ensure_ascii=True),flush=True)
    (ROOT/'verification'/f'old-app-{VERSION}-run.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
except Exception as error:
    print(repr(error),flush=True);raise
