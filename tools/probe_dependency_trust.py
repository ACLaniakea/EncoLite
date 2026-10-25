"""Read-only native-module loading probes; never changes Windows trust settings."""
from pathlib import Path
import json,subprocess,sys,os
ROOT=Path(__file__).resolve().parents[1]
python=ROOT/'.tools/python-3.13.17-embed-amd64/python.exe'
results=[]
for version in ('1.18.0b1','1.17.1b2','1.16.1b1'):
    package=ROOT/'.tools/slint-candidates'/version/'package'
    code='import sys,os; sys.path.append('+repr(str(package))+'); dlls=os.add_dll_directory('+repr(str(ROOT/'dist/EncoLite/_internal'))+'); import slint; print(slint.__file__)'
    p=subprocess.run([str(python),'-c',code],capture_output=True,timeout=25)
    result={'slint':version,'host':str(python),'exit':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')}
    results.append(result)
    print(json.dumps(result,ensure_ascii=True),flush=True)
(ROOT/'verification/dependency-trust.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')
