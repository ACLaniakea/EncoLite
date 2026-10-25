"""Render and inspect the actual EQ page without opening a Bluetooth session."""
from pathlib import Path
import ctypes as C,json,os,sys,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['ENCOLITE_DATA_DIR']=str(ROOT/'.install-test/eq-visual')
from encolite.web_desktop import Desktop
from encolite.webview_native import Handler,call,checked,HRESULT
from encolite import windows_shell as shell
shell.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
folder=ROOT/'verification/eq-vertical';folder.mkdir(parents=True,exist_ok=True)
app=Desktop(ROOT);messages=[];report={'checks':[],'errors':[],'layouts':{}}
app.send=lambda kind,**values:messages.append({'type':kind,**values})
app.payload={'type':'state','fixture':True,'preferences':{'web_main':{'page':5}},'state':{
    'model_name':'OPPO Enco X3','connected':True,'custom_available':True,'custom_names':['新增音效'],
    'custom_index':0,'eq_name':'我的音效','eq_minimum':-6,'eq_maximum':6,
    'bands':[{'label':label,'gain':gain} for label,gain in zip(
        ['62 Hz','250 Hz','1 kHz','4 kHz','8 kHz','16 kHz'],[-6,-3,0,2,4,6])],
    'status':'已连接 · OPPO Enco X3','dark':False}}
def failed(error):report['errors'].append(str(error));app.quit()
def execute(script,callback):
    def completed(status,result):
        try:checked(status);callback(json.loads(result))
        except Exception:failed(traceback.format_exc())
    handler=Handler('49511172-CC67-4BCA-9923-137112F4C4CC',completed,(HRESULT,W.LPCWSTR))
    window=app.windows['main'];window.browser.handlers.append(handler)
    checked(call(window.browser.core,29,script,handler.pointer,types=(W.LPCWSTR,C.c_void_p)))
layout='''(()=>{
 const sliders=[...document.querySelectorAll('[data-gain]')], panel=document.querySelector('.eq-console');
 const style=getComputedStyle(sliders[0]), box=panel.getBoundingClientRect(), page=document.querySelector('.page');
 return {sliders:sliders.length,writingMode:style.writingMode,direction:style.direction,
   horizontalOverflow:page.scrollWidth>page.clientWidth,verticalOverflow:page.scrollHeight>page.clientHeight,
   zeroLine:!!document.querySelector('.eq-grid .zero'),ticks:[...document.querySelectorAll('.eq-axis span')].map(x=>x.textContent),
   readouts:[...document.querySelectorAll('[data-gain-value]')].map(x=>x.textContent),
   width:box.width,viewport:innerWidth,viewportHeight:innerHeight,panelHeight:box.height,pageHeight:page.clientHeight,scrollHeight:page.scrollHeight,sliderHeight:sliders[0].getBoundingClientRect().height,
   xs:sliders.map(x=>x.getBoundingClientRect().x)};
})()'''
def inspect(name,next_step):
    def result(data):
        report['layouts'][name]=data
        assert data['sliders']==6 and data['writingMode']=='vertical-lr' and data['direction']=='rtl',data
        assert data['zeroLine'] and not data['horizontalOverflow'],data
        assert len(set(data['xs']))==6 and data['sliderHeight']>=160,data
        if name=='light':assert not data['verticalOverflow'],data
        report['checks'].append(name+' vertical layout and grid')
        app.windows['main'].browser.capture(folder/(name+'.png'),lambda:app.later(.1,next_step))
    execute(layout,result)
def start():app.later(.2,lambda:inspect('light',dark))
def dark():
    app.payload['state']['dark']=True;app.windows['main'].publish()
    app.later(.15,lambda:inspect('dark',narrow))
def narrow():
    window=app.windows['main'];scale=(shell.GetDpiForWindow(window.hwnd) or 96)/96
    shell.SetWindowPos(window.hwnd,None,0,0,round(740*scale),round(560*scale),0x16)
    app.later(.15,lambda:inspect('compact',interaction))
def interaction():
    script='''(()=>{
      const input=document.querySelector('[data-gain="2"]');
      input.value=3;input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      const adjusted=document.querySelector('[data-gain-value="2"]').textContent;
      input.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
      return {adjusted,reset:input.value,readout:document.querySelector('[data-gain-value="2"]').textContent};
    })()'''
    def result(data):
        assert data=={'adjusted':'+3','reset':'0','readout':'0'},data
        writes=[m['args'] for m in messages if m.get('name')=='edit_gain']
        assert writes==[[2,3],[2,0]],writes
        report['checks'].append('gain editing and double-click reset use existing edit_gain actions')
        app.payload['state'].update(eq_minimum=-12,eq_maximum=12)
        app.windows['main'].publish()
        app.later(.15,limits)
    execute(script,result)
def limits():
    def result(data):
        assert '-12' in data['ticks'] and '+12' in data['ticks'],data
        report['checks'].append('grid follows selected EQ gain limits')
        app.quit()
    execute(layout,result)
app.show('main');app.when_ready('main',start);app.later(25,lambda:failed('EQ preview timeout'))
try:app.loop.run()
finally:
    app.quit()
    if app.environment:app.environment.close()
    shell.DestroyWindow(app.owner)
    report['result']='FAIL' if report['errors'] else 'PASS'
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report),flush=True)
    if report['errors']:raise SystemExit(1)
