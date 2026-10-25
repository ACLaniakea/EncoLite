"""Inspect only our own window regions, including after a resize."""
from pathlib import Path
import sys,os,json,ctypes as C
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
PtInRegion=shell.api(shell.gdi,'PtInRegion',W.BOOL,W.HANDLE,C.c_int,C.c_int)
GetRgnBox=shell.api(shell.gdi,'GetRgnBox',C.c_int,W.HANDLE,C.POINTER(W.RECT))
report={'checks':[],'errors':[]};stage=0

def inspect(title):
 hwnd=shell.window_handle(title);assert hwnd
 rect=W.RECT();shell.GetWindowRect(hwnd,C.byref(rect));width=rect.right-rect.left;height=rect.bottom-rect.top
 region=shell.CreateRoundRectRgn(0,0,1,1,1,1)
 try:
  kind=GetWindowRgn(hwnd,region)
  assert kind==3,f'Expected rounded complex region, got {kind} for {title}'
  assert not PtInRegion(region,0,0),'Corner must be outside window'
  assert PtInRegion(region,width//2,height//2),'Center must remain inside'
  box=W.RECT();GetRgnBox(region,C.byref(box))
  assert abs(box.right-width)<=1 and abs(box.bottom-height)<=1,(width,height,box.right,box.bottom)
  report['checks'].append({'title':title,'width':width,'height':height,'rounded':True})
 finally:shell.DeleteObject(region)

def tick():
 global stage
 try:
  if stage==0:
   inspect(desktop.MAIN_TITLE);shell.SetWindowPos(shell.window_handle(desktop.MAIN_TITLE),None,0,0,1840,1360,0x16);stage=1
  elif stage==1:
   inspect(desktop.MAIN_TITLE);desktop.show_quick();stage=2
  else:
   inspect(desktop.QUICK_TITLE);desktop.quit()
 except Exception as e:report['errors'].append(repr(e));desktop.quit()

desktop.show_main();timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=500),tick)
try:native.run_event_loop()
finally:
 timer.stop();controller.close();desktop.close()
 report['result']='FAIL' if report['errors'] else 'PASS'
 (ROOT/'verification/rounded-windows.json').write_text(json.dumps(report,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
