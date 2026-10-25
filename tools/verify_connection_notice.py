"""Verify connection notifications on the actual paired X3; no setting writes."""
from pathlib import Path
import sys,os,time,json
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
os.environ.setdefault('SLINT_BACKEND','winit-software')
import slint
from slint._native import native
from datetime import timedelta
from encolite.controller import Controller
from encolite.desktop import Desktop
controller=Controller(dispatch=native.invoke_from_event_loop)
desktop=Desktop(ROOT,controller,test_mode=True)
desktop._notifications_enabled=True
desktop.show_main();controller.start()
report={'checks':[],'errors':[]};stage=0;notice=None;started=time.monotonic()

def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def tick():
 global stage,notice
 try:
  if time.monotonic()-started>30:raise RuntimeError(controller.status)
  if controller.busy:return
  s=controller.session
  if stage==0:
   if not s.ready:return
   assert desktop.notice and desktop.notice.model_name==s.device_name
   assert '左耳' in desktop.notice.battery_text
   check('real handshake and battery produce connection notice')
   notice=desktop.notice;desktop._notice_hover(True)
   controller.refresh();stage=1
  elif stage==1:
   assert desktop.notice is notice
   check('state refresh never repeats real connection notice')
   controller.change_connection();stage=2
  elif stage==2:
   assert not s.connected and desktop.notice is None
   check('disconnect releases stale connection notice')
   controller.change_connection();stage=3
  else:
   assert s.ready and desktop.notice is not None
   check('real reconnection produces one fresh notice')
   desktop.quit()
 except Exception as error:report['errors'].append(f'stage {stage}: {error!r}');desktop.quit()

timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=200),tick)
try:native.run_event_loop()
finally:
 timer.stop();controller.close();desktop.close()
 report['result']='FAIL' if report['errors'] else 'PASS'
 (ROOT/'verification/connection-notice-live.json').write_text(json.dumps(report,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
