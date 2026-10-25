"""Exercise themed selectors and page layouts in the application's actual WebView2 host."""
from pathlib import Path
import ctypes as C,json,os,sys,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['ENCOLITE_DATA_DIR']=str(ROOT/'.install-test/web-controls')
from encolite.web_desktop import Desktop
from encolite.webview_native import Handler,call,checked,HRESULT
from encolite import windows_shell as shell
shell.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
folder=ROOT/'verification/web-controls';folder.mkdir(parents=True,exist_ok=True)
app=Desktop(ROOT);messages=[];report={'checks':[],'errors':[],'layouts':{}}
app.send=lambda kind,**values:messages.append({'type':kind,**values})
models=sorted(json.loads((ROOT/'encolite/oppo_models.json').read_text('utf-8')),key=lambda item:item['name'])
state={'model_name':'OPPO Enco X3','connected':True,'busy':False,'status':'已连接 · OPPO Enco X3',
 'theme_mode':'light','system_motion':True,'fast_mode':False,'connection_popup':True,
 'firmware':'112.112.119','device_info':'112.112.119 · LHDC · 左耳已佩戴 · 右耳已佩戴',
 'left_value':'90%','right_value':'85%','case_value':'75%',
 'left_level':.9,'right_level':.85,'case_level':.75,'left_charging':True,'right_charging':True,
 'noise':'smart','anc_level':'smart','can_anc':True,'can_transparency':True,'can_off':True,'can_equalizer':True,
 'noise_options':[{'key':key,'name':name} for key,name in [('off','关闭'),('transparency','通透'),('smart','智能降噪'),('light','轻度降噪'),('moderate','中度降噪'),('deep','深度降噪')]],
 'presets':[{'id':i,'name':name} for i,name in enumerate(['原音','纯粹人声','澎湃低音','清澈人声','古典','自然','自定义'])],'preset':0,
 'switches':[{'key':key,'title':title,'detail':detail,'checked':True,'enabled':True} for key,title,detail in [('wear','佩戴检测','摘下暂停，戴上继续'),('dual','双设备连接','同时连接两台设备'),('voice','人声增强','突出音乐中的人声'),('long','长续航模式','以音质设置换取更长续航')]],
 'custom_available':True,'custom_names':['新增音效','我的音效'],'custom_index':1,'eq_name':'我的音效','eq_minimum':-6,'eq_maximum':6,
 'bands':[{'label':label,'gain':gain} for label,gain in zip(['62 Hz','250 Hz','1 kHz','4 kHz','8 kHz','16 kHz'],[-6,-3,0,2,4,6])],
 'device_names':['OPPO Enco X3'],'device_index':0,'model_names':[p['name'] for p in models],'model_index':next(i for i,p in enumerate(models) if p['name']=='OPPO Enco X3'),
 'multi_available':True,'multi_writable':True,'priority_text':'管理耳机的设备连接',
 'multi_devices':[{'name':'此电脑','address':'01:02:03:04:05:06','detail':'已连接 · 此电脑','connected':True},{'name':'OPPO Find X8','address':'02:03:04:05:06:07','detail':'未连接','connected':False}]}
picture=ROOT/'ui/assets/models/067410.png'
if picture:state['product_picture']=str(picture)
app.receive({'type':'state','fixture':True,'preferences':{'web_main':{'page':2}},'state':state})
def fail(error):report['errors'].append(str(error));app.quit()
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def execute(script,callback,kind='main'):
 def completed(status,value):
  try:checked(status);callback(json.loads(value))
  except Exception:fail(traceback.format_exc())
 handler=Handler('49511172-CC67-4BCA-9923-137112F4C4CC',completed,(HRESULT,W.LPCWSTR))
 window=app.windows[kind];window.browser.handlers.append(handler)
 checked(call(window.browser.core,29,script,handler.pointer,types=(W.LPCWSTR,C.c_void_p)))
