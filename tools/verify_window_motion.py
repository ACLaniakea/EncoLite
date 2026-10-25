"""Inspect actual HWND opacity during native window transitions, not only DOM animation."""
from pathlib import Path
import ctypes as C,json,os,sys,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['ENCOLITE_DATA_DIR']=str(ROOT/'.install-test/native-motion')
from encolite.web_desktop import Desktop
from encolite import windows_shell as s
s.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
app=Desktop(ROOT);messages=[];report={'checks':[],'errors':[],'samples':[]}
app.send=lambda kind,**values:messages.append({'type':kind,**values})
state={'theme_mode':'light','fast_mode':False,'system_motion':True,'connected':True,'model_name':'OnePlus Buds Pro 3','noise':'smart','can_anc':True,'can_transparency':True,'can_off':True,
 'noise_options':[{'key':'smart','name':'智能降噪'},{'key':'deep','name':'深度降噪'},{'key':'off','name':'关闭'},{'key':'transparency','name':'通透'}]}
app.receive({'type':'state','fixture':True,'state':state,'preferences':{}})
get_alpha=s.api(s.user,'GetLayeredWindowAttributes',W.BOOL,W.HWND,C.POINTER(W.DWORD),C.POINTER(C.c_ubyte),C.POINTER(W.DWORD))
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def fail(error):report['errors'].append(str(error));app.quit()
def safe(callback):
 def run():
  try:callback()
  except Exception:fail(traceback.format_exc())
 return run
def sample(window,phase):
 color=W.DWORD();alpha=C.c_ubyte();flags=W.DWORD();ok=get_alpha(window.hwnd,C.byref(color),C.byref(alpha),C.byref(flags))
 data={'kind':window.kind,'phase':phase,'layered':bool(s.GetWindowLong(window.hwnd,-20)&0x80000),'alpha':alpha.value if ok else None,'timer':bool(window.native_timer and window.native_timer.running)}
 report['samples'].append(data);return data

def begin(index=0):
 kind=('main','quick','notice')[index];app.show(kind)
 def ready():app.later(.025,safe(lambda:opening(index)))
 app.when_ready(kind,safe(ready))
def opening(index):
 window=app.windows[('main','quick','notice')[index]];data=sample(window,'open')
 assert data['layered'] and data['alpha'] is not None and 0<=data['alpha']<255 and data['timer'],data
 check(window.kind+' opens with actual HWND alpha, including the window background')
 app.later(.32,safe(lambda:opened(index,window)))
def opened(index,window):
 data=sample(window,'idle');assert not data['layered'] and not data['timer'] and window.native_alpha==255,data
 check(window.kind+' removes its native animation timer and layered style when idle')
 if index==0 and not getattr(window,'restoration_checked',False):
  window.restoration_checked=True;s.ShowWindow(window.hwnd,6);window.activate()
  app.later(.045,safe(lambda:restoring(index,window)));return
 window.close(exiting=False);app.later(.065,safe(lambda:closing(index,window)))
def restoring(index,window):
 data=sample(window,'restore');assert data['layered'] and 0<=data['alpha']<255,data
 check('restoring the minimized main window fades the whole HWND from transparency')
 app.later(.32,safe(lambda:opened(index,window)))
def closing(index,window):
 data=sample(window,'close');assert not window.closed and data['layered'] and 0<data['alpha']<255,data
 check(window.kind+' closes with actual HWND alpha rather than an abrupt frame removal')
 if index==0:
  token=window.close_serial;window.activate();app.window_message(window,{'type':'window','name':'dismissed','token':token})
  app.later(.32,safe(lambda:reopened(index,window)))
 else:app.later(.22,safe(lambda:closed(index,window)))
def reopened(index,window):
 assert not window.closed and not window.closing and window.native_alpha==255 and not window.layered
 check('reopening during fade-out restores opacity and ignores the previous close acknowledgement')
 window.close(exiting=False);app.later(.3,safe(lambda:closed(index,window)))
def closed(index,window):
 assert window.closed and not window.native_timer.running
 if index<2:begin(index+1)
 else:speed()
def speed():
 state['fast_mode']=True;app.receive({'type':'state','fixture':True,'state':state,'preferences':{}})
 app.show('main');app.when_ready('main',safe(speed_ready))
def speed_ready():
 window=app.windows['main'];assert not window.layered and window.native_timer is None
 check('speed mode shows the native window immediately without allocating an animation timer')
 window.close(exiting=False);assert window.closed
 state.update(fast_mode=False,system_motion=False);app.receive({'type':'state','fixture':True,'state':state,'preferences':{}})
 app.show('quick');app.when_ready('quick',safe(reduced))
def reduced():
 window=app.windows['quick'];assert not window.layered and window.native_timer is None
 check('system reduced motion also bypasses the entire native transition')
 window.close(exiting=False);assert window.closed
 state['system_motion']=True;app.receive({'type':'state','fixture':True,'state':state,'preferences':{}})
 app.show('main');app.when_ready('main',safe(interrupt))
def interrupt():
 window=app.windows['main'];state['fast_mode']=True
 app.receive({'type':'state','fixture':True,'state':state,'preferences':{}})
 assert not window.layered and window.native_alpha==255 and not window.native_timer.running
 check('turning on speed mode during a transition immediately restores a fully opaque surface')
 app.quit()
begin();app.later(25,lambda:fail('native motion verification timeout'))
try:app.loop.run()
finally:
 app.quit()
 if app.environment:app.environment.close()
 s.DestroyWindow(app.owner)
 report['result']='FAIL' if report['errors'] else 'PASS'
 folder=ROOT/'verification/native-motion';folder.mkdir(parents=True,exist_ok=True)
 (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
