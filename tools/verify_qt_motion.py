"""Observe rendered Qt/native transitions, reversals and reduced-motion behavior."""
from pathlib import Path
import ctypes as C,json,sys,time,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1]
TARGET=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT
sys.path[:0]=[str(TARGET),str(TARGET/'qt' if TARGET!=ROOT else ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QPointF,QTimer,qInstallMessageHandler
from PySide6.QtQuick import QQuickItem
from encolite.qt_desktop import Desktop
from encolite import windows_shell as shell
OUT=ROOT/'verification/qt-motion';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'frames':{},'real_hardware':False,'target':str(TARGET),'python':sys.version,
        'scope':'Own Qt windows and native alpha; no renderer wrappers or physical input'}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(TARGET,read_pipe=False)
state={'glass_effect':True,'glass_transparency':70,'system_transparency':True,'connected':True,'model_name':'OPPO Enco X3','noise_options':[],
       'fast_mode':False,'fast_launch':True,'system_motion':True,'dark':False}
native_alpha=shell.api(shell.user,'GetLayeredWindowAttributes',W.BOOL,W.HWND,
                       C.POINTER(W.DWORD),C.POINTER(C.c_ubyte),C.POINTER(W.DWORD))
def publish():app.receive({'type':'state','state':state,'preferences':{}})
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def until(predicate,fn,label):
    deadline=time.monotonic()+3
    def poll():
        if predicate():fn()
        elif time.monotonic()>deadline:raise TimeoutError(label)
        else:later(8,poll)
    later(0,poll)
def sample(win,phase,pixels=False):
    color=W.DWORD();alpha=C.c_ubyte();flags=W.DWORD()
    ok=native_alpha(int(win.winId()),C.byref(color),C.byref(alpha),C.byref(flags))
    surface=win.findChild(QQuickItem,'windowSurface')
    top=surface.mapToScene(QPointF(0,0));bottom=surface.mapToScene(QPointF(surface.width(),surface.height()))
    image=win.grabWindow() if pixels else None
    return {'phase':phase,'opacity':win.property('displayOpacity'),'reveal':win.property('reveal'),
            'scale':win.property('surfaceScale'),'offset':win.property('surfaceOffset'),
            'surface_bounds':[top.x(),top.y(),bottom.x(),bottom.y()],
            'native_alpha':alpha.value if ok else None,'surface_ready':win.property('surfaceReady'),'glass':win.property('nativeGlass'),'glass_mix':win.property('glassMix'),'render_alpha':image.pixelColor(image.width()//2,40).alphaF() if image is not None else None,
            'bounds':[win.x(),win.y(),win.width(),win.height()]}
def settled(win):return win.property('displayOpacity')==1 and win.property('reveal')==1 and not win.property('transitioning') and win.property('glassMix')==1
def track(win,key):
    # Observe completed scene-graph frames, leaving production methods untouched.
    began=time.monotonic();rows=report['frames'][key]=[]
    def frame():
        rows.append({**sample(win,'frame'),'ms':round((time.monotonic()-began)*1000,1)})
    win.frameSwapped.connect(frame)
    return frame
def cycle(index=0):
    if index==3:return switch_views()
    kind=('main','quick','notice')[index]
    app.show(kind);win=app.windows[kind];geometry=sample(win,'created')['bounds']
    observer=track(win,kind+'-open')
    def mid():
        row=sample(win,'open-mid',pixels=True)
        assert 0<row['opacity']<1 and 0<row['reveal']<1,row
        assert .94<row['scale']<1 and row['offset']>0,row
        left,top,right,bottom=row['surface_bounds']
        assert 0<left<right<win.width() and 0<top<bottom<=win.height(),row
        assert row['native_alpha'] is None and not row['glass'],row
        assert abs(row['render_alpha']-row['opacity'])<.035,row
        win.grabWindow().save(str(OUT/(kind+'-opening.png')))
        before=(win.property('displayOpacity'),win.property('reveal'));app.show(kind)
        assert (win.property('displayOpacity'),win.property('reveal'))==before
        check(kind+': the complete surface fades and moves before native glass is enabled; repeated show preserves progress')
        until(lambda:settled(win),opened,kind+' open completes')
    def opened():
        win.frameSwapped.disconnect(observer)
        rows=report['frames'][kind+'-open']
        assert len([r for r in rows if 0<r['reveal']<1])>=3,rows
        assert all(r['bounds']==geometry for r in rows)
        assert win.property('surfaceScale')==1 and win.property('surfaceOffset')==0 and win.opacity()==1
        assert sample(win,'settled')['surface_bounds']==[0,0,win.width(),win.height()]
        assert app.material.native.caption_hidden(int(win.winId())) if win.property('systemFrame') else not shell.GetWindowLong(int(win.winId()),-16)&0x00C00000
        win.grabWindow().save(str(OUT/(kind+'-opened.png')))
        check(kind+': several actual intermediate frames, unchanged placement and full-size caption-free endpoint')
        app.close_view(kind,exiting=False);until(lambda:not win.property('surfaceReady') and .08<win.property('displayOpacity')<.95,closing,kind+' fading after glass cover')
    def closing():
        row=sample(win,'close-mid')
        assert 0<row['opacity']<1 and 0<row['reveal']<1,row
        assert row['scale']<1 and row['offset']>0 and row['bounds']==geometry,row
        assert row['surface_bounds'][0]>0 and row['surface_bounds'][1]>0,row
        win.grabWindow().save(str(OUT/(kind+'-closing.png')))
        if kind=='notice':
            # Only an automatic notice timeout is allowed to reverse on hover.
            until(lambda:kind not in app.windows,closed,kind+' close completes')
        else:
            before=(win.property('displayOpacity'),win.property('reveal'));app.show(kind)
            assert (win.property('displayOpacity'),win.property('reveal'))==before
            until(lambda:settled(win),reversed_close,kind+' reversed close')
    def reversed_close():
        later(420,after_old_deadline)
    def after_old_deadline():
        assert app.windows.get(kind) is win and settled(win) and kind not in app.closing
        check(kind+': closing reverses continuously and the old close deadline cannot destroy the reopened window')
        app.close_view(kind,exiting=False)
        until(lambda:kind not in app.windows,closed,kind+' final close')
    def closed():
        check(kind+': reverse motion completes before window disposal')
        later(50,lambda:cycle(index+1))
    until(lambda:win.property('presented') and .08<win.property('reveal')<.85,mid,kind+' opening frame')
def switch_views():
    app.show('quick');win=app.windows['quick']
    def switch():
        app.show('main');main=app.windows['main']
        until(lambda:settled(main) and set(app.windows)=={'main'},done,'switch to main')
    def done():
        check('switching quick control to main completes both transitions and retains the target window')
        app.close_view('main',exiting=False,animate=False);early_reopen()
    until(lambda:settled(win),switch,'quick before switch')
def early_reopen():
    app.show('quick');win=app.windows['quick']
    app.close_view('quick',exiting=False);app.show('quick')
    until(lambda:settled(win),done,'reopen before first frame')
def done():
    check('close and reopen before the first frame still reaches a fully presented window')
    app.close_view('quick',exiting=False,animate=False);speed_during_open()
def speed_during_open():
    app.show('main');win=app.windows['main']
    def disable():
        state['fast_mode']=True;publish()
        assert settled(win) and win.property('surfaceScale')==1 and win.property('surfaceOffset')==0
        check('enabling speed mode during entrance immediately settles all visual transforms')
        app.close_view('main',exiting=False);assert 'main' not in app.windows
        state.update(fast_mode=False,system_motion=False);publish();app.show('notice')
        assert app.windows['notice'].property('surfaceScale')==1 and app.windows['notice'].property('surfaceOffset')==0
        later(150,reduced)
    until(lambda:.05<win.property('reveal')<.85,disable,'entrance to cancel')
def reduced():
    win=app.windows['notice'];assert settled(win)
    app.close_view('notice',exiting=False);assert 'notice' not in app.windows
    check('system reduced motion skips fade, scale and translation from the first visible frame')
    state['system_motion']=True;publish();app.show('quick');win=app.windows['quick']
    def close():
        app.close_view('quick',exiting=False)
        later(55,disable)
    def disable():
        state['fast_mode']=True;publish();assert 'quick' not in app.windows
        check('disabling motion during dismissal completes disposal without leaving a transparent window')
        assert not report['warnings'],report['warnings'];app.quit()
    until(lambda:settled(win),close,'quick for close interruption')
publish();later(0,cycle)
later(20000,lambda:(_ for _ in ()).throw(TimeoutError('motion verification timeout')))
try:app.run()
finally:
    report['result']='PASS' if not report['errors'] and not report['warnings'] and len(report['checks'])==16 else 'FAIL'
    (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='frames'}),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
