"""Measure own native tray callbacks and GUI lifetime, without Bluetooth writes."""
from pathlib import Path
from types import SimpleNamespace
import ctypes as C,json,os,sys,time,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(ROOT/'.build-deps')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
import psutil
from encolite import windows_shell as s
from encolite.native_desktop import NativeDesktop
from encolite.hotkeys import ACTIONS
TARGET=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT
OUT=ROOT/'verification/qt-tray-speed';OUT.mkdir(exist_ok=True)
DATA=ROOT/'.install-test/qt-tray-speed';DATA.mkdir(exist_ok=True)
os.environ['ENCOLITE_DATA_DIR']=str(DATA)
(DATA/'preferences.json').write_text(json.dumps({'connection_popup':False,'fast_mode':False,'fast_launch':False,
    'hotkeys':{'enabled':True,'bindings':{key:None for key,_ in ACTIONS}}}),'utf-8')
app=NativeDesktop(TARGET,SimpleNamespace(fixture=True,tray_only=True,quick=False,test_timeout=0,test_report=None,isolated_tray=True))
report={'checks':[],'errors':[],'samples':[],'real_hardware':False,'scope':'Own native tray messages, production JSON pipe and Qt HWND; no physical mouse automation','target':str(TARGET)}
enum_type=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
enum=s.api(s.user,'EnumWindows',W.BOOL,enum_type,W.LPARAM)
title=s.api(s.user,'GetWindowTextW',C.c_int,W.HWND,W.LPWSTR,C.c_int)
alpha=s.api(s.user,'GetLayeredWindowAttributes',W.BOOL,W.HWND,C.POINTER(W.DWORD),C.POINTER(C.c_ubyte),C.POINTER(W.DWORD))
dispatched=[];views=[]
on_quick=app.tray.on_quick;receive=app.receive
def quick():dispatched.append(time.perf_counter());on_quick()
def received(data):
    if data.get('type')=='view':views.append((time.perf_counter(),data.get('view')))
    receive(data)
app.tray.on_quick=quick;app.receive=received
def window(kind):
    if not app.gui:return None
    found=[];pid=app.gui.pid
    def visit(hwnd,_):
        owner=W.DWORD();s.GetWindowThreadProcessId(hwnd,C.byref(owner))
        if owner.value==pid:
            text=C.create_unicode_buffer(256);title(hwnd,text,256)
            if text.value=='Enco Lite · '+{'main':'耳机助手','quick':'快捷控制'}[kind] and s.IsWindowVisible(hwnd):found.append(hwnd)
        return True
    enum(enum_type(visit),0);return found[0] if found else None
def opaque(kind):
    hwnd=window(kind)
    if not hwnd:return False
    a=C.c_ubyte();color=W.DWORD();flags=W.DWORD()
    return not alpha(hwnd,C.byref(color),C.byref(a),C.byref(flags)) or a.value==255
def condition(predicate,label,timeout=15):return {'predicate':predicate,'label':label,'deadline':time.perf_counter()+timeout,'earliest':0}
def delay(seconds):return condition(lambda:True,'delay')|{'earliest':time.perf_counter()+seconds}
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def click():s.PostMessage(app.tray.hwnd,0x8001,0,0x400)
def sample(name,duplicates=False):
    before=len(dispatched);first=len(views);began=time.perf_counter();click()
    if duplicates:
        s.PostMessage(app.tray.hwnd,0x8001,0,0x202);click()
    yield condition(lambda:opaque('quick'),name+' fully shown')
    now=time.perf_counter()
    assert len(dispatched)==before+1,(name,len(dispatched)-before)
    ready=next(t for t,kind in views[first:] if kind=='quick')
    row={'name':name,'dispatch_ms':round((dispatched[-1]-began)*1000,1),
         'first_frame_ms':round((ready-began)*1000,1),'opaque_ms':round((now-began)*1000,1),'gui_pid':app.gui.pid}
    report['samples'].append(row);print(json.dumps(row),flush=True)
    assert row['dispatch_ms']<200,row
def steps():
    for i in range(2):
        yield from sample('low-memory-'+str(i),duplicates=i==0)
        click();yield condition(lambda:app.gui is None,'low memory GUI exit')
    check('single tray selection dispatches without 350ms delay and duplicate mouse/select events toggle once')
    check('default low-memory mode still exits the complete GUI process')
    app.controller.change_fast_launch(True)
    yield from sample('fast-first')
    pid=app.gui.pid;click();yield condition(lambda:app.active_view is None and not window('quick'),'idle GUI')
    yield delay(.2)
    assert app.gui and app.gui.pid==pid and app.gui.poll() is None
    memory=psutil.Process(pid).memory_full_info()
    report['idle_gui_memory']={'uss_mib':round(memory.uss/1024**2,2),'working_set_mib':round(memory.rss/1024**2,2)}
    check('fast launch destroys the closed window, preserves the engine, and marks backend visibility false')
    assert not app.view.visible
    for i in range(3):
        yield from sample('fast-warm-'+str(i))
        assert app.gui.pid==pid
        click();yield condition(lambda:app.active_view is None and not window('quick'),'warm idle')
        yield delay(.1)
    check('three tray reopens reuse the same GUI process with transitions enabled')
    # Double-click must route to main and ignore the following mouse-up/select.
    s.PostMessage(app.tray.hwnd,0x8001,0,0x203)
    s.PostMessage(app.tray.hwnd,0x8001,0,0x202);click()
    yield condition(lambda:opaque('main'),'double click main')
    assert not window('quick')
    check('double-click still opens main once and its trailing select does not reopen quick UI')
    # Close through the real Window.close handler, via the owned HWND.
    s.PostMessage(window('main'),0x10,0,0)
    yield condition(lambda:app.active_view is None and not window('main'),'main idle')
    app.controller.change_fast_launch(False)
    yield condition(lambda:app.gui is None,'disabled fast launch releases GUI')
    check('turning fast launch off releases an already idle GUI without quitting the tray')
    app.controller.change_quick_idle_seconds(5);app.controller.change_quick_auto_hide(True)
    yield delay(.5)
    yield from sample('auto-hide-low-memory')
    yield condition(lambda:app.gui is None,'automatic idle close releases GUI',9)
    assert not app.view.visible and s.api(s.user,'IsWindow',W.BOOL,W.HWND)(app.tray.hwnd)
    check('automatic idle close releases the default-mode GUI while retaining the native tray')
runner=steps();waiting=None;completed=False;timer=app.loop.timer()
def tick():
    global waiting,completed
    try:
        if waiting:
            if time.perf_counter()<waiting['earliest']:return
            if not waiting['predicate']():
                if time.perf_counter()>waiting['deadline']:raise TimeoutError(waiting['label'])
                return
        waiting=next(runner)
    except StopIteration:completed=True;timer.stop();app.quit()
    except Exception:report['errors'].append(traceback.format_exc());timer.stop();app.quit()
timer.start(.01,tick,repeat=True)
try:app.run()
finally:
    app.close();report['completed']=completed
    report['result']='PASS' if completed and not report['errors'] else 'FAIL'
    (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
