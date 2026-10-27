"""Check real Qt HWND transitions, deletion, restoration and window policies."""
from pathlib import Path
import ctypes as C,json,sys,time,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'.tools/qt-probe/packages')]
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import Qt,QTimer
from shiboken6 import isValid
from encolite.qt_desktop import Desktop
from encolite import windows_shell as s
from ctypes import wintypes as W
app=Desktop(ROOT,read_pipe=False);report={'checks':[],'errors':[],'alpha':[]};dead=[]
state={'connected':True,'model_name':'OPPO Enco X3','noise_options':[],'dark':False,'fast_mode':False,'system_motion':True}
get_alpha=s.api(s.user,'GetLayeredWindowAttributes',W.BOOL,W.HWND,C.POINTER(W.DWORD),C.POINTER(C.c_ubyte),C.POINTER(W.DWORD))
def publish():app.receive({'type':'state','state':state,'preferences':{}})
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def safe(fn):
 def run():
  try:fn()
  except Exception:report['errors'].append(traceback.format_exc());app.quit()
 return run
def later(ms,fn):QTimer.singleShot(ms,safe(fn))
def until(predicate,fn,label,timeout=2500):
 deadline=time.monotonic()+timeout/1000
 def poll():
  if predicate():fn()
  elif time.monotonic()>=deadline:raise TimeoutError(label)
  else:later(10,poll)
 later(0,poll)
def capture(window,phase):
 color=W.DWORD();alpha=C.c_ubyte();flags=W.DWORD();hwnd=int(window.winId())
 ok=get_alpha(hwnd,C.byref(color),C.byref(alpha),C.byref(flags))
 row={'phase':phase,'opacity':window.property('displayOpacity'),'native_alpha':alpha.value if ok else None,'caption':not app.material.native.caption_hidden(hwnd) if window.property('systemFrame') else bool(s.GetWindowLong(hwnd,-16)&0x00C00000)}
 report['alpha'].append(row);assert not row['caption'];return row
def start():
 win=app.windows['main'];capture(win,'opening')
 until(lambda:bool(win.property('presented')) and .01<win.property('displayOpacity')<1,lambda:opening(win),'first frame and opening animation')
def opening(win):
 assert 0<win.property('displayOpacity')<1,capture(win,'open-mid')
 capture(win,'open-mid')
 check('window content fades in with no system caption')
 until(lambda:win.property('displayOpacity')==1,lambda:opened(win),'opening animation completes')
def opened(win):
 assert win.property('displayOpacity')==1
 app.close_view('main',exiting=False);until(lambda:not win.property('surfaceReady') and .08<win.property('displayOpacity')<.95,lambda:closing(win),'complete-surface fade after glass cover')
def closing(win):
 row=capture(win,'close-mid');assert 0<row['opacity']<1,row
 assert row['native_alpha'] is None,row
 check('complete surface opacity changes during close without a native shadow halo')
 app.show('main');later(250,lambda:cancelled(win))
def cancelled(win):
 assert app.windows['main'] is win and win.property('displayOpacity')==1 and not win.property('closingUi')
 check('reopen cancels the close transition and retains the same window')
 win.showMinimized();app.show('main');later(250,lambda:maximized(win))
def maximized(win):
 assert win.windowState()!=Qt.WindowMinimized;check('main-window activation restores a minimized window')
 win.setGeometry(100,100,820,600);later(50,lambda:maximize(win))
def maximize(win):
 win.showMaximized();later(120,lambda:maxclose(win))
def maxclose(win):
 assert win.windowState()==Qt.WindowMaximized
 state['fast_mode']=True;publish();app.close_view('main',exiting=False)
 saved=next(m for m in reversed(app.messages) if m.get('name')=='save_window')
 assert saved['args'][1]==[100,100,820,600,True],saved
 check('maximized close saves the normal placement and maximized flag')
 dead.append(win);cycle(0)
def cycle(index):
 if index==8:return finish()
 kind='quick' if index%2==0 else 'main';app.show(kind)
 def ready():
  win=app.windows[kind];assert win.property('displayOpacity')==1
  app.close_view(kind,exiting=False);dead.append(win);later(50,lambda:cycle(index+1))
 later(100,ready)
def finish():
 assert all(not isValid(win) for win in dead)
 check('nine closed QML windows are destroyed rather than retained')
 state.update(fast_mode=False,system_motion=False);publish();app.show('notice');later(150,notice)
def notice():
 win=app.windows['notice'];assert win.property('displayOpacity')==1
 assert s.GetWindowLong(int(win.winId()),-20)&0x08000000
 check('connection notice does not activate and honors reduced motion')
 app.quit()
publish();app.show('main');later(20,start);later(12000,lambda:(_ for _ in ()).throw(RuntimeError('window test timeout')))
try:app.run()
finally:
 report['result']='FAIL' if report['errors'] else 'PASS'
 out=ROOT/'verification/qt-windows';out.mkdir(exist_ok=True,parents=True)
 (out/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
