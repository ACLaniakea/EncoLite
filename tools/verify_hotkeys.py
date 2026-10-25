"""Isolated native registration, tray messages and actual WebView2 shortcut settings."""
from pathlib import Path
from types import SimpleNamespace
import ctypes as C,json,os,sys,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
data=ROOT/'.install-test/hotkeys';data.mkdir(parents=True,exist_ok=True)
os.environ['ENCOLITE_DATA_DIR']=str(data)
from encolite import windows_shell as shell
from encolite.hotkeys import ACTIONS,WindowsRegistration,Hotkeys
from encolite.native_desktop import NativeDesktop
from encolite.web_desktop import Desktop
from encolite.webview_native import Handler,call,checked,HRESULT
shell.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
placement={'bounds':[80,80,864,640,False],'page':2}
preferences=data/'preferences.json'
preferences.write_text(json.dumps({'web_main':placement,'theme_mode':'light','hotkeys':{'enabled':True,'bindings':{key:None for key,_ in ACTIONS}}}),'utf-8')
args=SimpleNamespace(fixture=True,tray_only=True,quick=False,test_timeout=0,test_report=None,isolated_tray=True)
backend=NativeDesktop(ROOT,args);gui=Desktop(ROOT);folder=ROOT/'verification/hotkeys';folder.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[]};messages=[];shown=[];other=None;external=None

def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def fail(error):report['errors'].append(str(error));backend.quit()
def deliver(data):
 gui.receive(json.loads(json.dumps(data)));return True
backend.send=deliver

def show(kind):
 shown.append(kind);backend.active_view=kind;backend.view.visible=True
 gui.receive(backend.payload());gui.show(kind)
backend.show=show

def send(kind,**values):
 messages.append({'type':kind,**values})
 backend.receive(json.loads(json.dumps({'type':kind,**values})))
gui.send=send

def execute(script,callback,kind='main'):
 def completed(status,value):
  try:
   checked(status)
   if value=='null':raise RuntimeError('Script failed: '+script)
   callback(json.loads(value))
  except Exception:fail(traceback.format_exc())
 handler=Handler('49511172-CC67-4BCA-9923-137112F4C4CC',completed,(HRESULT,W.LPCWSTR))
 window=gui.windows[kind];window.browser.handlers.append(handler)
 checked(call(window.browser.core,29,script,handler.pointer,types=(W.LPCWSTR,C.c_void_p)))
def soon(callback):gui.later(.15,callback)
def capture(name,callback):gui.windows['main'].browser.capture(folder/(name+'.png'),lambda:soon(callback))

# Register before any GUI exists, then post only this component's own registered WM_HOTKEY.
backend.hotkeys.set_binding('toggle_noise',{'modifiers':7,'key':128})
identifier,value=backend.hotkeys.active['toggle_noise']
shell.PostMessage(backend.tray.hwnd,0x312,identifier,7|128<<16)
def background():
 try:
  assert not gui.windows and backend.gui is None
  assert backend.controller.session.noise=='transparency'
  check('native tray receives registered shortcut messages with no graphical window')
  shell.PostMessage(backend.tray.hwnd,0x312,identifier,7|128<<16)
  gui.later(.1,restored)
 except Exception:fail(traceback.format_exc())
def restored():
 try:
  assert backend.controller.session.noise=='smart'
  check('noise shortcut restores the remembered ANC level through the real controller and fixture transport')
  show('main');gui.when_ready('main',lambda:soon(start))
 except Exception:fail(traceback.format_exc())
def start():
 execute("""(()=>{const button=document.querySelector('[data-hotkey-edit=toggle_noise]');button.scrollIntoView({block:'center'});button.click();return {dialog:!!document.querySelector('.hotkey-dialog'),rows:document.querySelectorAll('.hotkey-row').length}})()""",lambda result:opened(result))
def opened(result):
 assert result=={'dialog':True,'rows':5},result
 soon(record)
