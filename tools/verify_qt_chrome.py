"""Measure own-window shadow on an owned backdrop, and inspect settings layout."""
from pathlib import Path
import ctypes as C,json,sys,time,traceback
ROOT=Path(__file__).resolve().parents[1]
TARGET=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT
sys.path[:0]=[str(TARGET),str(TARGET/'qt' if TARGET!=ROOT else ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8')
from PySide6.QtCore import QTimer,Qt,QPointF,qInstallMessageHandler
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickWindow,QQuickItem
from encolite.qt_desktop import Desktop
from encolite import windows_shell as shell
OUT=ROOT/'verification/qt-chrome';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'pixels':{},'scope':'Only owned Qt windows and a solid owned backdrop; no Bluetooth commands or global Windows appearance changes.'}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(TARGET,read_pipe=False)
backdrop=QQuickWindow();backdrop.setFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
background=QColor('#b0c0d0');backdrop.setColor(background)
area=app.app.primaryScreen().availableGeometry();backdrop.setGeometry(area);backdrop.show()
state={'system_motion':True,'glass_effect':True,'glass_transparency':45,'system_transparency':True,
       'fast_launch':True,'connected':True,'model_name':'OPPO Enco X3','noise_options':[],
       'theme_mode':'system','accent_mode':'custom','accent_color':'#168b51','quick_topmost':True,
       'quick_auto_hide':False,'quick_idle_seconds':30,'autostart_available':True}
hotkeys={'enabled':True,'capturing':False,'items':[{'action':'noise','title':'切换降噪','label':'Ctrl + Alt + N','binding':{'modifiers':3,'key':78}}]}
def publish():app.receive({'type':'state','state':dict(state),'hotkeys':dict(hotkeys),'preferences':{}})
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def until(predicate,fn):
    deadline=time.monotonic()+3
    def poll():
        if predicate():fn()
        elif time.monotonic()>deadline:raise TimeoutError('window transition or settings did not settle')
        else:later(12,poll)
    later(0,poll)
def check(text):report['checks'].append(text);print('PASS',text,flush=True)
def settled(win):return win.property('presented') and not win.property('transitioning') and win.property('reveal')==1
def pixels(win,name):
    box=win.frameGeometry();d=win.devicePixelRatio()
    image=win.screen().grabWindow(0,box.x()-40,box.y()-40,box.width()+80,box.height()+80).toImage()
    image.save(str(OUT/(name+'.png')))
    x=image.width()//2;bottom=round((40+box.height())*d)
    samples={offset:image.pixelColor(x,bottom+round(offset*d)) for offset in (1,4,8,16,24,32)}
    report['pixels'][name]={str(k):c.name() for k,c in samples.items()}
    return samples,image
def distance(a,b):return max(abs(a.red()-b.red()),abs(a.green()-b.green()),abs(a.blue()-b.blue()))
def begin():
    publish();app.show('quick');win=app.windows['quick']
    win.setGeometry(area.x()+80,area.y()+50,352,374)
    shell.SetWindowPos(int(backdrop.winId()),C.c_void_p(-1),0,0,0,0,0x13)
    shell.SetWindowPos(int(win.winId()),C.c_void_p(-1),0,0,0,0,0x13)
    until(lambda:settled(win),lambda:baseline(win))
def baseline(win):
    # Compare the former Windows default contour with the new small contour.
    app.material.native.attribute(int(win.winId()),33,2)
    later(180,lambda:wide(win))
def wide(win):
    samples,_=pixels(win,'old-large-shadow');report['old_shadow_24']=distance(samples[24],background)
    app.material.native.attribute(int(win.winId()),33,3)
    later(180,lambda:compact(win))
def compact(win):
    samples,image=pixels(win,'compact-shadow');d=win.devicePixelRatio()
    assert distance(samples[24],background)<=2,samples
    assert report['old_shadow_24']>distance(samples[24],background)+5,report['pixels']
    corner=image.pixelColor(round(40*d),round(40*d))
    assert distance(corner,background)<=4,corner.name()
    bright=sum(min(image.pixelColor(x,y).getRgb()[:3])>=249
               for y in range(round(44*d),round(68*d))
               for x in range(round(44*d),round(130*d)))
    report['unexpected_caption_pixels']=bright
    assert bright==0,'a native white caption was drawn behind the translucent title area'
    check('compact native corners eliminate the large lower shadow without an exposed corner or duplicate native caption')
    app.close_view('quick',exiting=False)
    until(lambda:win.property('closingUi') and .1<win.property('displayOpacity')<.95,lambda:fading(win))
def fading(win):
    samples,_=pixels(win,'closing-no-halo')
    assert all(distance(samples[offset],background)<=2 for offset in (24,32)),report['pixels']
    assert win.property('nativeGlass') and win.opacity()==1
    assert win.findChild(QQuickItem,'windowSurface').opacity()==1
    check('content fades over stable Acrylic while the compact contour keeps the distant lower shadow clear')
    until(lambda:'quick' not in app.windows,settings)
def items(win):
    def walk(item):
        yield item
        for child in item.childItems():yield from walk(child)
    return list(walk(win.contentItem()))
def named(win,name):return next((i for i in items(win) if i.objectName()==name),None)
def settings():
    state['system_motion']=False;publish();app.show('main');win=app.windows['main'];win.setProperty('page',2)
    until(lambda:settled(win),lambda:layout(win))
def layout(win):
    groups=[named(win,name) for name in ('appearanceSettings','quickSettings','performanceSettings','hotkeySettings','aboutSettings')]
    assert all(groups),groups
    rects=[]
    for group in groups:
        p=group.mapToScene(QPointF(0,0));rects.append((p.x(),p.y(),group.width(),group.height()))
        assert group.width()>400 and group.height()>40,rects
    assert all(rects[i][1]+rects[i][3]+15<=rects[i+1][1] for i in range(4)),rects
    assert all(abs(rects[i+1][1]-rects[i][1]-rects[i][3]-24)<=1 for i in range(4)),rects
    row_geometry=[]
    for item in items(win):
        if item.isVisible() and (item.property('minimumRowHeight') or item.objectName()=='accentPalette'):
            point=item.mapToScene(QPointF(0,0))
            row_geometry.append({'title':item.property('title') or 'accentPalette','y':point.y(),'height':item.height()})
            assert abs(item.height()-52)<=1,row_geometry[-1]
    assert len(row_geometry)>=14,row_geometry
    report['settings_rows']=row_geometry
    check('settings groups have equal 24 DIP gaps and all regular setting rows use a consistent 52 DIP height')
    assert named(win,'glassTransparencySlider').isVisible()
    state['glass_effect']=False;publish();later(100,lambda:dependent(win))
def dependent(win):
    assert not named(win,'glassTransparencySlider').isVisible()
    assert not named(win,'quickIdleSeconds').isVisible()
    state['quick_auto_hide']=True;publish();later(100,lambda:idle(win))
def idle(win):
    assert named(win,'quickIdleSeconds').isVisible()
    hotkeys['enabled']=False;publish();later(100,lambda:hotkey_rows(win))
def hotkey_rows(win):
    assert not any(i.property('text')=='Ctrl + Alt + N' and i.isVisible() for i in items(win))
    check('glass, idle-time and shortcut details appear only when their parent feature is enabled')
    state['glass_effect']=True;hotkeys['enabled']=True;publish();later(150,lambda:finish(win))
def finish(win):
    assert named(win,'glassTransparencySlider').isVisible()
    assert any(i.property('text')=='Ctrl + Alt + N' and i.isVisible() for i in items(win))
    win.grabWindow().save(str(OUT/'settings.png'))
    check('dependent settings restore their values when re-enabled')
    assert not report['warnings'],report['warnings'];app.quit()
later(0,begin);later(12000,lambda:(_ for _ in ()).throw(TimeoutError('chrome verification timeout')))
try:app.run()
finally:
    backdrop.hide();report['result']='FAIL' if report['errors'] or report['warnings'] or len(report['checks'])!=5 else 'PASS'
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
