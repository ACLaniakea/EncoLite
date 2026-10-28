"""Sample real Qt/Acrylic state through show, close and minimize transitions.

Uses fixture UI only: no Bluetooth connection, preference writes or installer.
"""
from pathlib import Path
import argparse
import ctypes as C
import json
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('target',nargs='?',type=Path,default=ROOT)
parser.add_argument('--tag',default='current')
args=parser.parse_args()
TARGET=args.target.resolve()
sys.path[:0]=[str(TARGET),str(TARGET/'qt' if TARGET!=ROOT else ROOT/'.tools/qt-probe/packages')]
from PySide6.QtCore import Qt,QTimer,qInstallMessageHandler
from PySide6.QtQuick import QQuickItem
from encolite.qt_desktop import Desktop
from encolite.window_material import AccentPolicy,CompositionData
from encolite import windows_shell as shell

app=Desktop(TARGET,read_pipe=False)
report={'scope':'Fixture-only Qt HWNDs; continuous Acrylic, translucent surfaces, native contours and unlayered rendering during transitions.',
        'checks':[],'errors':[],'warnings':[],'samples':[],'native_calls':[]}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
state={'connected':False,'noise_options':[],'glass_effect':True,'system_transparency':True,
       'fast_mode':False,'system_motion':True,'dark':False,'fast_launch':True,'quick_topmost':True}
phase='start'
start=time.perf_counter()
observer=QTimer();observer.setInterval(8)
read_accent=getattr(C.windll.user32,'GetWindowCompositionAttribute',None)
if read_accent:
    read_accent.argtypes=[C.c_void_p,C.POINTER(CompositionData)]
    read_accent.restype=C.c_int
original_accent=app.material.native.accent

def accent(hwnd,enabled,dark):
    report['native_calls'].append({'t':time.perf_counter()-start,'phase':phase,
                                  'hwnd':hwnd,'enabled':enabled})
    return original_accent(hwnd,enabled,dark)
app.material.native.accent=accent

def check(message):
    report['checks'].append(message);print('PASS '+message,flush=True)

def fail():
    observer.stop()
    report['errors'].append(traceback.format_exc())
    app.quit()

def later(ms,callback):
    def run():
        try:callback()
        except Exception:fail()
    QTimer.singleShot(ms,run)

def publish():app.receive({'type':'state','state':dict(state),'preferences':{}})

def sample():
    try:
        for kind,win in list(app.windows.items()):
            if not win.isVisible():continue
            hwnd=int(win.winId())
            surface=win.findChild(QQuickItem,'windowSurface')
            row={'t':time.perf_counter()-start,'phase':phase,'kind':kind,
                 'minimized':win.windowState()==Qt.WindowMinimized,
                 'glass':bool(win.property('nativeGlass')),
                 'active':bool(app.material.states.get(hwnd,(False,))[-1]),
                 'surface_alpha':surface.property('color').alphaF(),
                 'surface_opacity':surface.opacity(),
                 'content_opacity':win.property('displayOpacity'),
                 'layered':bool(shell.GetWindowLong(hwnd,-20)&0x80000)}
            if read_accent:
                policy=AccentPolicy();data=CompositionData(19,C.addressof(policy),C.sizeof(policy))
                if read_accent(hwnd,C.byref(data)):row['native_accent_state']=policy.state
            report['samples'].append(row)
            assert row['glass'] and row['active'],row
            assert row['surface_alpha']<.99,row
            assert not row['layered'],row
            if 'native_accent_state' in row:assert row['native_accent_state']==4,row
    except Exception:fail()
observer.timeout.connect(sample)

def begin():
    global phase
    assert app.material.supported,'Windows 11 Acrylic support required'
    publish();phase='main-opening';app.show('main');observer.start();sample()
    later(350,minimize)

def minimize():
    global phase
    win=app.windows['main'];assert win.property('displayOpacity')==1
    check('main opens without an opaque or unblurred client frame')
    phase='main-minimizing';win.showMinimized();later(100,restore)

def restore():
    global phase
    phase='main-restoring';app.show('main');later(350,native_minimize)

def native_minimize():
    global phase
    assert app.windows['main'].windowState()!=Qt.WindowMinimized
    check('tray restoration retains Acrylic through the entrance')
    phase='native-minimizing';app.windows['main'].showMinimized();later(100,native_restore)

def native_restore():
    global phase
    phase='native-restoring';app.windows['main'].showNormal();later(300,cancel_close)

def cancel_close():
    global phase
    check('taskbar-style restore retains the same glass surface')
    phase='main-closing';app.close_view('main',exiting=False)
    later(50,reopen)

def reopen():
    global phase
    phase='main-reopening';app.show('main');later(300,close_main)

def close_main():
    global phase
    win=app.windows['main'];assert not win.property('closingUi')
    check('reopening during close keeps glass without an opaque interlude')
    phase='main-final-close';app.close_view('main',exiting=False);later(300,lambda:popup(0))

def popup(index):
    global phase
    if index==2:return finish()
    kind=('quick','notice')[index];phase=kind+'-opening';app.show(kind)
    def opened():
        global phase
        win=app.windows[kind];assert win.property('displayOpacity')==1
        check(kind+' entrance preserves the native backdrop')
        if kind=='quick':
            state['quick_topmost']=False;publish()
            later(180,lambda:close_popup(index,kind))
        else:close_popup(index,kind)
    later(350,opened)

def close_popup(index,kind):
    global phase
    phase=kind+'-closing';app.close_view(kind,exiting=False)
    later(300,lambda:popup(index+1))

def finish():
    assert not app.windows
    assert not app.material.states
    check('all close transitions keep glass until the window is hidden and release state afterward')
    assert not report['warnings'],report['warnings']
    check('no Qt warnings during transition sampling')
    observer.stop();app.quit()

later(0,begin)
later(12000,lambda:(_ for _ in ()).throw(TimeoutError('Material transition verification timed out')))
try:app.run()
finally:
    observer.stop();app.quit()
    report['result']='PASS' if not report['errors'] and len(report['checks'])==8 else 'FAIL'
    out=ROOT/'verification/qt-material-transitions';out.mkdir(parents=True,exist_ok=True)
    (out/(args.tag+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'result':report['result'],'checks':len(report['checks']),
                      'samples':len(report['samples']),'errors':report['errors']}),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