def record():
 try:
  assert backend.hotkeys.suspended and not backend.hotkeys.active
  check('opening the recorder suspends this application’s global shortcuts until editing completes')
  execute("""(()=>{document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'F18',code:'F18',ctrlKey:true,altKey:true,shiftKey:true,bubbles:true}));const value=document.querySelector('[data-hotkey-record-value]').textContent;document.querySelector('[data-hotkey-save]').click();return value})()""",lambda result:recorded(result))
 except Exception:fail(traceback.format_exc())
def recorded(result):
 assert result=='Ctrl + Alt + Shift + F18',result
 soon(saved)
def saved():
 try:
  assert not backend.hotkeys.suspended
  assert backend.hotkeys.config['bindings']['toggle_noise']=={'modifiers':7,'key':129}
  saved=json.loads(preferences.read_text('utf-8'));assert saved['web_main']==placement
  check('recorded keys save through the UI action bridge and native registration without erasing placement')
  global other,external
  other=shell.CreateWindow(0,backend.tray.class_name,'Enco Lite shortcut conflict probe',0,0,0,0,0,None,None,backend.tray.instance,None)
  assert other
  external=WindowsRegistration(other);assert external.register(0x7200,{'modifiers':7,'key':135})
  execute("document.querySelector('[data-hotkey-edit=toggle_noise]').click();true",lambda _:soon(conflict))
 except Exception:fail(traceback.format_exc())
def conflict():
 execute("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'F24',code:'F24',ctrlKey:true,altKey:true,shiftKey:true,bubbles:true}));document.querySelector('[data-hotkey-save]').click();true",lambda _:soon(conflicted))
def conflicted():
 try:
  assert backend.hotkeys.config['bindings']['toggle_noise']=={'modifiers':7,'key':129}
  check('Windows registration conflicts reject the new binding and preserve the saved shortcut')
  execute("({error:document.querySelector('[data-hotkey-record-error]').textContent,open:!!hotkeyEditor})",lambda result:conflict_visible(result))
 except Exception:fail(traceback.format_exc())
def conflict_visible(result):
 assert result['open'] and '占用' in result['error'],result
 capture('conflict-light',cancel)
def cancel():
 execute("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',code:'Escape',bubbles:true}));true",lambda _:soon(cancelled))
def cancelled():
 try:
  assert not backend.hotkeys.suspended and 'toggle_noise' in backend.hotkeys.active
  check('Escape cancels the editor without closing the window and restores the previous binding')
  backend.hotkeys.set_binding('show_quick',{'modifiers':7,'key':130})
  backend.hotkeys.set_binding('show_main',{'modifiers':7,'key':131})
  backend.publish()
  execute("document.querySelector('[data-switch=hotkeys_enabled]').click();true",lambda _:soon(disabled))
 except Exception:fail(traceback.format_exc())
def disabled():
 try:
  assert not backend.hotkeys.config['enabled'] and not backend.hotkeys.active
  probe=WindowsRegistration(other);assert probe.register(0x7201,{'modifiers':7,'key':129});probe.unregister(0x7201)
  check('the master switch immediately releases global registrations')
  execute("document.querySelector('[data-switch=hotkeys_enabled]').click();true",lambda _:soon(enabled))
 except Exception:fail(traceback.format_exc())
def enabled():
 try:
  assert len(backend.hotkeys.active)==3
  execute("document.querySelector('[data-hotkey-clear=show_main]').click();true",lambda _:soon(cleared))
 except Exception:fail(traceback.format_exc())
def cleared():
 try:
  assert backend.hotkeys.config['bindings']['show_main'] is None and 'show_main' not in backend.hotkeys.active
  check('clear removes the saved binding and unregisters the key immediately')
  backend.hotkeys.suspend();backend.capture_timer.start(.05,backend.end_hotkey_capture)
  soon(timeout_recovery)
 except Exception:fail(traceback.format_exc())
