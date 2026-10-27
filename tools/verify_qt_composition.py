"""Check real Acrylic pixels against owned stripes, then exercise its slider."""
from pathlib import Path
import sys,json,traceback,ctypes as C
ROOT=Path(__file__).resolve().parents[1];TARGET=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT
sys.path[:0]=[str(TARGET),str(TARGET/'qt' if TARGET!=ROOT else ROOT/'.tools/qt-probe/packages')];sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
from PySide6.QtCore import QTimer,QUrl,QPointF,Qt,qInstallMessageHandler
from PySide6.QtQuick import QQuickItem
from PySide6.QtQml import QQmlComponent
from encolite.qt_desktop import Desktop
OUT=ROOT/'verification/qt-composition';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'measurements':[],'scope':'Owned window, owned blue/amber backdrop, real composed pixels and isolated GUI actions; no hardware writes'}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(TARGET,read_pipe=False);state={'glass_effect':True,'glass_transparency':70,'system_motion':False,'fast_mode':False,'system_transparency':True,'noise_options':[]}
def publish():app.receive({'type':'state','state':dict(state),'preferences':{}})
def later(ms,fn):
 def run():
  try:fn()
  except Exception:report['errors'].append(traceback.format_exc());app.quit()
 QTimer.singleShot(ms,run)
def check(text):report['checks'].append(text);print('PASS',text,flush=True)
publish();component=QQmlComponent(app.engine)
component.setData(b'''import QtQuick
Window {color:'#174f98';flags:Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint;Repeater{model:30;Rectangle{required property int index;x:index*120;width:60;height:parent.height;color:'#f1b24a'}}}''',QUrl())
bg=component.create();assert bg
app.show('main');win=app.windows['main'];bg.setGeometry(win.geometry());bg.show();win.setTransientParent(bg);app.activate(win,'main')
from encolite import windows_shell as shell
shell.SetWindowPos(int(bg.winId()),C.c_void_p(-1),0,0,0,0,0x13)
shell.SetWindowPos(int(win.winId()),C.c_void_p(-1),0,0,0,0,0x13)
def sample(label):
 raw=win.grabWindow();surface=win.findChild(QQuickItem,'windowSurface');print('STATE',label,app.bridge.glassTransparency,surface.property('color').alphaF(),raw.pixelColor(raw.width()-50,raw.height()*4//5).alpha(),win.isExposed(),flush=True)
 box=win.frameGeometry();image=win.screen().grabWindow(0,box.x(),box.y(),box.width(),box.height()).toImage();assert not image.isNull();image.save(str(OUT/(label+'.png')))
 colors=[image.pixelColor(x,image.height()*4//5).red() for x in range(image.width()//2,image.width()-50)]
 row={'name':label,'span':max(colors)-min(colors),'edge':max(abs(a-b) for a,b in zip(colors,colors[1:]))};report['measurements'].append(row)
 return row
def begin():
 count=len(app.messages);calls=app.material.updates;app.bridge.previewGlassTransparency(85)
 assert calls==app.material.updates
 assert not [m for m in app.messages[count:] if m.get('name')=='change_glass_transparency']
 check('live preview changes no persisted preference and sends no backend action')
 later(250,transparent)
def transparent():
 row=sample('high-transparency');assert row['span']>25,row
 check('the actual composed window reveals the owned background colors')
 assert row['edge']<row['span']*.35,row
 check('background boundaries are blurred rather than merely alpha blended')
 app.bridge.previewGlassTransparency(0);later(250,opaque)
def opaque():
 row=sample('zero-transparency');assert row['span']<4,row
 check('zero transparency produces a genuinely opaque background')
 app.bridge.previewGlassTransparency(70);win.setProperty('page',2);later(250,slider)
def slider():
 control=win.findChild(QQuickItem,'glassTransparencySlider');assert control and control.isEnabled()
 if TARGET==ROOT:
  from PySide6.QtTest import QTest
  start=control.mapToScene(QPointF(control.width()*.3,control.height()/2)).toPoint();end=control.mapToScene(QPointF(control.width()*.8,control.height()/2)).toPoint()
  before=len([m for m in app.messages if m.get('name')=='change_glass_transparency'])
  QTest.mousePress(win,Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(win,end,40)
  assert len([m for m in app.messages if m.get('name')=='change_glass_transparency'])==before
  QTest.mouseRelease(win,Qt.LeftButton,Qt.NoModifier,end)
  actions=[m for m in app.messages if m.get('name')=='change_glass_transparency'];assert len(actions)==before+1
  value=actions[-1]['args'][0];assert type(value) is int and 0<=value<=100
  state['glass_transparency']=value;publish();assert app.bridge._glass_preview is None
  check('dragging previews immediately and releasing the actual slider commits exactly once')
 else:
  assert round(control.property('value'))==70
  check('packaged transparency slider follows the preview value')
 state['fast_mode']=True;publish();assert not control.isEnabled() and not win.property('nativeGlass')
 check('speed mode disables both Acrylic and the transparency control without erasing its setting')
 assert not report['warnings'],report['warnings'];app.quit()
later(1200,begin);later(12000,lambda:(_ for _ in ()).throw(TimeoutError('composition verification timeout')))
try:app.run()
finally:
 report['result']='PASS' if not report['errors'] and not report['warnings'] and len(report['checks'])==6 else 'FAIL'
 (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
 if report['result']!='PASS':raise SystemExit(1)
