"""Test a fully copied official Python runtime and old Slint, without policy changes."""
from pathlib import Path
import json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.install-test/old-app/1.17.1b2'
runtime=STAGE/'runtime'
if runtime.exists():shutil.rmtree(runtime)
shutil.copytree(ROOT/'.tools/python-3.13.17-embed-amd64',runtime)
(STAGE/'tools').mkdir(exist_ok=True)
(STAGE/'verification').mkdir(exist_ok=True)
for name in ('verify_desktop.py','verify_window_lifetime.py','verify_persistence.py','verify_native_read.py'):
    shutil.copy2(ROOT/'tools'/name,STAGE/'tools'/name)
bootstrap=STAGE/'run_check.py'
bootstrap.write_text('import runpy,sys\nfrom pathlib import Path\nroot=Path(__file__).resolve().parent\nsys.path[:0]=[str(root),str(root/".build-deps")]\ntarget=sys.argv.pop(1)\nrunpy.run_path(str(root/target),run_name="__main__")\n','utf-8')
env={**os.environ,'PYTHONIOENCODING':'utf-8'}
main=STAGE/'main.py'
source=main.read_text('utf-8')
source=source.replace('smoke_errors.append(repr(error))','smoke_errors.append(__import__("traceback").format_exc())')
main.write_text(source,'utf-8')
results=[]
def run(label,target,*args,timeout=35):
    try:
        p=subprocess.run([str(runtime/'python.exe'),str(bootstrap),target,*args],capture_output=True,env=env,timeout=timeout)
        result={'label':label,'exit':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
    except (OSError,subprocess.TimeoutExpired) as error:result={'label':label,'error':repr(error)}
    results.append(result)
    print(json.dumps(result,ensure_ascii=True),flush=True)
    (ROOT/'verification/old-runtime.json').write_text(json.dumps({'results':results,'security_changes':False},ensure_ascii=False,indent=2),'utf-8')
    return result.get('exit')==0
for i in range(3):
    run(f'copied runtime smoke {i+1}','main.py','--smoke-test','--test-report',str(STAGE/'verification'/f'smoke-{i}.json'))
for name in ('verify_desktop.py','verify_window_lifetime.py'):
    run(name,'tools/'+name)
for phase in ('write','read','write-max','read-max'):
    run('persistence '+phase,'tools/verify_persistence.py',phase)
run('read-only X3 connection','tools/verify_native_read.py')
