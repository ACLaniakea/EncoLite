"""Check rendered corner contours and native clipping at the selected DPI."""
from pathlib import Path
import ctypes as C,json,math,os,sys,traceback
ROOT=Path(__file__).resolve().parents[1];TARGET=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT
sys.path[:0]=[str(TARGET),str(TARGET/'qt' if TARGET!=ROOT else ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8')
from PySide6.QtCore import QTimer,Qt,qInstallMessageHandler
from encolite.qt_desktop import Desktop
OUT=ROOT/'verification/qt-corners';OUT.mkdir(parents=True,exist_ok=True)
tag=os.environ.get('ENCOLITE_CORNER_TAG','default')
report={'checks':[],'errors':[],'warnings':[],'target':str(TARGET),'pixel_ratios':[]}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(TARGET,read_pipe=False)
state={'connected':False,'fast_mode':True,'system_motion':True,'dark':False,'noise_options':[],
       'palette':{'line':'#f03636'}}
get=C.windll.dwmapi.DwmGetWindowAttribute
get.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_uint];get.restype=C.c_long
def later(ms,fn):
    def run():
        try:fn()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    QTimer.singleShot(ms,run)
def check(text):report['checks'].append(text);print('PASS',text,flush=True)
def verify(win,label,rounded=True):
    image=win.grabWindow();image.save(str(OUT/(tag+'-'+label+'.png')))
    dpr=image.width()/win.width();report['pixel_ratios'].append(dpr)
    native=C.c_int();result=get(int(win.winId()),33,C.byref(native),C.sizeof(native))
    if result==0:assert native.value==1,'DWM must not apply another corner contour'
    width,height=image.width(),image.height()
    if rounded:
        assert image.pixelColor(0,height-1).alpha()==0 and image.pixelColor(width-1,height-1).alpha()==0
        radius=12*dpr;stroke_mid=radius-.5*dpr
        for side in ('left','right'):
            for angle in (0,15,30,45,60,75,90):
                theta=math.radians(angle);x=radius-stroke_mid*math.cos(theta)
                if side=='right':x=width-x-1
                y=height-radius+stroke_mid*math.sin(theta)-.5
                pixels=[image.pixelColor(xx,yy) for xx in range(max(0,round(x)-1),min(width,round(x)+2))
                        for yy in range(max(0,round(y)-1),min(height,round(y)+2))]
                assert any(p.alpha()>80 and p.red()-p.green()>70 for p in pixels),(label,dpr,side,angle)
    else:
        assert image.pixelColor(0,height-1).alpha()==255 and image.pixelColor(width-1,height-1).alpha()==255
    check(label+': continuous lower outline follows the alpha contour without native recutting')
def cycle(index=0):
    if index==6:return resized()
    kind=('main','quick','notice')[index%3];state['dark']=index>=3
    app.receive({'type':'state','state':state,'preferences':{}});app.show(kind)
    def shown():
        verify(app.windows[kind],kind+('-dark' if state['dark'] else '-light'))
        app.close_view(kind,exiting=False,animate=False);later(50,lambda:cycle(index+1))
    later(220,shown)
def resized():
    app.show('main');win=app.windows['main'];win.setWidth(740);win.setHeight(560)
    def ready():
        verify(win,'main-minimum');win.showMaximized();later(220,maximized)
    later(220,ready)
def maximized():
    win=app.windows['main'];assert win.windowState()==Qt.WindowMaximized
    verify(win,'main-maximized',False);assert not report['warnings'],report['warnings'];app.quit()
later(0,cycle);later(10000,lambda:(_ for _ in ()).throw(TimeoutError('corner test timeout')))
try:app.run()
finally:
    report['result']='PASS' if len(report['checks'])==8 and not report['errors'] and not report['warnings'] else 'FAIL'
    (OUT/(tag+'-report.json')).write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
