"""Regression-check only this application's chrome and desktop interactions."""
from pathlib import Path
import sys,os,json,time,ctypes as C
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
os.environ.setdefault('SLINT_BACKEND','winit-software')
import slint
from slint._native import native
from datetime import timedelta
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.desktop import Desktop
from encolite import windows_shell as shell
controller=Controller(session=DemoSession(),dispatch=native.invoke_from_event_loop)
desktop=Desktop(ROOT,controller,test_mode=True)
GetWindowRgn=shell.api(shell.user,'GetWindowRgn',C.c_int,W.HWND,W.HANDLE)
GetRgnBox=shell.api(shell.gdi,'GetRgnBox',C.c_int,W.HANDLE,C.POINTER(W.RECT))
dwm=C.WinDLL('dwmapi');getter=shell.api(dwm,'DwmGetWindowAttribute',C.c_long,W.HWND,W.DWORD,C.c_void_p,W.DWORD)
report={'checks':[],'errors':[]};stage=0;placement=None;quick_before=None;dismiss_deadline=0

def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def inspect(title,tool=False):
 hwnd=shell.window_handle(title);assert hwnd
 installed=shell.api(shell.controls,'GetWindowSubclass',W.BOOL,W.HWND,shell.SUBCLASSPROC,C.c_size_t,C.POINTER(C.c_size_t))
 reference=C.c_size_t()
 assert installed(hwnd,shell._borderless_proc,1,C.byref(reference)),'Nonclient paint guard absent'
 send=shell.api(shell.user,'SendMessageW',shell.LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
 assert send(hwnd,0x85,1,0)==0,'Native rim paint was not suppressed'
 style=shell.GetWindowLong(hwnd,-16);extended=shell.GetWindowLong(hwnd,-20)
 assert not style&0x00C00000,f'Native caption remains: {style:X}'
 assert not extended&(0x200|0x20000),f'Native client edge remains: {extended:X}'
 if tool:assert extended&0x80 and not extended&0x40000
 color=C.c_uint32(0xFFFFFFFE)
 setter=shell.api(dwm,'DwmSetWindowAttribute',C.c_long,W.HWND,W.DWORD,C.c_void_p,W.DWORD)
 assert setter(hwnd,34,C.byref(color),4)==0,'DWM border suppression rejected'
 region=shell.CreateRoundRectRgn(0,0,1,1,1,1)
 try:
  assert GetWindowRgn(hwnd,region)==3,'No rounded region'
  rect=W.RECT();shell.GetWindowRect(hwnd,C.byref(rect))
  client=W.RECT();shell.GetClientRect(hwnd,C.byref(client))
  assert (client.right,client.bottom)==(rect.right-rect.left,rect.bottom-rect.top),'Native frame consumes client space'
 finally:shell.DeleteObject(region)

def tick():
 global stage,placement,quick_before,dismiss_deadline
 try:
  if stage==0:
   inspect(desktop.MAIN_TITLE);check('main has no native rim')
   desktop.main.page=5
   shell.SetWindowPos(desktop.main_hwnd,None,120,100,1760,1300,0x14);stage=1
  elif stage==1:
   placement=shell.window_placement(desktop.MAIN_TITLE)
   inspect(desktop.MAIN_TITLE);desktop.show_quick();stage=2
  elif stage==2:
   inspect(desktop.QUICK_TITLE,tool=True);check('quick has no native rim or taskbar button')
   desktop.show_main();stage=3
  elif stage==3:
   inspect(desktop.MAIN_TITLE)
   assert desktop.main.page==5
   actual=shell.window_placement(desktop.MAIN_TITLE)
   assert actual[:4]==placement[:4],(placement,actual)
   check('window switch preserves page, position and size')
   desktop.main.window_maximized=True;stage=4
  elif stage==4:
   assert desktop.main.window_maximized
   desktop.show_main();stage=5
  elif stage==5:
   assert desktop.main.window_maximized,'Repeated activation restored maximized window'
   check('activation preserves maximized state')
   desktop.main.window_maximized=False
   desktop._notifications_enabled=True
   controller.session.transport.connected=False;controller.sync()
   controller.session.transport.connected=True;controller.sync();stage=6
  elif stage==6:
   assert desktop.notice is not None
   inspect(desktop.NOTICE_TITLE,tool=True)
   assert shell.GetForegroundWindow()==desktop.main_hwnd,'Notice stole foreground'
   check('connection notice has no border and preserves foreground')
   notice=desktop.notice;controller.sync();assert desktop.notice is notice
   desktop._notice_hover(True);assert not desktop._notice_timer.running
   desktop._notice_hover(False);assert desktop._notice_timer.running
   check('refresh does not repeat notice; hover pauses dismissal')
   notice.open_controls();assert desktop.notice is None and desktop.quick is not None
   check('notice promotes to shared quick controls')
   quick_before=desktop.quick
   desktop.tray._wndproc(desktop.tray.hwnd,0x8002,1,0)
   stage=7
  elif stage==7:
   assert desktop.quick is quick_before
   check('explicit quick-open request never toggles it closed')
   desktop.quick.dismiss()
   assert desktop.quick is None
   check('explicit dismissal releases the manual quick view')
   controller.change_connection_popup(False)
   controller.session.transport.connected=False;controller.sync()
   controller.session.transport.connected=True;controller.sync()
   assert desktop.notice is None,'Notice appeared despite disabled preference'
   check('disabled connection notice stays closed')
   controller.change_connection_popup(True)
   assert desktop.notice is None,'Enabling preference replayed old notice'
   controller.session.transport.connected=False;controller.sync()
   controller.session.transport.connected=True;controller.sync()
   assert desktop.notice,'Fresh connection failed to show notice'
   desktop._notice_hover(False)
   dismiss_deadline=time.monotonic()+3.6;stage=8
  elif stage==8 and time.monotonic()>=dismiss_deadline:
   assert desktop.notice is None and not desktop._notice_timer.running
   check('connection notice automatically releases after timeout')
   desktop.quit()
 except Exception as error:
  report['errors'].append(f'stage {stage}: {error!r}');desktop.quit()

desktop.show_main();timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=450),tick)
try:native.run_event_loop()
finally:
 timer.stop();controller.close();desktop.close()
 report['result']='FAIL' if report['errors'] else 'PASS'
 (ROOT/'verification/desktop-interactions.json').write_text(json.dumps(report,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