def capture(name,next_step,kind='main'):
 app.later(.18,lambda:app.windows[kind].browser.capture(folder/(name+'.png'),lambda:app.later(.08,next_step)))
bounds="""(()=>{const popup=document.querySelector('.choice-popup'),r=popup.getBoundingClientRect();return {inside:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,side:popup.dataset.side,options:popup.querySelectorAll('[role=option]').length,shadow:getComputedStyle(popup).boxShadow,active:document.activeElement.className}})()"""
def start():
 def result(value):
  assert value['hidden'] and value['options']==3 and value['selected']=='浅色',value
  assert value['label']=='外观' and value['expanded']=='true',value
  check('visible selector and listbox share theme, labels and selected state; native menu stays hidden')
  execute(bounds,lambda data:report['layouts'].update(theme_menu=data))
  capture('settings-light',keyboard)
 execute("""(()=>{const trigger=document.querySelector('[data-choice=theme]');trigger.click();return {hidden:getComputedStyle(document.querySelector('[data-select=theme]')).display==='none',options:document.querySelectorAll('[role=option]').length,selected:document.querySelector('[aria-selected=true]').textContent.trim(),label:trigger.getAttribute('aria-label'),expanded:trigger.getAttribute('aria-expanded')}})()""",result)
def keyboard():
 def result(data):
  assert data=={'value':'dark','closed':True,'focused':True},data
  writes=[m['args'] for m in messages if m.get('name')=='change_theme_mode'];assert writes==[['dark']],writes
  check('keyboard End/Enter commits exactly one existing theme action and restores focus')
  state['theme_mode']='dark';app.receive({**app.payload,'state':state})
  app.later(.15,escape)
 execute("""(()=>{document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true}));document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return {value:document.querySelector('[data-select=theme]').value,closed:!document.querySelector('.choice-popup'),focused:document.activeElement.dataset.choice==='theme'}})()""",result)
def escape():
 before=len([m for m in messages if m.get('type')=='window' and m.get('name')=='close'])
 def result(data):
  assert data=={'closed':True,'focused':True,'value':'dark'},data
  after=len([m for m in messages if m.get('type')=='window' and m.get('name')=='close']);assert before==after
  check('Escape dismisses the selector without changing its value or closing the window')
  execute("document.querySelector('[data-choice=theme]').click();true",lambda _:capture('settings-dark',outside))
 execute("""(()=>{document.querySelector('[data-choice=theme]').click();document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp',bubbles:true}));document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return {closed:!document.querySelector('.choice-popup'),focused:document.activeElement.dataset.choice==='theme',value:document.querySelector('[data-select=theme]').value}})()""",result)
def outside():
 def result(data):
  assert data=={'outside':True,'tab':True,'focus':'theme'},data
  check('outside clicks and Tab dismiss menus; focus returns to the natural tab sequence')
  window=app.windows['main'];scale=(shell.GetDpiForWindow(window.hwnd) or 96)/96
  shell.SetWindowPos(window.hwnd,None,0,0,round(740*scale),round(560*scale),0x16)
  execute("document.querySelector('[data-choice=models]').scrollIntoView({block:'center'});true",lambda _:app.later(.12,search))
 execute("""(()=>{document.querySelector('.heading').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));const outside=!document.querySelector('.choice-popup');document.querySelector('[data-choice=theme]').click();document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));return {outside,tab:!document.querySelector('.choice-popup'),focus:document.activeElement.dataset.choice}})()""",result)
def search():
 def result(data):
  assert data['inside'] and data['options']>40,data
  check('long model list scrolls within the compact window and opens above the trigger when needed')
  report['layouts']['models_menu']=data
  capture('models-dark-compact',filter_models)
 execute("document.querySelector('[data-choice=models]').click();"+bounds,result)
