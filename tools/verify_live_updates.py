"""Read-only X3 checks for visible/tray polling and current charging UI."""
from pathlib import Path
from datetime import timedelta
import os,sys,time,json
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
os.environ.setdefault('SLINT_BACKEND','winit-software')
import slint
from slint._native import native
from encolite.controller import Controller
from encolite.desktop import Desktop
c=Controller(dispatch=native.invoke_from_event_loop)
d=Desktop(ROOT,c,test_mode=True);d.show_quick();c.start()
report={'checks':[],'errors':[],'reads':[]};stage=0;started=time.monotonic();deadline=0;before=0
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def tick():
 global stage,deadline,before
 try:
  if time.monotonic()-started>35:raise RuntimeError(c.status)
  s=c.session
  if c.busy:return
  if stage==0:
   if not s.ready:return
   assert {1,2,3}.issubset(s.registered_events),s.registered_events
   check('X3 battery, wear and ANC notifications subscribed')
   report.update(model=s.device_name,firmware=s.firmware)
   original=s.request
   def record(command,payload=b'',**kwargs):
    result=original(command,payload,**kwargs)
    report['reads'].append({'command':f'{command:04X}','time':round(time.monotonic()-started,3)})
    return result
   s.request=record;before=len(report['reads']);deadline=time.monotonic()+5;stage=1
  elif stage==1 and time.monotonic()>=deadline and not c._refreshing:
   commands=[r['command'] for r in report['reads'][before:]]
   assert '0106' in commands and '010C' in commands,commands
   assert not c.busy and d.quick.can_off
   for key in ('left','right','case'):
    b=s.battery.get(key)
    assert getattr(d.quick,key+'_value')==(f'{b.percent}%' if b else '—')
    assert getattr(d.quick,key+'_charging')==bool(b and b.charging)
   check('background poll updates real quick UI without disabling controls')
   check('battery text and charging icon match separate real device fields')
   d.close_quick();before=len(report['reads']);deadline=time.monotonic()+12;stage=2
  elif stage==2 and time.monotonic()>=deadline and not c._refreshing:
   commands=[r['command'] for r in report['reads'][before:]]
   assert '0106' in commands,commands
   assert all(command in ('0106','0112','0132') for command in commands),commands
   check('tray lowers activity and retains battery fallback')
   d.show_quick();before=len(report['reads']);deadline=time.monotonic()+1;stage=3
  elif stage==3 and time.monotonic()>=deadline and not c._refreshing:
   assert '010C' in [r['command'] for r in report['reads'][before:]]
   assert s.ready and d.quick.connected
   check('reopening quick controls immediately fetches current state')
   d.quit()
 except Exception as error:report['errors'].append(f'stage {stage}: {error!r}');d.quit()
timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=100),tick)
try:native.run_event_loop()
finally:
 timer.stop();c.close();d.close()
 report['result']='FAIL' if report['errors'] else 'PASS'
 (ROOT/'verification/live-updates.json').write_text(json.dumps(report,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
