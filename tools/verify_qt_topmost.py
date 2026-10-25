"""Check actual native quick-window topmost flags and live preference changes."""
from pathlib import Path
import json,sys,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8')
from PySide6.QtCore import QTimer,Qt,qInstallMessageHandler
from encolite.qt_desktop import Desktop
from encolite import windows_shell as s
report={'checks':[],'errors':[],'warnings':[],'real_hardware':False}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(ROOT,read_pipe=False)
state={'connected':False,'model_name':'未连接耳机','fast_mode':True,'system_motion':True,'quick_topmost':True}
def publish():app.receive({'type':'state','state':state,'preferences':{}})
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def topmost(win):return bool(s.GetWindowLong(int(win.winId()),-20)&0x8)
def shown():
    win=app.windows['quick'];assert win.isVisible() and topmost(win)
    report['geometry']=list((win.x(),win.y(),win.width(),win.height()))
    check('quick control defaults to a visible native topmost window')
    state['quick_topmost']=False;publish();later(80,off)
def off():
    win=app.windows['quick'];assert win.isVisible() and not topmost(win)
    assert [win.x(),win.y(),win.width(),win.height()]==report['geometry']
    check('disabling topmost updates the open HWND without hiding or moving quick control')
    state['quick_topmost']=True;publish();later(80,on)
def on():
    win=app.windows['quick'];assert win.isVisible() and topmost(win)
    check('reenabling topmost immediately updates the same open quick window')
    app.show('main');later(200,main)
def main():
    assert app.windows['main'].isVisible() and not topmost(app.windows['main'])
    check('main window retains its normal stacking policy')
    app.show('notice');later(200,notice)
def notice():
    win=app.windows['notice'];assert win.isVisible() and topmost(win)
    assert s.GetWindowLong(int(win.winId()),-20)&0x08000000
    check('connection notice remains independently topmost and nonactivating')
    app.quit()
publish();app.show('quick');later(400,shown)
later(7000,lambda:(_ for _ in ()).throw(TimeoutError('topmost test timeout')))
try:app.run()
finally:
    report['result']='PASS' if len(report['checks'])==5 and not report['errors'] and not report['warnings'] else 'FAIL'
    out=ROOT/'verification/qt-topmost';out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