def timeout_recovery():
 try:
  assert not backend.hotkeys.suspended and len(backend.hotkeys.active)==2
  check('a bounded recorder lease restores registrations even if the renderer never ends capture')
  identifier,value=backend.hotkeys.active['show_quick'];shell.PostMessage(backend.tray.hwnd,0x312,identifier,value['modifiers']|value['key']<<16)
  gui.when_ready('quick',lambda:soon(quick))
 except Exception:fail(traceback.format_exc())
def quick():
 try:
  assert shown[-1]=='quick' and 'quick' in gui.windows
  check('the quick-control shortcut routes through the ordinary show path')
  # Check contextual noise controls in the actual quick window, including voice transparency.
  execute("""(()=>{const check=()=>({hidden:document.querySelector('[data-mode-row]').hidden,label:document.querySelector('[data-mode-label]').textContent,options:[...document.querySelector('[data-select=anc]').options].map(x=>x.value)});S.noise='off';update();const off=check();S.noise='transparency';if(!S.noise_options.some(x=>x.key==='vocal'))S.noise_options.push({key:'vocal',name:'人声通透'});update();const transparency=check();S.noise='deep';update();const anc=check();S.noise='transparency';S.noise_options=S.noise_options.filter(x=>x.key!=='vocal');update();return {off,transparency,anc,single:check()}})()""",lambda result:contextual(result),'quick')
 except Exception:fail(traceback.format_exc())
def contextual(result):
 assert result['off']['hidden'] and result['single']['hidden'],result
 assert not result['transparency']['hidden'] and result['transparency']['label']=='通透模式',result
 assert result['transparency']['options']==['transparency','vocal'],result
 assert not result['anc']['hidden'] and result['anc']['label']=='降噪强度' and 'vocal' not in result['anc']['options'],result
 check('quick window hides ANC controls in off mode and substitutes only supported transparency submodes')
 show('main');gui.when_ready('main',lambda:soon(main_context))
def main_context():
 execute("""(()=>{navigatePage(0);S.noise='off';update();const hidden=document.querySelector('[data-mode-row]').hidden;S.noise='transparency';if(!S.noise_options.some(x=>x.key==='vocal'))S.noise_options.push({key:'vocal',name:'人声通透'});update();const select=document.querySelector('[data-select=anc]');select.value='vocal';select.dispatchEvent(new Event('change',{bubbles:true}));return {hidden,label:document.querySelector('[data-mode-label]').textContent,options:[...select.options].map(x=>x.value)}})()""",lambda result:main_context_done(result))
def main_context_done(result):
 assert result=={'hidden':True,'label':'通透模式','options':['transparency','vocal']},result
 soon(voice_applied)
def voice_applied():
 try:
  assert any(message.get('name')=='change_noise' and message.get('args')==['vocal'] for message in messages),messages
  backend.controller.set_status('已连接');backend.controller.sync()
  check('main-window transparency submenu routes the distinct voice-transparency argument to the controller')
  execute("navigatePage(2);S.theme_mode='dark';applyAppearance();document.querySelector('.hotkey-settings').scrollIntoView({block:'start'});true",lambda _:gui.later(.2,lambda:capture('settings-dark',restart)))
 except Exception:fail(traceback.format_exc())
def restart():
 try:
  saved=json.loads(preferences.read_text('utf-8'));backend.hotkeys.close()
  restarted=Hotkeys(WindowsRegistration(backend.tray.hwnd),saved['hotkeys'],lambda _:None,lambda _:None)
  assert len(restarted.active)==2 and restarted.config['bindings']['show_main'] is None
  restarted.close();assert external.register(0x7201,{'modifiers':7,'key':129});external.unregister(0x7201)
  check('saved bindings restore on a fresh manager; shutdown releases them for other applications')
  backend.quit()
 except Exception:fail(traceback.format_exc())
gui.later(.12,background);gui.later(35,lambda:fail('shortcut verification timed out'))
try:backend.loop.run()
finally:
 backend.close();gui.quit()
 if external:external.unregister(0x7200)
 if other:shell.DestroyWindow(other)
 if gui.environment:gui.environment.close()
 shell.DestroyWindow(gui.owner)
 report['result']='FAIL' if report['errors'] else 'PASS'
 (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
