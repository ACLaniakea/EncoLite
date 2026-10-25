"""End-to-end native tray, real UI callbacks, process release, and reopen checks."""
from pathlib import Path
from types import SimpleNamespace
import argparse,json,os,sys,time,traceback
SOURCE_ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--bundle',type=Path,default=SOURCE_ROOT)
parser.add_argument('--report',type=Path,default=SOURCE_ROOT/'verification/new-desktop.json')
parser.add_argument('--data-dir',type=Path,default=SOURCE_ROOT/'.install-test/new-desktop-userdata')
parser.add_argument('--hotkeys',action='store_true',help='Also reopen and switch windows using registered shortcut messages')
options=parser.parse_args()
ROOT=options.bundle
sys.path[:0]=[str(ROOT),str(SOURCE_ROOT/'tools')]
os.environ['ENCOLITE_DATA_DIR']=str(options.data_dir)
os.environ['ENCOLITE_CAPTURE_DIR']=str(SOURCE_ROOT/'verification/web-pages')
os.environ['ENCOLITE_DIAGNOSTICS']='1'
from encolite import windows_shell as shell
from encolite.native_desktop import NativeDesktop
from memory_metrics import process_memory,process_tree_memory

assert not shell.FindWindow('EncoLiteTray','Enco Lite tray'),'Close the running Enco Lite instance before regression tests'
args=SimpleNamespace(fixture=True,tray_only=True,quick=False,test_timeout=0,test_report=None)
app=NativeDesktop(ROOT,args)
if options.hotkeys:
    app.hotkeys.set_binding('show_quick',{'modifiers':7,'key':134})
    app.hotkeys.set_binding('show_main',{'modifiers':7,'key':133})
from encolite.protocol import Battery
app.controller.session.battery={'left':Battery(100,True),'right':Battery(0,True),'case':Battery(100,True)}
app.controller.sync()
report={'checks':[],'errors':[],'memory':{},'ui':None}
stage=0;started=time.monotonic();deadline=started+2;gui_pid=None
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def tick():
    global stage,deadline,gui_pid
    try:
        now=time.monotonic()
        if now-started>65:raise TimeoutError(f'stage {stage}; app={app.report}')
        if stage==0 and now>=deadline:
            assert app.gui is None
            assert 'slint' not in sys.modules
            report['memory']['tray_before']=process_memory(os.getpid())
            check('native tray starts without loading Slint or .NET')
            app.show('main');gui_pid=app.gui.pid;stage=1;deadline=now+3
        elif stage==1 and now>=deadline:
            app.send({'type':'test','id':'source-ui'});stage=2
        elif stage==2 and app.report.get('ui'):
            result=app.report['ui'][-1];report['ui']=result
            assert result['result']=='PASS',result
            assert result['caption_absent'],result
            assert result['full_client'],result
            report['memory']['main_and_backend']={'backend':process_memory(os.getpid()),'gui':process_memory(gui_pid)}
            report['memory']['gui_tree']=process_tree_memory(gui_pid)
            check('seven pages, shared control callbacks, persistent quick window, native chrome and window activation')
            stage=3;deadline=now+2
        elif stage==3 and app.gui is None and now>=deadline:
            assert app.controller.session.connected,'Closing UI released the earphone session'
            report['memory']['tray_after']=process_memory(os.getpid())
            assert not any(key=='slint' or key.startswith('slint.') for key in sys.modules)
            check('closing the last window releases the graphical process and keeps the session')
            if options.hotkeys:
                assert 'show_quick' in app.hotkeys.active and 'show_main' in app.hotkeys.active
                ident,value=app.hotkeys.active['show_quick']
                shell.PostMessage(app.tray.hwnd,0x312,ident,value['modifiers']|value['key']<<16)
                check('registered shortcuts survive disposal of the entire graphical process')
            else:app.tray._wndproc(app.tray.hwnd,0x8002,1,0)
            stage=4;deadline=now+3
        elif stage==4 and app.gui and now>=deadline:
            assert app.active_view=='quick' and app.report['gui_starts']==2
            check('one registered shortcut starts a fresh quick popup' if options.hotkeys else 'single quick-open tray request starts a fresh lightweight popup')
            if options.hotkeys:
                ident,value=app.hotkeys.active['show_main']
                shell.PostMessage(app.tray.hwnd,0x312,ident,value['modifiers']|value['key']<<16)
            else:
                original=shell.TrackPopupMenu
                shell.TrackPopupMenu=lambda *args:2
                try:app.tray.menu()
                finally:shell.TrackPopupMenu=original
            stage=5;deadline=now+1
        elif stage==5 and now>=deadline:
            assert app.active_view=='main' and app.report['gui_starts']==2
            check('one registered shortcut restores the main window' if options.hotkeys else 'one main-menu selection switches directly to the main window')
            app.quit()
    except Exception:
        report['errors'].append(traceback.format_exc());app.quit()
timer=app.loop.timer();timer.start(.2,tick,repeat=True)
try:app.run()
finally:
    timer.stop();app.close()
    report['backend']=app.report
    report['result']='FAIL' if report['errors'] else 'PASS'
    options.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    if report['errors']:raise SystemExit(1)
