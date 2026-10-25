"""Run production UI callbacks against X3 and restore its ANC setting."""
from pathlib import Path
import sys,os,json,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.build-deps'))
os.environ.setdefault('SLINT_BACKEND','winit-software')
import slint
from slint._native import native
from datetime import timedelta
from encolite.controller import Controller
from encolite.desktop import Desktop
controller=Controller(dispatch=native.invoke_from_event_loop)
desktop=Desktop(ROOT,controller,test_mode=True)
desktop.show_main();controller.start()
report={'checks':[]};stage=0;started=time.monotonic();original=None;target=None;errors=[];expect_rejection=False

def record(label):report['checks'].append(label);print('PASS',label,flush=True)

def tick():
 global stage,original,target,expect_rejection
 try:
  if time.monotonic()-started>45:raise RuntimeError('UI integration timed out: '+controller.status)
  if controller.busy:return
  s=controller.session
  if stage==0:
   if not s.connected:return
   assert s.product_id=='067410' and desktop.main.model_name=='OPPO Enco X3'
   assert desktop.main.left_value.endswith('%') and desktop.main.custom_available
   assert desktop.main.product_picture is not None
   original=s.noise;target='deep' if original!='deep' else 'smart'
   expect_rejection=any(s.wear_state.get(i)!='已佩戴' for i in (1,2))
   record('real state reaches main window');desktop.main.change_noise(target);stage=1
  elif stage==1:
   if expect_rejection:
    assert s.noise==original and desktop.main.noise==original and '操作未完成' in controller.status,controller.status
    record('headset refusal keeps actual UI state')
   else:
    assert s.noise==target and desktop.main.noise==target,controller.status
    record('main callback confirms ANC readback')
   current=s.noise
   desktop.show_quick();assert desktop.main is None and desktop.quick.noise==current
   record('lazy quick window shares real connection')
   if not expect_rejection:desktop.quick.change_noise(original)
   stage=2
  elif stage==2:
   assert s.noise==original and desktop.quick.noise==original
   record('quick window retains original ANC' if expect_rejection else 'quick callback restores original ANC')
   desktop.show_main();desktop.main.change_connection();stage=3
  elif stage==3:
   assert not s.connected and desktop.main.left_value=='—'
   record('disconnect clears stale values');desktop.main.change_connection();stage=4
  elif stage==4:
   assert s.connected and desktop.main.noise==original
   record('reconnect loads real state')
   for page in range(7):desktop.main.page=page
   controller.select_custom(1)
   assert controller._draft_id==s.custom_entries[0].id
   assert controller._draft_gains==list(s.custom_entries[0].gains)
   record('saved custom EQ loads into editor')
   desktop.hide_main();assert not controller.windows
   record('tray keeps live session without views')
   desktop.show_main();assert desktop.main.connected
   record('reopened window restores state');desktop.quit()
 except Exception as error:
  report['trace']=list(controller.session.trace)
  errors.append(f'stage {stage}: '+repr(error));desktop.quit()

timer=slint.Timer();timer.start(slint.TimerMode.Repeated,timedelta(milliseconds=150),tick)
try:native.run_event_loop()
finally:
 timer.stop()
 if original and controller.session.connected and controller.session.noise!=original:
  try:controller.session.set_noise(original)
  except Exception as error:errors.append('restoration: '+repr(error))
 controller.close();desktop.close()
 report['result']='FAIL' if errors else 'PASS';report['errors']=errors
 (ROOT/'verification/live-ui.json').write_text(json.dumps(report,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if errors:raise SystemExit(1)
