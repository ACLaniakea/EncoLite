"""Own Qt input events, real inactivity timer and isolated saved preferences."""
from pathlib import Path
import json,sys,tempfile,time,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QObject,QPoint,QPointF,QEvent,QMetaObject,QTimer,Qt,qInstallMessageHandler
from PySide6.QtGui import QKeyEvent
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from shiboken6 import isValid
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.presentation import JsonPresentation
from encolite.json_view import JsonView
from encolite.qt_desktop import Desktop,plain
from encolite.native_desktop import NativeDesktop
OUT=ROOT/'verification/qt-quick-idle';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'real_hardware':False}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
temporary=tempfile.TemporaryDirectory(prefix='qt-idle-',dir=ROOT/'.install-test')
preferences=Path(temporary.name)/'preferences.json'
app=Desktop(ROOT,read_pipe=False);view=JsonView()
c=Controller(session=DemoSession(),preferences=preferences,presentation=JsonPresentation())
c.fast_mode=True;c.fast_launch=True;overrides={}
def publish():
    state={**view.snapshot(),'connected':True,'model_name':'OPPO Enco X3','noise':'smart','anc_level':'smart',
      'can_anc':True,'can_transparency':True,'can_off':True,'can_equalizer':True,
      'presets':[{'id':0,'name':'均衡'},{'id':1,'name':'低音'}],
      'noise_options':[{'key':'smart','name':'智能降噪'},{'key':'off','name':'关闭'}],**overrides}
    app.receive({'type':'state','state':state,'preferences':c.preference_data,'hotkeys':{'items':[]}})
c.on_changed=publish;c.attach(view);action=app.bridge.action
def dispatch(name,args):
    action(name,args)
    if name in ('change_quick_auto_hide','change_quick_idle_seconds'):
        assert name in NativeDesktop.ACTIONS;getattr(c,name)(*plain(args))
app.bridge.action=dispatch
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def objects(kind):
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
def named(name,kind='main'):return next(o for o in objects(kind) if o.objectName()==name)
def click(item,kind='main'):QTest.mouseClick(app.windows[kind],Qt.LeftButton,Qt.NoModifier,item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint())
def type_text(text):
    QTest.keyClick(app.windows['main'],Qt.Key_A,Qt.ControlModifier)
    for char in text:
        for event in (QEvent.KeyPress,QEvent.KeyRelease):app.app.sendEvent(app.windows['main'],QKeyEvent(event,ord(char),Qt.NoModifier,char))
    QTest.keyClick(app.windows['main'],Qt.Key_Return)
def settings():
    app.windows['main'].setProperty('page',2);later(100,edit)
def edit():
    assert not app.quick_idle_timer.isActive();click(named('quickAutoHide'));later(60,enabled)
def enabled():
    assert c.quick_auto_hide and not app.quick_idle_timer.isActive()
    field=named('quickIdleSeconds');click(field);type_text('37')
    assert c.quick_idle_seconds==37 and field.property('text')=='37'
    saved=json.loads(preferences.read_text('utf-8'));assert saved['quick_auto_hide'] and saved['quick_idle_seconds']==37
    check('settings switch and typed seconds call production actions and persist without arming the main window')
    c.change_quick_idle_seconds(5);app.show('quick');later(250,guards)
def guards():
    assert app.quick_idle_timer.isActive();before=app.quick_idle_timer.remainingTime()
    overrides['left_value']='80%';publish();after=app.quick_idle_timer.remainingTime()
    assert after<=before, (before,after)
    check('unrelated battery updates do not reset the inactivity deadline')
    menu=next(o for o in objects('quick') if o.property('accessibleName')=='耳机音效')
    click(menu,'quick');later(60,lambda:menu_open(menu))
def menu_open(menu):
    assert menu.property('popupVisible') and app.windows['quick'].property('quickMenuOpen')
    assert not app.quick_idle_timer.isActive()
    QTest.keyClick(app.windows['quick'],Qt.Key_Escape);later(60,pointer)
def pointer():
    assert not app.windows['quick'].property('quickMenuOpen') and app.quick_idle_timer.isActive()
    check('open dropdown suspends the timer; closing it starts a fresh idle period')
    win=app.windows['quick'];QTest.mousePress(win,Qt.LeftButton,Qt.NoModifier,QPoint(5,110));app.quick_idle_expired()
    assert 'quick' in app.windows and not app.closing
    QTest.mouseRelease(win,Qt.LeftButton,Qt.NoModifier,QPoint(5,110))
    check('holding a pointer does not let an expiry close the window during interaction')
    overrides['busy']=True;publish();app.quick_idle_expired()
    assert 'quick' in app.windows and not app.closing
    overrides['busy']=False;publish()
    check('pending earbud operations defer automatic closing')
    c.change_quick_auto_hide(False);assert not app.quick_idle_timer.isActive()
    app.quick_idle_expired();assert 'quick' in app.windows
    check('disabling automatic close cancels the timer and ignores a stale expiry')
    c.change_quick_auto_hide(True);later(2800,activity)
def activity():
    QTest.mouseMove(app.windows['quick'],QPoint(6,112));QTest.keyClick(app.windows['quick'],Qt.Key_Shift)
    assert app.quick_idle_timer.remainingTime()>4700
    later(2800,still_open)
def still_open():
    assert 'quick' in app.windows and app.quick_idle_timer.isActive()
    check('mouse and keyboard activity extend visibility beyond the original five-second deadline')
    later(2600,closed)
def closed():
    assert 'quick' not in app.windows and app.idle and not app.stopping
    assert not app.quick_idle_timer.isActive()
    check('five real inactive seconds close quick control through the normal fast-launch lifecycle')
    app.show('quick');later(250,rescue)
def rescue():
    overrides['fast_mode']=False;publish();app.quick_idle_expired()
    assert app.closing['quick']['reason']=='idle'
    QTest.mouseMove(app.windows['quick'],QPoint(7,113));later(400,rescued)
def rescued():
    assert 'quick' in app.windows and 'quick' not in app.closing and app.windows['quick'].opacity()==1
    check('new input during an automatic close fade cancels that close')
    app.close_view('quick');QTest.mouseMove(app.windows['quick'],QPoint(8,114));later(250,manual_closed)
def manual_closed():
    assert 'quick' not in app.windows and app.idle
    check('input does not cancel an explicit user close')
    app.show('quick');later(250,to_main)
def to_main():
    assert app.quick_idle_timer.isActive()
    app.show('main');later(350,finish)
def finish():
    assert 'main' in app.windows and 'quick' not in app.windows and not app.quick_idle_timer.isActive()
    check('switching to main stops the quick timer and leaves main open')
    assert not report['warnings'],report['warnings'];app.quit()
app.show('main');later(400,settings)
later(18000,lambda:(_ for _ in ()).throw(TimeoutError('idle test timeout')))
try:app.run()
finally:
    c.close();temporary.cleanup();report['result']='PASS' if len(report['checks'])==11 and not report['errors'] and not report['warnings'] else 'FAIL'
    (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
