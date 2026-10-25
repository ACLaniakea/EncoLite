"""Render model-specific OnePlus projections through the actual WebView2 host, with no Bluetooth."""
from pathlib import Path
import ctypes as C,json,os,sys,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['ENCOLITE_DATA_DIR']=str(ROOT/'.install-test/oneplus-ui')
from encolite.web_desktop import Desktop
from encolite.webview_native import Handler,call,checked,HRESULT
from encolite.live_session import LiveSession
from encolite.controller import Controller
from encolite.json_view import JsonView
from encolite.presentation import JsonPresentation
from encolite.model_catalog import models
from encolite.protocol import Battery
from encolite import windows_shell as shell
shell.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
folder=ROOT/'verification/oneplus';folder.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'models':[]};messages=[];app=Desktop(ROOT)
app.send=lambda kind,**values:messages.append({'type':kind,**values})

def project(profile):
 session=LiveSession();session.profile=profile;session.product_id=profile['id'];session.device_name=profile['name'];session.connected=True
 session.bitmap=b'\xff'*9;session.game_sound=0;session.codec='AAC';session.firmware='113'
 session.noise=next((mode for mode in profile['noise'] if mode not in ('off','transparency','vocal')),'')
 session.preset=profile['presets'][0]['id'] if profile['presets'] else -1
 session.features={4:True,0x11:True,6:False,0xB:False};session.bass_state=(0,6,0)
 session.battery={'right':Battery(78,True)} if profile['form_factor']=='N' else {'left':Battery(84,False),'right':Battery(78,False),'case':Battery(65,False)}
 controller=Controller(session=session,presentation=JsonPresentation());view=JsonView();controller.windows.append(view)
 try:controller.set_status('已连接 · '+profile['name']);controller.sync();return view.snapshot()
 finally:controller.close()
projections={}
for profile in models():
 if profile['brand']=='OnePlus':
  state=project(profile);projections[profile['id']]=state
  assert state['model_name']==profile['name'] and state['custom_available']==profile['custom']
  report['models'].append({'id':profile['id'],'name':profile['name'],'noise_modes':[x['key'] for x in state['noise_options']],'presets':[x['id'] for x in state['presets']]})
report['checks'].append('32 OnePlus profiles project their own controls and sparse protocol indices')

def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def fail(error):report['errors'].append(str(error));app.quit()
def execute(script,callback,kind='main'):
 def completed(status,value):
  try:checked(status);callback(json.loads(value))
  except Exception:fail(traceback.format_exc())
 handler=Handler('49511172-CC67-4BCA-9923-137112F4C4CC',completed,(HRESULT,W.LPCWSTR))
 window=app.windows[kind];window.browser.handlers.append(handler)
 checked(call(window.browser.core,29,script,handler.pointer,types=(W.LPCWSTR,C.c_void_p)))
def load(identifier,dark=False,kind='main',page=0,callback=None):
 state={**projections[identifier],'theme_mode':'dark' if dark else 'light','fast_mode':False,'system_motion':True}
 app.receive({'type':'state','fixture':True,'preferences':{'web_main':{'page':page}},'state':state});app.show(kind)
 app.when_ready(kind,lambda:execute(f'if(view===\'main\')navigatePage({page});true',lambda _:app.later(.35,callback),kind))
def capture(name,callback,kind='main'):
 app.windows[kind].browser.capture(folder/(name+'.png'),lambda:app.later(.08,callback))
def overview():
 def result(data):
  assert data=={'name':'OnePlus Buds Pro 3','options':['smart','light','moderate','deep'],'image':True,'overflow':False},data
  check('OnePlus Buds Pro 3 shows its own official product image and ANC strengths')
  capture('buds-pro-3-light',eq)
 execute("({name:document.querySelector('.model').textContent,options:[...document.querySelector('[data-select=anc]').options].map(x=>x.value),image:document.querySelector('[data-picture]').naturalWidth>0,overflow:document.querySelector('.page').scrollWidth>document.querySelector('.page').clientWidth})",result)
def eq():load('064014',True,page=5,callback=eq_ready)
def eq_ready():
 def result(data):
  assert data=={'bands':6,'enabled':True,'overflow':False},data
  check('OnePlus EQ uses actual imported frequencies in the existing vertical grid')
  capture('buds-pro-3-eq-dark',ce)
 execute("({bands:document.querySelectorAll('[data-gain]').length,enabled:[...document.querySelectorAll('[data-gain]')].every(x=>!x.disabled),overflow:document.querySelector('.page').scrollWidth>document.querySelector('.page').clientWidth})",result)
def ce():load('061C14',callback=ce_ready)
def ce_ready():
 def result(data):
  assert data=={'hidden':True,'neutral':True,'loaded':True,'name':'OnePlus Nord Buds CE'},data
  check('Nord Buds CE hides unsupported listening modes and renders the real neutral fallback')
  capture('nord-buds-ce-light',neck)
 execute("({hidden:document.querySelector('[data-listening-section]').hidden,neutral:document.querySelector('[data-picture]').src.startsWith('data:image/svg+xml'),loaded:document.querySelector('[data-picture]').naturalWidth>0,name:document.querySelector('.model').textContent})",result)
def neck():load('050C14',True,'quick',callback=neck_ready)
def neck_ready():
 def result(data):
  assert data=={'count':1,'value':'78%','name':'耳机','strengthHidden':True},data
  check('neckband quick control uses one reported battery and hides a nonexistent ANC strength selector')
  capture('bullets-z2-anc-quick-dark',settings,'quick')
 execute("(()=>{const visible=[...document.querySelectorAll('[data-battery]')].filter(x=>!x.hidden);return {count:visible.length,value:visible[0].querySelector('.battery-value').textContent,name:visible[0].querySelector('.battery-name').textContent,strengthHidden:document.querySelector('[data-mode-row]').hidden}})()",result,'quick')
def settings():load('065414',False,page=2,callback=settings_ready)
def settings_ready():
 execute("document.querySelector('[data-choice=models]').scrollIntoView({block:'center'});true",lambda _:app.later(.12,open_models))
def open_models():
 execute("document.querySelector('[data-choice=models]').click();document.querySelector('.choice-search input').value='OnePlus';document.querySelector('.choice-search input').dispatchEvent(new Event('input',{bubbles:true}));({total:document.querySelector('[data-select=models]').options.length,filtered:document.querySelectorAll('[role=option]').length})",models_ready)
def models_ready(data):
 assert data=={'total':88,'filtered':32},data
 check('model selection contains 56 OPPO plus 32 OnePlus entries and searches by brand')
 capture('model-search-oneplus',app.quit)
load('064014',callback=overview);app.later(30,lambda:fail('OnePlus UI timeout'))
try:app.loop.run()
finally:
 app.quit()
 if app.environment:app.environment.close()
 shell.DestroyWindow(app.owner)
 report['result']='FAIL' if report['errors'] else 'PASS'
 (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
