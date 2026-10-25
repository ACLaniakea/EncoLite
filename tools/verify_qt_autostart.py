"""Real settings clicks and native registration with an isolated shortcut key."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ctypes as C,json,os,sys,tempfile,traceback,uuid
ROOT=Path(__file__).resolve().parents[1]
TARGET=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT
sys.path[:0]=[str(TARGET),str(ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QObject,QPointF,QTimer,Qt,qInstallMessageHandler
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from shiboken6 import isValid
from encolite.autostart import WindowsStartup
from encolite.hotkeys import ACTIONS
from encolite.native_desktop import NativeDesktop
from encolite.qt_desktop import Desktop,plain
OUT=ROOT/'verification/qt-autostart';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'target':str(TARGET),'real_hardware':False,
        'scope':'Own Qt input, native Shell Link COM in an isolated folder; user Startup folder unchanged'}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
temporary=tempfile.TemporaryDirectory(prefix='qt-startup-',dir=ROOT/'.install-test')
data=Path(temporary.name);os.environ['ENCOLITE_DATA_DIR']=str(data)
(data/'preferences.json').write_text(json.dumps({'fast_mode':True,'connection_popup':False,
    'hotkeys':{'bindings':{key:None for key,_ in ACTIONS}}}),'utf-8')
startup=WindowsStartup(TARGET,folder=data/'Startup')
args=SimpleNamespace(fixture=True,tray_only=True,quick=False,test_report=None,test_timeout=0,isolated_tray=True)
native=NativeDesktop(TARGET,args,startup=startup);app=Desktop(TARGET,read_pipe=False)
native.send=app.receive
action=app.bridge.action
def dispatch(name,args):
    action(name,args)
    native.receive({'type':'action','name':name,'args':plain(args)})
app.bridge.action=dispatch
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def items():
    win=app.windows['main'];pending=[win,win.contentItem()];seen=set();result=[]
    while pending:
        item=pending.pop()
        if id(item) in seen or not isValid(item):continue
        seen.add(id(item));result.append(item);pending.extend(item.children())
        if isinstance(item,QQuickItem):pending.extend(item.childItems())
    return result
def switch():return next(o for o in items() if o.objectName()=='autostartSwitch')
def click():
    item=switch();QTest.mouseClick(app.windows['main'],Qt.LeftButton,Qt.NoModifier,
        item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint())
def start():
    app.windows['main'].setProperty('page',2);later(80,scroll)
def scroll():
    item=switch();flick=item.parentItem()
    while flick.property('contentY') is None:flick=flick.parentItem()
    y=item.mapToScene(QPointF(0,0)).y()-flick.mapToScene(QPointF(0,0)).y()
    flick.setProperty('contentY',max(0,y-80));later(80,enable)
def enable():
    assert switch().property('enabled') and not switch().property('value')
    click();later(60,enabled)
def enabled():
    assert startup.enabled() and switch().property('value')
    assert WindowsStartup(TARGET,folder=data/'Startup').enabled()
    assert startup.read()==startup.command(validate=True)
    assert 'autostart_enabled' not in native.controller.preference_data
    app.windows['main'].grabWindow().save(str(OUT/'enabled.png'))
    check('actual settings click writes the windowless tray command and projects verified shortcut state')
    check('a fresh instance reads the registration without relying on a preferences flag')
    with patch.object(startup,'set_enabled',side_effect=PermissionError('测试拒绝写入')):click()
    assert startup.enabled() and switch().property('value') and app.bridge.state['status_error']
    check('registration failure leaves the real switch state intact and displays an error')
    click();assert not startup.enabled() and not switch().property('value') and not app.bridge.state['status_error']
    check('turning the switch off removes this registration immediately')
    startup.set_enabled(True);native.system_settings_changed()
    assert switch().property('value')
    startup.path.unlink()
    native.system_settings_changed();assert not switch().property('value')
    check('external shortcut changes refresh through the native settings event')
    # Verify Windows parsing of a Unicode command containing spaces.
    candidate=WindowsStartup(TARGET/'测试 带空格目录',folder=data/'Startup')
    count=C.c_int();parse=C.windll.shell32.CommandLineToArgvW
    parse.argtypes=[C.c_wchar_p,C.POINTER(C.c_int)];parse.restype=C.POINTER(C.c_wchar_p)
    parsed=parse(candidate.command(),C.byref(count));assert parsed
    try:
        argv=[parsed[i] for i in range(count.value)]
        assert argv==[str(candidate.root/'.tools/python-3.13.17-embed-amd64/pythonw.exe'),str(candidate.root/'desktop_entry.py'),'--tray-only'],argv
    finally:
        free=C.windll.kernel32.LocalFree;free.argtypes=[C.c_void_p];free.restype=C.c_void_p;free(parsed)
    check('Windows command-line parsing preserves Unicode, spaces and the tray-only argument')
    assert not report['warnings'],report['warnings'];app.quit()
native.publish();app.show('main');later(350,start)
later(8000,lambda:(_ for _ in ()).throw(TimeoutError('autostart UI timeout')))
try:app.run()
finally:
    native.close()
    temporary.cleanup()
    report['result']='PASS' if len(report['checks'])==6 and not report['errors'] and not report['warnings'] else 'FAIL'
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
