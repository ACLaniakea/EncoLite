"""Check the actual double-click entry opens exactly one production process."""
from pathlib import Path
import os,sys,time,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.build-deps'))
import psutil
os.startfile(str(ROOT.parent/'启动 Enco Lite.cmd'))
time.sleep(3)
found=[]
for p in psutil.process_iter(['pid','name','cmdline']):
 try:
  if not p.info['name'].lower().startswith('python'):continue
  if any(Path(arg).resolve()==(ROOT/'main.py').resolve() for arg in (p.info['cmdline'] or [])[1:] if not arg.startswith('--')):
   found.append(p.pid)
 except (OSError,psutil.Error):pass
report={'result':'PASS' if len(found)==1 else 'FAIL','production_instances':len(found),'pids':found}
(ROOT/'verification/double-click-launch.json').write_text(json.dumps(report,indent=2),'utf-8')
print(json.dumps(report),flush=True)
assert len(found)==1,report
