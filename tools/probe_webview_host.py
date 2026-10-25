"""Exercise the official WebView2 loader, compositor and two-way local messages."""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import json,os,sys
os.environ['ENCOLITE_DIAGNOSTICS']='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from encolite import windows_shell as s
from encolite.native_loop import NativeLoop
from encolite.webview_native import Environment,Browser
s.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
loop=NativeLoop();report={'result':'FAIL','errors':[]};env=None;browser=None
@s.WNDPROC
def proc(hwnd,msg,wp,lp):
    if msg==0x8003 or msg==0x113 and wp==2:loop.drain();return 0
    if msg==5 and browser:browser.resize();return 0
    if msg==0x10:loop.quit();return 0
    return s.DefWindowProc(hwnd,msg,wp,lp)
kind=s.WndClass(name='EncoLiteWebProbe',proc=proc,instance=s.GetModuleHandle(None),background=C.c_void_p(6))
s.RegisterClass(C.byref(kind))
hwnd=s.CreateWindow(0,'EncoLiteWebProbe','Enco Lite WebView2 check',0x10CF0000,300,220,860,600,None,None,kind.instance,None)
assert hwnd
loop.hwnd=hwnd
def receive(data):
    print('MESSAGE',data,flush=True)
    if data.get('type')=='ready':browser.send({'echo':'降噪与通透'})
    if data.get('echo')=='降噪与通透':
        report.update(result='PASS',version=env.version,message='UTF-8 roundtrip rendered');loop.quit()
def ready():
    global browser
    print('ENVIRONMENT',env.version,flush=True)
    browser=Browser(env,hwnd,"""<!doctype html><meta charset=utf-8><style>body{background:#f6f8f7;color:#20352c;font:18px 'Segoe UI',sans-serif;padding:40px}button{background:#17684b;color:white;border:0;border-radius:10px;padding:12px 30px}</style><h1>Enco Lite</h1><p>OPPO 耳机控制</p><button>降噪</button><script>chrome.webview.addEventListener('message',e=>{document.querySelector('p').textContent=e.data.echo;chrome.webview.postMessage(JSON.stringify(e.data))});chrome.webview.postMessage(JSON.stringify({type:'ready'}));</script>""",receive,lambda:print('CONTROLLER',flush=True))
def failed(error):report['errors'].append(error);loop.quit()
timeout=loop.timer();timeout.start(25,lambda:failed('WebView2 rendering timeout'))
try:
    loader=ROOT/'WebView2Loader.dll'
    if not loader.exists():loader=ROOT/'.tools/webview2/WebView2Loader.dll'
    env=Environment(loader,ROOT/'.install-test/webview-probe-data',lambda:loop.post(ready),failed)
    loop.run()
finally:
    if browser:browser.close()
    if env:env.close()
    s.DestroyWindow(hwnd)
    destination=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'verification/webview-probe.json'
    destination.write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
