"""Exercise actual window placement across two independent app processes."""
from pathlib import Path
import os,sys,subprocess,json
ROOT=Path(__file__).resolve().parents[1]
PREFS=ROOT/'verification/persistence-test.json'
if len(sys.argv)==1:
    PREFS.unlink(missing_ok=True)
    try:
        for phase in ('write','read','write-max','read-max'):
            subprocess.run([sys.executable,__file__,phase],check=True,timeout=20)
        report={'result':'PASS','checks':['main placement and page across process restart','quick placement across process restart','appearance edits preserve placement','maximized state and normal restore across restart']}
        (ROOT/'verification/window-persistence.json').write_text(json.dumps(report,indent=2),'utf-8')
        print(json.dumps(report),flush=True)
    finally:PREFS.unlink(missing_ok=True)
    raise SystemExit()
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
os.environ.setdefault('SLINT_BACKEND','winit-software')
import slint
from slint._native import native
from datetime import timedelta
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.desktop import Desktop
controller=Controller(session=DemoSession(),preferences=PREFS,dispatch=native.invoke_from_event_loop)
desktop=Desktop(ROOT,controller,test_mode=True)
shell=desktop.native_shell
phase=sys.argv[1];expected=controller.preference_data.copy();stage=0;errors=[]

def tick():
    global stage
    try:
        if phase.startswith('write'):
            if stage==0:
                desktop.main.page=5
                shell.SetWindowPos(desktop.main_hwnd,None,110,100,1800,1320,0x14)
                stage=1
            elif stage==1 and phase=='write-max':
                desktop.main.window_maximized=True;stage=2
            elif stage in (1,2) and desktop.main is not None:
                desktop.hide_main()
                bounds=controller.preference_data['main_window']['bounds'];assert bounds
                controller.change_theme(True)
                assert controller.preference_data['main_window']['page']==5
                desktop.show_quick();stage=2
            else:
                desktop.close_quick()
                assert controller.preference_data['quick_window']['bounds']
                desktop.quit()
        elif stage==0:
            assert desktop.main.window_maximized==(phase=='read-max')
            assert desktop.main.page==5
            assert desktop.main.dark
            actual=shell.window_placement(desktop.MAIN_TITLE)
            if phase=='read-max':
                desktop.main.window_maximized=False;stage=1
            else:
                assert actual[:4]==tuple(expected['main_window']['bounds'][:4]),(actual,expected)
                desktop.show_quick();stage=2
        elif stage==1:
            actual=shell.window_placement(desktop.MAIN_TITLE)
            assert actual[:4]==tuple(expected['main_window']['bounds'][:4]),(actual,expected)
            desktop.show_quick();stage=2
        else:
            actual=shell.window_placement(desktop.QUICK_TITLE)
            assert actual[:4]==tuple(expected['quick_window']['bounds'][:4]),(actual,expected)
            desktop.quit()
    except Exception as error:
        errors.append(f'stage {stage}: {error!r}; saved={expected}; current_max={desktop.main.window_maximized if desktop.main else None}; current_page={desktop.main.page if desktop.main else None}');desktop.quit()

desktop.show_main();timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=600),tick)
try:native.run_event_loop()
finally:
    timer.stop();controller.close();desktop.close()
    print(phase,errors or 'PASS',flush=True)
    if errors:raise SystemExit(1)
