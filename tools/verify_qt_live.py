"""Verify X3 state in all new pages, then a reversible noise/readback roundtrip."""
from pathlib import Path
from types import SimpleNamespace
import json,os,sys,time,traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
os.environ['ENCOLITE_DATA_DIR']=str(ROOT/'.install-test/qt-live-userdata')
os.environ['ENCOLITE_CAPTURE_DIR']=str(ROOT/'verification/qt-live-pages')
os.environ['ENCOLITE_DIAGNOSTICS']='1'
from encolite import windows_shell as shell
from encolite.native_desktop import NativeDesktop
from memory_metrics import process_memory,process_tree_memory
assert not shell.FindWindow('EncoLiteTray','Enco Lite tray'),'Close the running Enco Lite instance before live verification'
args=SimpleNamespace(fixture=False,tray_only=True,quick=False,test_timeout=0,
    test_report=ROOT/'verification/qt-live-backend.json')
app=NativeDesktop(ROOT,args);c=app.controller
c.connection_popup=False;c.sync()
report={'checks':[],'errors':[],'memory':{}}
stage=0;started=time.monotonic();deadline=0;original=None;target=None
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def tick():
    global stage,deadline,original,target
    try:
        now=time.monotonic()
        if now-started>65:raise TimeoutError(f'stage {stage}; status={c.status}')
        if stage==0:
            if not(c.session.connected and c.session.ready and not c.busy):return
            assert c.session.product_id=='067410',c.session.product_id
            original=c.session.noise
            report.update(model=c.session.device_name,firmware=c.session.firmware,product_id=c.session.product_id,
                original_noise=original,battery={key:value.percent if value else None for key,value in c.session.battery.items()},
                codec=c.session.codec,notifications=sorted(c.session.registered_events))
            report['memory']['tray_connected']=process_memory(os.getpid())
            check('real X3 handshake, battery, firmware and notifications through the unchanged Python Bluetooth backend')
            app.show('main');stage=1;deadline=now+3
        elif stage==1 and now>=deadline:
            app.send({'type':'inspect','id':'real-x3'});stage=2
        elif stage==2 and app.report.get('ui'):
            result=app.report['ui'][-1];report['ui']=result
            assert result['result']=='PASS',result
            assert result['model']=='OPPO Enco X3' and result['presets']>0 and result['switches']>0,result
            assert result['caption_absent'] and result['framework']=='Qt Quick',result
            assert Path(result['picture']).name=='067410.png',result
            check('all six Qt pages consume real model, image, feature, EQ and device data')
            report['memory']['after_page_inspection']={'backend':process_memory(os.getpid()),'gui':process_memory(app.gui.pid)}
            report['memory']['gui_tree']=process_tree_memory(app.gui.pid)
            target=next((mode for mode in ('transparency','off','smart') if mode!=original and mode in c.session.noise_modes),None)
            if target is None:
                report['noise_control']='SKIP: no alternate mode';stage=5
                app.send({'type':'quit'});return
            app.send({'type':'verify_action','name':'change_noise','args':[target]});stage=3;deadline=now+1
        elif stage==3 and not c.busy and now>=deadline:
            if c.session.noise!=target:
                assert c.session.noise==original and c.status.startswith('操作未完成'),c.status
                report['noise_control']='device rejected change; UI retained actual state and reported error'
                report['noise_rejection']=c.status
                check('device rejection leaves actual noise state intact')
                app.send({'type':'quit'});stage=5;return
            assert app.view.noise==target
            check('noise write and real readback reach the Qt UI state')
            report['noise_control']='PASS';app.send({'type':'verify_action','name':'change_noise','args':[original]});stage=4;deadline=now+1
        elif stage==4 and not c.busy and now>=deadline:
            assert c.session.noise==original and app.view.noise==original,c.status
            check('original noise mode restored and confirmed')
            app.send({'type':'quit'});stage=5;deadline=now+1
        elif stage==5 and app.gui is None and now>=deadline:
            assert c.session.connected
            report['memory']['tray_after_ui_closed']=process_memory(os.getpid())
            check('real connection survives graphical process release')
            app.quit()
    except Exception:
        report['errors'].append(traceback.format_exc());app.quit()
timer=app.loop.timer();timer.start(.25,tick,repeat=True)
try:app.run()
finally:
    timer.stop()
    if original and c.session.connected and c.session.noise!=original:
        try:c.session.set_noise(original)
        except Exception as error:report['errors'].append('restore: '+repr(error))
    app.close()
    report['slint_loaded']=any(key=='slint' or key.startswith('slint.') for key in sys.modules)
    report['result']='FAIL' if report['errors'] else 'PASS'
    (ROOT/'verification/qt-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    if report['errors']:raise SystemExit(1)
