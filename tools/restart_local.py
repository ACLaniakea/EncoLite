"""Restart only this workspace's Enco Lite process after a source update."""
from pathlib import Path
import sys,subprocess,ctypes,time,os
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
import psutil
main=(ROOT/'main.py').resolve()
for p in psutil.process_iter(['pid','name','cmdline']):
 try:
  args=p.info['cmdline'] or []
  if p.pid==psutil.Process().pid or not p.info['name'].lower().startswith('python'):continue
  if not any(Path(a).resolve()==main for a in args[1:] if not a.startswith('--')):continue
  # Migrate visible placement from the prior version before terminating it.
  from ctypes import wintypes as W
  from encolite.preferences import read_preferences,write_preferences
  u=ctypes.WinDLL('user32',use_last_error=True)
  u.FindWindowW.argtypes=[W.LPCWSTR,W.LPCWSTR];u.FindWindowW.restype=W.HWND
  u.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
  u.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
  u.IsIconic.argtypes=[W.HWND];u.IsZoomed.argtypes=[W.HWND]
  owner=W.DWORD()
  helper=u.FindWindowW('EncoLiteTray','Enco Lite tray')
  if helper:
   u.GetWindowThreadProcessId(helper,ctypes.byref(owner))
  if helper and owner.value==p.pid:
   u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
   u.PostMessageW(helper,0x8002,3,0)
   try:
    p.wait(5)
    print('Closed previous Enco Lite instance with preferences saved',p.pid,flush=True)
    continue
   except psutil.TimeoutExpired:pass
  prefs=Path(os.environ['APPDATA'])/'EncoLite/preferences.json'
  data=read_preferences(prefs)
  for title,key in (('Enco Lite · OPPO 耳机助手','main_window'),('Enco Lite · 快捷控制','quick_window')):
   hwnd=u.FindWindowW(None,title);owner=W.DWORD()
   if not hwnd:continue
   u.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
   if owner.value!=p.pid or u.IsIconic(hwnd):continue
   rect=W.RECT()
   if u.GetWindowRect(hwnd,ctypes.byref(rect)):
    saved=data.get(key,{})
    if not isinstance(saved,dict):saved={}
    saved['bounds']=[rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top,bool(u.IsZoomed(hwnd))]
    data[key]=saved
  write_preferences(prefs,data)
  p.terminate();p.wait(5);print('Stopped previous Enco Lite instance',p.pid,flush=True)
 except (psutil.NoSuchProcess,psutil.AccessDenied,OSError):pass
if '--stop-only' not in sys.argv:
 pythonw=Path(sys.executable).with_name('pythonw.exe')
 p=subprocess.Popen([str(pythonw),str(main)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 time.sleep(2)
 assert p.poll() is None,'Enco Lite exited unexpectedly'
 print('Started updated Enco Lite',p.pid,flush=True)