def filter_models():
 def result(data):
  assert data['matches']>0 and data['allMatch'] and data['none']==0 and data['empty']=='没有匹配项',data
  check('model search filters names and presents a clean empty state')
  execute("closeChoice();navigatePage(0);true",lambda _:app.later(.15,lambda:page_layout(0)))
 execute("""(()=>{const search=document.querySelector('.choice-search input');search.value='X3';search.dispatchEvent(new Event('input',{bubbles:true}));const matches=[...document.querySelectorAll('[role=option]')];const value={matches:matches.length,allMatch:matches.every(x=>x.textContent.includes('X3'))};search.value='does not exist';search.dispatchEvent(new Event('input',{bubbles:true}));return {...value,none:document.querySelectorAll('[role=option]').length,empty:document.querySelector('.choice-empty').textContent}})()""",result)
pages=[0,1,4,5,6,2,3]
def page_layout(index):
 number=pages[index]
 def result(data):
  assert not data['overflow'] and not data['nativeVisible'],(number,data)
  assert not data['filler'],(number,data)
  report['layouts']['compact_page_'+str(number)]=data
  def next_page():
   if index+1<len(pages):execute(f'navigatePage({pages[index+1]});true',lambda _:app.later(.16,lambda:page_layout(index+1)))
   else:busy()
  capture('page-'+str(number)+'-dark-compact',next_page)
 execute("""(()=>{const page=document.querySelector('.page');return {overflow:page.scrollWidth>page.clientWidth+1,nativeVisible:[...document.querySelectorAll('select')].some(x=>getComputedStyle(x).display!=='none'),filler:/留一点空间|随时继续聆听|让耳机控制回到简单|音效选项会根据/.test(document.body.textContent),height:page.scrollHeight,viewportHeight:page.clientHeight}})()""",result)
def busy():
 check('all seven pages fit the compact width without native select controls or filler copy')
 def result(data):
  assert data=={'closed':True,'disabled':True},data
  check('an incoming busy state disables the control and closes a stale hardware menu')
  state.update(busy=False,fast_mode=True);app.receive({**app.payload,'state':state})
  app.later(.1,speed)
 execute("navigatePage(1);document.querySelector('[data-choice=presets]').click();S.busy=true;update();({closed:!document.querySelector('.choice-popup'),disabled:document.querySelector('[data-choice=presets]').disabled})",result)
def speed():
 def result(data):
  assert data=={'shadow':'none','animations':0},data
  check('speed mode also removes dropdown shadows and animation')
  execute("closeChoice();true",lambda _:quick())
 execute("document.querySelector('[data-choice=presets]').click();({shadow:getComputedStyle(document.querySelector('.choice-popup')).boxShadow,animations:document.getAnimations().filter(x=>x.playState==='running').length})",result)
def quick():
 app.show('quick');app.when_ready('quick',lambda:app.later(.15,quick_menu))
def quick_menu():
 def result(data):
  assert data['inside'] and data['options']==7,data
  report['layouts']['quick_menu']=data
  check('quick-control dropdown stays inside the 352 × 374 popup')
  capture('quick-menu-dark',choose_preset,'quick')
 execute("document.querySelector('[data-choice=presets]').click();"+bounds,result,'quick')
def choose_preset():
 def result(data):
  assert data=={'value':'2','closed':True},data
  writes=[m['args'] for m in messages if m.get('name')=='change_preset'];assert writes==[[2]],writes
  check('pointer choice forwards the numeric earbud preset ID exactly once')
  app.quit()
 execute("document.querySelector('[data-choice-option=\"2\"]').click();({value:document.querySelector('[data-select=presets]').value,closed:!document.querySelector('.choice-popup')})",result,'quick')
app.show('main');app.when_ready('main',lambda:app.later(.2,start));app.later(35,lambda:fail('web control verification timeout'))
try:app.loop.run()
finally:
 app.quit()
 if app.environment:app.environment.close()
 shell.DestroyWindow(app.owner)
 report['result']='FAIL' if report['errors'] else 'PASS'
 (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
