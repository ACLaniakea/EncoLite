"""Measure the complete Qt client with real Bluetooth; no earbud setting writes."""
from pathlib import Path
import json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
OUT=ROOT/'verification/qt-memory';OUT.mkdir(parents=True,exist_ok=True)
CONTROL=OUT/'control.json';STATE=OUT/'state.json'

def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False),'utf-8');temp.replace(path)

def worker():
    from types import SimpleNamespace
    from encolite.native_desktop import NativeDesktop
    os.environ['ENCOLITE_DATA_DIR']=str(ROOT/'.install-test/qt-memory-data')
    app=NativeDesktop(ROOT,SimpleNamespace(fixture=False,tray_only=True,quick=False,test_timeout=0,test_report=OUT/'backend.json'))
    app.controller.connection_popup=False;app.controller.sync()
    requested=None;stage=None;started=time.monotonic()
    def tick():
        nonlocal requested,stage
        if time.monotonic()-started>240:app.quit();return
        c=app.controller
        if not(c.session.connected and c.session.ready and not c.busy):return
        command=json.loads(CONTROL.read_text('utf-8'))['stage']
        if command!=requested:
            requested=command;stage=None
            if command=='quit':app.quit();return
            if command=='tray':app.send({'type':'quit'})
            else:app.show(command)
        settled=(app.gui is None) if command=='tray' else app.gui is not None and app.active_view==command
        if settled and stage!=command:
            stage=command
            write(STATE,{'stage':stage,'pid':os.getpid(),'gui_pid':app.gui.pid if app.gui else None,
                'connected':c.session.connected,'ready':c.session.ready,'model':c.session.device_name,'fixture':False})
    timer=app.loop.timer();timer.start(.25,tick,repeat=True)
    try:app.run()
    finally:timer.stop();app.close()

def measure():
    import datetime,statistics
    sys.path.insert(0,str(ROOT/'.build-deps'))
    import psutil
    from memory_metrics import process_tree_memory
    from encolite import windows_shell as shell
    assert not shell.FindWindow('EncoLiteTray','Enco Lite tray'),'Exit client before measurement'
    report={'framework':'Qt Quick / PySide6 6.12.0','date':datetime.datetime.now().astimezone().isoformat(),
        'conditions':{'warmup_seconds':25,'samples':15,'interval_seconds':.5,'real_bluetooth':True,
        'forced_gc_or_working_set_trim':False,'source':'complete current source with official embedded Python 3.13.17',
        'notes':['USS excludes shared resident pages; private bytes measure committed memory.',
                 'Short sequential measurements, not a long-duration leak test.',
                 'Original and WebView2 baseline were measured earlier on the same machine; not simultaneously.']},'measurements':{}}
    STATE.unlink(missing_ok=True);write(CONTROL,{'stage':'main'})
    host=ROOT/'.tools/python-3.13.17-embed-amd64/pythonw.exe'
    p=subprocess.Popen([str(host),str(Path(__file__)),'--worker'],cwd=ROOT)
    try:
        for stage in ('main','quick','tray'):
            write(CONTROL,{'stage':stage});deadline=time.monotonic()+65
            while True:
                assert p.poll() is None,'Backend exited'
                state=json.loads(STATE.read_text('utf-8')) if STATE.exists() else {}
                if state.get('stage')==stage:break
                assert time.monotonic()<deadline,('Bluetooth/window timeout',stage,state)
                time.sleep(.2)
            if stage!='tray':
                title='Enco Lite · '+('耳机助手' if stage=='main' else '快捷控制')
                for _ in range(150):
                    hwnd=shell.FindWindow(None,title)
                    if hwnd and shell.IsWindowVisible(hwnd):break
                    time.sleep(.1)
                else:raise RuntimeError('Expected Qt window not visible')
            print('WARMUP',stage,flush=True);time.sleep(25)
            samples=[]
            for _ in range(15):
                assert p.poll() is None
                tree=process_tree_memory(p.pid)
                for row in tree['processes']:row['uss']=psutil.Process(row['pid']).memory_full_info().uss
                assert not any('webview' in row['name'].lower() for row in tree['processes'])
                tree['uss_sum']=sum(row['uss'] for row in tree['processes']);samples.append(tree);time.sleep(.5)
            result={'connection':state,'process_count':len(samples[-1]['processes']),'samples':samples}
            for key in ('uss_sum','private_bytes_sum','working_set_sum'):
                result['mean_'+key+'_mib']=round(statistics.mean(s[key] for s in samples)/1048576,2)
            report['measurements'][stage]=result
            write(OUT/'report.json',report)
            print(json.dumps({stage:{k:v for k,v in result.items() if k!='samples'}},ensure_ascii=True),flush=True)
        report['result']='PASS';write(OUT/'report.json',report)
    finally:
        write(CONTROL,{'stage':'quit'})
        try:p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            subprocess.run([str(host),str(ROOT/'desktop_entry.py'),'--quit'],timeout=10);p.wait(timeout=15)

if __name__=='__main__':worker() if '--worker' in sys.argv else measure()
