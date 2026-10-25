"""Exercise production code with the statically linked Slint binding.

Only the isolated MSI test install's Python entry is temporarily replaced with
the existing validation scripts, then restored in finally. The distributed executable, runtime, controller and UI stay unchanged.
"""
from pathlib import Path
import json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
stage=ROOT/'.install-test/Enco Lite'
assert (stage/'EncoLite.exe').exists(),'Install the isolated MSI test first'
app=stage/'app';original=(app/'main.py').read_bytes()
tools=app/'tools';tools.mkdir()
(app/'verification').mkdir()
report={'checks':[],'errors':[],'runtime':'statically linked Slint + official CPython 3.13.17'}

def run(script,args=(),timeout=35):
    shutil.copy2(ROOT/'tools'/script,tools/script)
    (app/'main.py').write_text('from pathlib import Path\nimport runpy\nrunpy.run_path(str(Path(__file__).resolve().parent/"tools"/'+repr(script)+'),run_name="__main__")\n','utf-8')
    p=subprocess.run([str(stage/'EncoLite.exe'),*args],timeout=timeout,capture_output=True)
    if p.returncode:
        detail=p.stderr.decode(errors='replace')
        raise RuntimeError(f'{script} {args}: exit={p.returncode}, {detail}')

try:
    for script,filename in (('verify_desktop.py','desktop-interactions.json'),('verify_window_lifetime.py','window-lifetime.json')):
        run(script)
        result=json.loads((app/'verification'/filename).read_text('utf-8'))
        shutil.copy2(app/'verification'/filename,ROOT/'verification'/('native-'+filename))
        assert result['result']=='PASS',result
        report['checks'].extend(result['checks'])
        print('PASS',script,flush=True)
    for phase in ('write','read','write-max','read-max'):run('verify_persistence.py',(phase,))
    report['checks'].append('window placement, theme, page and maximized state persist across four native processes')
    print('PASS native persistence',flush=True)
    run('verify_native_read.py',timeout=35)
    result=json.loads((app/'verification/native-bluetooth.json').read_text('utf-8'))
    shutil.copy2(app/'verification/native-bluetooth.json',ROOT/'verification/native-bluetooth.json')
    report['bluetooth']=result
    assert result['result']=='PASS',result
    report['checks'].append('packaged runtime completes real X3 Bluetooth handshake and reads actual state')
except Exception as error:
    report['errors'].append(repr(error))
finally:
    report['result']='FAIL' if report['errors'] else 'PASS'
    (ROOT/'verification/native-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    (app/'main.py').write_bytes(original)
    shutil.rmtree(tools)
    shutil.rmtree(app/'verification')
    if report['errors']:raise SystemExit(1)
