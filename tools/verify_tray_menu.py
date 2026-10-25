"""Drive our tray callback once per selection; no desktop input automation."""
from pathlib import Path
from datetime import timedelta
import os,sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
os.environ.setdefault('SLINT_BACKEND','winit-software')
import slint
from slint._native import native
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.desktop import Desktop
from encolite import windows_shell as shell
c=Controller(session=DemoSession(),dispatch=native.invoke_from_event_loop)
d=Desktop(ROOT,c,test_mode=True)
report={'checks':[],'errors':[]};stage=0;selection=1;menus=[];writes=[];dispatches=[]
original_track=shell.TrackPopupMenu
shell.TrackPopupMenu=lambda *args:(menus.append(selection) or selection)
d.tray.on_noise=writes.append
original_defer=d.tray.defer
def defer(fn):dispatches.append(fn);original_defer(fn)
d.tray.defer=defer
def right_click():d.tray._wndproc(d.tray.hwnd,0x8001,0,0x7B)
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def tick():
 global stage,selection
 try:
  if stage==0:
   d.tray.click_timer.start(slint.TimerMode.SingleShot,timedelta(seconds=3),lambda:None)
   right_click();right_click();stage=1
  elif stage==1:
   assert d.quick is not None and len(menus)==1 and len(dispatches)==1
   assert not d.tray.click_timer.running
   check('one quick-menu selection opens immediately; duplicate context event coalesced')
   selection=2;right_click();stage=2
  elif stage==2:
   assert d.main is not None and d.quick is None
   assert len(dispatches)==2
   check('one main-menu selection opens immediately')
   selection=10;right_click();stage=3
  elif stage==3:
   assert len(writes)==1 and len(dispatches)==3
   check('one noise-menu selection issues one action')
   selection=0;right_click();stage=4
  else:
   assert d.main is not None and not d.tray._menu_pending
   check('dismissed menu leaves view and next menu usable')
   d.quit()
 except Exception as error:report['errors'].append(repr(error));d.quit()
timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=300),tick)
try:native.run_event_loop()
finally:
 timer.stop();shell.TrackPopupMenu=original_track;c.close();d.close()
 report['result']='FAIL' if report['errors'] else 'PASS'
 (ROOT/'verification/tray-menu.json').write_text(json.dumps(report,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
