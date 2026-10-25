"""Exercise real window lifetime/activation with production dismissal policy.

Only our own app windows and UI callbacks are used; no earphone writes.
"""
from pathlib import Path
from datetime import timedelta
import sys,os,time,json,ctypes as C
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
d=Desktop(ROOT,c,tray_enabled=False,test_mode=False)
d._notifications_enabled=False
# A tiny, unowned window in this test process keeps foreground permission
# while main is minimized, as a user-invoked launcher/tray action would.
# Otherwise Windows rightly refuses a timer in a background app stealing focus.
probe_class=f'EncoLiteActivationProbe-{os.getpid()}'
probe_proc=shell.WNDPROC(lambda hwnd,msg,wp,lp:shell.DefWindowProc(hwnd,msg,wp,lp))
probe_wc=shell.WndClass(proc=probe_proc,instance=shell.GetModuleHandle(None),name=probe_class)
assert shell.RegisterClass(C.byref(probe_wc))
probe=shell.CreateWindow(0x80,probe_class,'Enco Lite activation probe',0x80000000,
                        0,0,1,1,None,None,probe_wc.instance,None)
assert probe
report={'checks':[],'errors':[],'activation_trace':[]};stage=0;deadline=0;quick=None
started=time.monotonic();first_handle=True;activations=[]
original_style=shell.style_window;original_activate=shell.activate_window
def style(title,**kwargs):
 global first_handle
 if title==d.MAIN_TITLE and first_handle:
  first_handle=False
  return None  # Model the native HWND appearing after Slint show() returns.
 return original_style(title,**kwargs)
def activate(hwnd):
 activations.append(hwnd)
 result=original_activate(hwnd)
 report['activation_trace'].append({'stage':stage,'target':hwnd,'accepted':result,
     'foreground':shell.GetForegroundWindow(),'attempt':d._main_activation_attempts})
 return result
shell.style_window=style;shell.activate_window=activate
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def tick():
 global stage,deadline,quick
 try:
  if time.monotonic()-started>20:raise TimeoutError(f'stage {stage}')
  if stage==0:
   if not d.main_hwnd or d._main_activation_pending:return
   assert shell.GetForegroundWindow()==d.main_hwnd,f'foreground={shell.GetForegroundWindow()}, main={d.main_hwnd}'
   check('main opens in foreground when initial native handle is delayed')
   d.show_quick();stage=1
  elif stage==1:
   if not d.quick_hwnd:return
   quick=d.quick
   assert original_activate(d.main_hwnd)
   deadline=time.monotonic()+5.2;stage=2
  elif stage==2:
   assert d.quick is quick,'Manual quick controls dismissed after losing focus'
   if time.monotonic()<deadline:return
   check('manual quick controls survive over five seconds without focus')
   quick.dismiss();assert d.quick is None
   check('close button releases manual quick controls')
   d.show_quick();d.hide_main();stage=3
  elif stage==3:
   if not d.quick_hwnd:return
   d.quick.show_main();stage=4
  elif stage==4:
   if not d.main_hwnd or d._main_activation_pending:return
   assert d.quick is None and shell.GetForegroundWindow()==d.main_hwnd
   check('open-main callback releases quick controls and foregrounds recreated main')
   shell.ShowWindow(probe,5)
   assert original_activate(probe)
   shell.ShowWindow(d.main_hwnd,7)  # SW_SHOWMINNOACTIVE: keep probe foreground.
   stage=5
  elif stage==5:
   if not shell.IsIconic(d.main_hwnd):return
   assert shell.GetForegroundWindow()==probe,'Test foreground permission was lost before open-main'
   d.show_main();stage=6
  elif stage==6:
   if shell.IsIconic(d.main_hwnd) or d._main_activation_pending:return
   assert shell.GetForegroundWindow()==d.main_hwnd,f'foreground={shell.GetForegroundWindow()}, main={d.main_hwnd}, minimized={d.main.window_minimized}, attempts={d._main_activation_attempts}'
   check('open-main restores minimized main and gives it foreground')
   d.main.window_maximized=True;stage=7
  elif stage==7:
   if not shell.IsZoomed(d.main_hwnd):return
   d.show_main();stage=8
  else:
   if d._main_activation_pending:return
   assert shell.IsZoomed(d.main_hwnd)
   assert shell.GetForegroundWindow()==d.main_hwnd
   check('repeated open-main preserves maximized state and foreground')
   d.quit()
 except Exception as error:report['errors'].append(f'stage {stage}: {error!r}');d.quit()
d.show_main();timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=150),tick)
try:native.run_event_loop()
finally:
 timer.stop();shell.style_window=original_style;shell.activate_window=original_activate
 c.close();d.close()
 shell.DestroyWindow(probe);shell.UnregisterClass(probe_class,probe_wc.instance)
 report['result']='FAIL' if report['errors'] else 'PASS'
 (ROOT/'verification/window-lifetime.json').write_text(json.dumps(report,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
