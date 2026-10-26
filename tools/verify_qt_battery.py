"""Low-battery threshold and charging presentation in all three owned Qt views."""
from pathlib import Path
import json,sys,traceback
ROOT=Path(__file__).resolve().parents[1]
TARGET=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT
sys.path[:0]=[str(TARGET),str(TARGET/'qt' if TARGET!=ROOT else ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8')
from PySide6.QtCore import QTimer,qInstallMessageHandler
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickItem
from encolite.qt_desktop import Desktop
OUT=ROOT/'verification/qt-battery';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'hardware_writes':False}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(TARGET,read_pipe=False)
state={'connected':True,'model_name':'OPPO Enco X3','battery_layout':'stereo','noise_options':[],
       'system_motion':False,'glass_effect':False,'fast_launch':True}
cases=[(19,20,0),(20,19,19),(None,None,None),(21,100,100)]
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def publish():app.receive({'type':'state','state':dict(state),'preferences':{}})
def visual_items(item):
    yield item
    for child in item.childItems():yield from visual_items(child)
def cycle(index=0,case=0):
    if index==6:
        assert not report['warnings'],report['warnings'];app.quit();return
    kind=('main','quick','notice')[index%3];state['dark']=index>=3
    for key,value in zip(('left','right','case'),cases[case]):
        state[key+'_value']='—' if value is None else str(value)+'%'
        state[key+'_level']=0 if value is None else value/100
        state[key+'_charging']=True
    publish()
    if case==0:app.show(kind)
    later(180,lambda:verify(index,case,kind))
def verify(index,case,kind):
    win=app.windows[kind]
    if not win.property('presented'):
        later(100,lambda:verify(index,case,kind));return
    for key,value in zip(('left','right','case'),cases[case]):
        low=value is not None and value<=20
        names=('noticeBattery_',) if kind=='notice' else ('batteryValue_','batteryBar_')
        for prefix in names:
            items=[item for item in visual_items(win.contentItem()) if item.objectName()==prefix+key and item.isVisible()]
            if kind=='notice' and value is None:
                assert not items;continue
            assert items,(kind,prefix,key)
            color=items[0].property('color')
            red=QColor('#ffaaa0' if state['dark'] else '#bb473d')
            assert (color==red)==low,(kind,key,value,color.name(),red.name())
    report['checks'].append(f"{kind} {'dark' if state['dark'] else 'light'} battery values {cases[case]} use the at-or-below-20% threshold")
    if case==0:
        box=win.frameGeometry()
        win.screen().grabWindow(0,box.x(),box.y(),box.width(),box.height()).save(str(OUT/(kind+('-dark' if state['dark'] else '-light')+'.png')))
    if case+1<len(cases):later(0,lambda:cycle(index,case+1))
    else:
        app.close_view(kind,exiting=False,animate=False)
        later(0,lambda:cycle(index+1,0))
later(0,cycle)
later(15000,lambda:(_ for _ in ()).throw(TimeoutError('battery check timed out')))
app.run()
report['result']='FAIL' if report['errors'] or report['warnings'] else 'PASS'
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
sys.exit(report['result']!='PASS')
