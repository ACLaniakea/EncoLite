"""Compare actual old Slint modules after normal Windows file copying.

No application files, certificates, or security policies are modified.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.install-test/older-slint'
HOST=ROOT/'.tools/python-3.13.17-embed-amd64/python.exe'
VERSIONS=('1.16.1b1','1.14.1b1','1.12.1b1')
report={'versions':[],'security_changes':False}
code='''import sys,json,os
os.environ['SLINT_BACKEND']='winit-software'
sys.path.insert(0,sys.argv[1])
import slint
native=slint.native
print(json.dumps({'phase':'import','result':'PASS','binary':native.__file__}),flush=True)
for name in ('app.slint','quick.slint','notice.slint'):
    slint.load_file(__import__('pathlib').Path(sys.argv[2])/'ui'/name,style='fluent')
print(json.dumps({'phase':'compile-current-ui','result':'PASS'}),flush=True)
'''
try:
    if STAGE.exists():shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    script=STAGE/'check.py';script.write_text(code,'utf-8')
    for version in VERSIONS:
        source=ROOT/'.tools/slint-candidates'/version/'package'
        package=STAGE/version
        shutil.copytree(source,package,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        item={'version':version,'binary_sha256':hashlib.sha256((package/'slint/slint.pyd').read_bytes()).hexdigest(),'runs':[]}
        for index in range(3):
            env={**os.environ,'PYTHONIOENCODING':'utf-8'}
            try:
                p=subprocess.run([str(HOST),str(script),str(package),str(ROOT)],capture_output=True,timeout=25,env=env)
                result={'exit':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
            except (OSError,subprocess.TimeoutExpired) as error:result={'error':repr(error)}
            item['runs'].append(result)
            print(json.dumps({'version':version,'attempt':index+1,**result},ensure_ascii=True),flush=True)
            time.sleep(.3)
        report['versions'].append(item)
finally:
    (ROOT/'verification/older-slint.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    if STAGE.exists():shutil.rmtree(STAGE)
