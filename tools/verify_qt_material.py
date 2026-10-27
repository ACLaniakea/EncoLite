"""Exercise native Desktop Acrylic and its opaque fallback on owned Qt windows."""
from pathlib import Path
import ctypes as C,json,os,sys,traceback
ROOT=Path(__file__).resolve().parents[1];TARGET=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT
sys.path[:0]=[str(TARGET),str(TARGET/'qt' if TARGET!=ROOT else ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8')
from PySide6.QtCore import QTimer,qInstallMessageHandler,QObject,QMetaObject
from PySide6.QtQuick import QQuickItem
from encolite.qt_desktop import Desktop
OUT=ROOT/'verification/qt-material';OUT.mkdir(exist_ok=True,parents=True)
TAG=os.environ.get('ENCOLITE_MATERIAL_TAG','default')
report={'checks':[],'errors':[],'warnings':[],'frames':[],'scope':'Owned Qt windows, native Acrylic state and readable DWM corner attributes, non-layered native client area and QML surfaces; prototype contour also confirmed by user. No earbud writes'}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(TARGET,read_pipe=False)
get=C.windll.dwmapi.DwmGetWindowAttribute;get.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_uint];get.restype=C.c_long
state={'connected':False,'noise_options':[],'glass_effect':True,'system_transparency':True,'fast_mode':False,
       'system_motion':False,'dark':False,'fast_launch':True}
def publish():app.receive({'type':'state','state':dict(state),'preferences':{}})
def attr(win,key):
 value=C.c_int();assert get(int(win.winId()),key,C.byref(value),C.sizeof(value))==0
 return value.value
def later(ms,fn):
 def run():
  try:fn()
  except Exception:report['errors'].append(traceback.format_exc());app.quit()
 QTimer.singleShot(ms,run)
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def sample(win):
 surface=win.findChild(QQuickItem,'windowSurface')
 return {'ratio':win.devicePixelRatio(),'kind':win.property('kind'),'native':bool(win.property('nativeGlass')),'backdrop':bool(app.material.states.get(int(win.winId()),(False,))[-1]),
         'corner':attr(win,33),'alpha':surface.property('color').alphaF(),'radius':surface.property('radius')}
def cycle(index=0):
 if index==6:return toggles()
 kind=('main','quick','notice')[index%3];state['dark']=index>=3;publish();app.show(kind)
 def shown():
  win=app.windows[kind];row=sample(win);report['frames'].append(row)
  assert row['native'] and row['backdrop'] is True and row['corner']==3,row
  assert 0.1<row['alpha']<.9 and row['radius']==0,row
  image=win.screen().grabWindow(int(win.winId()));assert not image.isNull()
  image.save(str(OUT/(kind+('-dark' if state['dark'] else '-light')+'.png')))
  check(kind+(': dark' if state['dark'] else ': light')+' native Acrylic, translucent surface and matching rounded contour')
  app.close_view(kind,exiting=False,animate=False);later(70,lambda:cycle(index+1))
 later(300,shown)
def toggles():
 state.update(dark=False);publish();app.show('main');later(300,disable)
def disable():
 state['glass_effect']=False;publish();later(120,disabled)
def disabled():
 row=sample(app.windows['main']);assert not row['native'] and row['backdrop'] is False and row['alpha']==1 and row['radius']==0,row
 check('turning glass off restores an opaque surface while preserving the same native corners')
 state.update(glass_effect=True,fast_mode=True);publish();later(120,fast)
def fast():
 row=sample(app.windows['main']);assert not row['native'] and row['alpha']==1 and row['backdrop'] is False,row
 assert not app.bridge.glassAllowed and app.bridge.state['glass_effect']
 check('speed mode overrides glass without erasing the stored choice')
 state['fast_mode']=False;publish();later(120,restored)
def restored():
 row=sample(app.windows['main']);assert row['native'] and row['backdrop'] is True,row
 check('leaving speed mode restores the selected glass effect')
 state['system_transparency']=False;publish();later(120,policy)
def policy():
 row=sample(app.windows['main']);assert not row['native'] and row['alpha']==1,row
 check('Windows transparency and accessibility policy can force the opaque fallback')
 state['system_transparency']=True;publish();later(120,cache)
def cache():
 before=app.material.updates
 for i in range(20):state['status']=str(i);publish()
 assert before==app.material.updates
 check('ordinary status updates do not repeat native composition calls')
 app.windows['main'].setProperty('page',2);later(200,control)
def control():
 win=app.windows['main'];switch=win.findChild(QQuickItem,'glassSwitch');assert switch and switch.property('value') and switch.isEnabled()
 state['fast_mode']=True;publish();later(100,lambda:disabled_control(switch))
def disabled_control(switch):
 assert not switch.property('value') and not switch.isEnabled()
 check('the appearance switch displays off and becomes unavailable while speed mode is active')
 state['fast_mode']=False;publish();later(100,moving)
def moving():
 from ctypes import wintypes as W
 win=app.windows['main'];hwnd=int(win.winId());msg=W.MSG();msg.hWnd=hwnd;msg.message=0x231
 assert app.material_filter_installed
 app.material_events.nativeEventFilter(b'windows_generic_MSG',C.addressof(msg))
 assert win.property('nativeGlass') and app.material.states[hwnd][-1]
 msg.message=0x232;app.material_events.nativeEventFilter(b'windows_generic_MSG',C.addressof(msg))
 assert win.property('nativeGlass')
 check('Acrylic remains enabled during native window moving')
 state['fast_mode']=True;publish();assert app.material_filter_installed and not win.property('nativeGlass')
 check('speed mode removes glass while retaining essential native client-area handling')
 state['fast_mode']=False;publish();later(120,shape_check)
def shape_check():
 from encolite import windows_shell as shell
 win=app.windows['main'];hwnd=int(win.winId())
 assert win.property('systemFrame') and attr(win,1)==0 and attr(win,33)==3
 assert not shell.GetWindowLong(hwnd,-20)&0x80000,'layered windows cannot use the native rounded contour'
 region=C.windll.gdi32.CreateRectRgn;region.argtypes=[C.c_int]*4;region.restype=C.c_void_p
 handle=region(0,0,0,0)
 try:
  get_region=C.windll.user32.GetWindowRgn;get_region.argtypes=[C.c_void_p,C.c_void_p];get_region.restype=C.c_int
  assert get_region(hwnd,handle)==0,'DWM must own the contour; no manual window region'
 finally:
  delete=C.windll.gdi32.DeleteObject;delete.argtypes=[C.c_void_p];delete(handle)
 assert app.material.native.caption_hidden(hwnd)
 composed=win.screen().grabWindow(hwnd);assert not composed.isNull()
 composed.save(str(OUT/(TAG+'-native-composed.png')))
 check('DWM owns background and corners together, without layering, custom regions or a native caption')
 app.close_view('main',exiting=False,animate=False)
 assert not app.material.states and not app.material.frames and not app.material_filter_installed
 check('closing the last window releases material state and its native listener')
 state['system_motion']=True;publish();app.show('quick');later(1900,animated)
def animated():
 win=app.windows['quick'];assert win.opacity()==1 and win.property('reveal')==1 and not win.property('transitioning')
 assert win.property('nativeGlass') and win.property('surfaceScale')==1 and win.property('surfaceOffset')==0
 check('glass entrance reaches full opacity even when the compositor animation clock is suspended')
 app.close_view('quick',exiting=False);later(500,animated_closed)
def animated_closed():
 assert 'quick' not in app.windows and not app.material_filter_installed
 check('animated glass dismissal releases its window and material listener')
 state.update(system_motion=False,dark=False,quick_auto_hide=True,custom_available=True,custom_names=['音效'],custom_index=0,can_equalizer=True,presets=[{'name':'默认','id':0}],noise_options=[{'key':'anc'}],can_anc=True,can_off=True,can_transparency=True,noise='anc');publish();app.show('main');later(150,lambda:surfaces(0))
def surfaces(index):
 modes=[(True,False),(True,True),(False,False)]
 if index==len(modes):
  assert not report['warnings'],report['warnings'];app.quit();return
 glass,dark=modes[index];state.update(glass_effect=glass,dark=dark);publish()
 win=app.windows['main'];win.setProperty('page',0);later(180,lambda:surface_page(index,0))
def surface_page(index,page_index):
 win=app.windows['main'];glass=state['glass_effect'];pages=[0,2,5]
 items=[item for item in win.findChildren(QQuickItem) if item.objectName() in ('cardSurface','appearanceSettings','batterySurface','buttonSurface','fieldSurface') and item.isVisible()]
 assert items,(index,page_index)
 for item in items:
  alpha=item.property('color').alphaF()
  if item.objectName()=='buttonSurface' and (item.parentItem().property('primary') or item.parentItem().property('quiet')):continue
  assert (0<alpha<.5 if glass else alpha==1),(item.objectName(),alpha,glass)
 if page_index==1:
  trigger=next(item for item in win.findChildren(QQuickItem,'selectTrigger') if item.isVisible())
  control=trigger.parentItem();QMetaObject.invokeMethod(control,'openMenu');later(100,lambda:menu_check(index,control));return
 continue_surfaces(index,page_index)
def menu_check(index,control):
 popup=control.findChild(QObject,'selectPopup');assert popup and popup.property('visible')
 alpha=popup.property('background').property('color').alphaF()
 assert (.6<alpha<.8 if state['glass_effect'] else alpha==1),alpha
 QMetaObject.invokeMethod(control,'closeMenu')
 check('drop-down menu inherits the active window glass setting')
 picker=app.windows['main'].findChild(QObject,'accentPicker');assert picker
 QMetaObject.invokeMethod(picker,'open');later(100,lambda:picker_check(index,picker))
def picker_check(index,picker):
 background=picker.property('background');alpha=background.property('color').alphaF()
 assert (.6<alpha<.8 if state['glass_effect'] else alpha==1),alpha
 QMetaObject.invokeMethod(picker,'close');continue_surfaces(index,1)
def continue_surfaces(index,page_index):
 if page_index<2:
  app.windows['main'].setProperty('page',[0,2,5][page_index+1]);later(150,lambda:surface_page(index,page_index+1))
 else:
  check('controls and color dialog use translucent surfaces' if state['glass_effect'] else 'disabling glass restores every checked control to its solid surface')
  later(0,lambda:surfaces(index+1))
publish();later(0,cycle);later(24000,lambda:(_ for _ in ()).throw(TimeoutError('material verification timeout')))
try:
 assert app.material.supported,'Native Acrylic needs Windows 10 1809 or later'
 app.run()
finally:
 report['result']='PASS' if not report['errors'] and not report['warnings'] and len(report['checks'])==24 else 'FAIL'
 (OUT/('report.json' if TAG=='default' else TAG+'-report.json')).write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
 if report['result']!='PASS':raise SystemExit(1)
