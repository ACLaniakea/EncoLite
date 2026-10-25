"""Real Qt pointer/key events wired to the production color controller, isolated preferences."""
from pathlib import Path
import json,sys,tempfile,time,traceback
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QObject,QPointF,QTimer,Qt,QEvent,qInstallMessageHandler
from PySide6.QtGui import QKeyEvent
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from shiboken6 import isValid
from encolite.qt_desktop import Desktop,plain
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.presentation import JsonPresentation
from encolite.json_view import JsonView
from encolite.appearance import accent_palette,read_system_accent
from encolite.native_desktop import NativeDesktop
OUT=ROOT/'verification/qt-accent';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'real_hardware':False,'system_accent':read_system_accent()}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
temporary=tempfile.TemporaryDirectory(prefix='qt-accent-',dir=ROOT/'.install-test')
preferences=Path(temporary.name)/'preferences.json'
app=Desktop(ROOT,read_pipe=False);view=JsonView()
controller=Controller(session=DemoSession(),preferences=preferences,presentation=JsonPresentation())
controller.fast_mode=True
def publish():app.receive({'type':'state','state':view.snapshot(),'preferences':controller.preference_data,'hotkeys':{'items':[]}})
controller.on_changed=publish;controller.attach(view)
action=app.bridge.action
def dispatch(name,args):
    action(name,args)
    if name in ('change_accent_mode','change_accent_color','change_theme_mode'):
        assert name in NativeDesktop.ACTIONS
        getattr(controller,name)(*plain(args))
app.bridge.action=dispatch
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def objects(kind='main'):
    win=app.windows[kind];pending=[win,win.contentItem()];seen=set();rows=[]
    while pending:
        item=pending.pop()
        if id(item) in seen or not isValid(item):continue
        seen.add(id(item));rows.append(item);pending.extend(item.children())
        if isinstance(item,QQuickItem):pending.extend(item.childItems())
        for key in ('contentItem','background'):
            child=item.property(key)
            if isinstance(child,QObject):pending.append(child)
    return rows
def named(name):return next(o for o in objects() if o.objectName()==name)
def button(text):return next(o for o in objects() if o.property('text')==text and o.property('primary') is not None and o.property('visible'))
def click(item,rx=.5,ry=.5):QTest.mouseClick(app.windows['main'],Qt.LeftButton,Qt.NoModifier,item.mapToScene(QPointF(item.width()*rx,item.height()*ry)).toPoint())
def start():
    app.windows['main'].setProperty('page',2);later(120,swatch)
def swatch():
    item=next(o for o in objects() if isinstance(plain(o.property('modelData')),dict) and plain(o.property('modelData')).get('color')=='#0078d4' and o.property('selected') is not None)
    click(item);later(60,swatch_done)
def swatch_done():
    assert controller.accent_color=='#0078d4' and view.palette==accent_palette('#0078d4',controller.dark)
    assert any(o.property('text')=='设置' and hasattr(o.property('color'),'name') and o.property('color').name()==view.palette['accent'] for o in objects())
    app.windows['main'].grabWindow().save(str(OUT/'blue-settings.png'))
    check('preset color click updates the actual controller and themed navigation')
    click(button('更多颜色'));later(80,picker)
def picker():
    assert named('accentPicker').property('visible')
    click(named('accentSaturationValue'),.7,.35)
    hex=named('accentHex');click(hex);QTest.keyClick(app.windows['main'],Qt.Key_A,Qt.ControlModifier)
    for char in '#12':
        for event in (QEvent.KeyPress,QEvent.KeyRelease):
            app.app.sendEvent(app.windows['main'],QKeyEvent(event,ord(char),Qt.NoModifier,char))
    assert not hex.property('acceptableInput')
    click(named('accentSaturationValue'),.5,.5)
    assert not hex.property('activeFocus') and hex.property('acceptableInput')
    check('picking visually recovers an incomplete color value without saving invalid text')
    click(hex);QTest.keyClick(app.windows['main'],Qt.Key_A,Qt.ControlModifier)
    for char in '#9C3BAA':
        for event in (QEvent.KeyPress,QEvent.KeyRelease):
            app.app.sendEvent(app.windows['main'],QKeyEvent(event,ord(char),Qt.NoModifier,char))
    assert hex.property('acceptableInput')
    app.windows['main'].grabWindow().save(str(OUT/'color-picker.png'))
    before=sum(m.get('name')=='change_accent_color' for m in app.messages)
    click(button('应用'));later(60,lambda:applied(before))
def applied(before):
    assert controller.accent_color=='#9c3baa',controller.accent_color
    assert sum(m.get('name')=='change_accent_color' for m in app.messages)==before+1
    assert not named('accentPicker').property('visible')
    check('saturation/value picker and HEX entry apply exactly one saved color action')
    click(button('更多颜色'));later(60,cancel)
def cancel():
    click(named('accentSaturationValue'),.1,.8);click(button('取消'))
    assert controller.accent_color=='#9c3baa'
    check('canceling a draft color retains the previous theme')
    click(button('更多颜色'));later(60,escape)
def escape():
    QTest.keyClick(app.windows['main'],Qt.Key_Escape)
    assert not named('accentPicker').property('visible') and 'main' in app.windows
    check('Escape dismisses the color picker without closing the app')
    select=next(o for o in objects() if o.property('accessibleName')=='主题色来源')
    click(select);later(80,follow)
def follow():
    with patch('encolite.appearance.read_system_accent',return_value='#c04b33'):
        click(button('跟随 Windows'))
    assert controller.accent_mode=='system' and view.system_accent=='#c04b33'
    assert view.palette==accent_palette('#c04b33',controller.dark)
    check('Windows color source menu uses the production action and system palette')
    saved=preferences.read_bytes()
    with patch('encolite.appearance.read_system_accent',return_value='#008184'):
        controller.refresh_system_appearance()
    assert view.palette==accent_palette('#008184',controller.dark) and preferences.read_bytes()==saved
    check('system color event updates open windows without rewriting preferences')
    restarted=Controller(session=DemoSession(),preferences=preferences,presentation=JsonPresentation())
    try:assert restarted.accent_mode=='system' and restarted.accent_color=='#9c3baa'
    finally:restarted.close()
    check('restarting the controller retains both the custom color and system selection')
    controller.change_theme_mode('dark');app.windows['main'].grabWindow().save(str(OUT/'system-dark.png'))
    assert view.palette==accent_palette('#008184',True)
    check('dark/light appearance remains independent from accent source')
    app.show('quick');later(200,quick)
def quick():
    app.windows['quick'].grabWindow().save(str(OUT/'quick-teal.png'))
    app.show('notice');later(150,notice)
def notice():
    app.windows['notice'].grabWindow().save(str(OUT/'notice-teal.png'))
    assert not report['warnings'],report['warnings']
    check('main, quick control and notice render the shared palette without QML warnings')
    app.quit()
app.show('main');later(250,start);later(12000,lambda:(_ for _ in ()).throw(TimeoutError('accent test timeout')))
try:app.run()
finally:
    controller.close();temporary.cleanup()
    report['result']='PASS' if not report['errors'] and len(report['checks'])==10 else 'FAIL'
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
