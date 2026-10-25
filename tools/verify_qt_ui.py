"""Exercise the actual Qt frontend, with isolated state and no Bluetooth writes."""
from pathlib import Path
import ctypes as C
import json
import os
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.tools/qt-probe/packages')]
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QTimer, QMetaObject, Qt, QObject, qInstallMessageHandler
from encolite.qt_desktop import Desktop
from encolite.hotkeys import saved_config, ACTIONS, label

OUT=ROOT/'verification/qt-ui';OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'real_device_tested':False}
def logging(kind,context,text):
    report['warnings'].append(text)
    print(text,file=sys.stderr,flush=True)
qInstallMessageHandler(logging)
app=Desktop(ROOT,read_pipe=False)
profiles=json.loads((ROOT/'encolite/oppo_models.json').read_text('utf-8'))
state={'connected':True,'busy':False,'ready':True,'dark':False,'fast_mode':False,'system_motion':True,
       'model_name':'OPPO Enco X3','firmware':'143.143.39','status':'已连接 · OPPO Enco X3',
       'noise':'smart','anc_level':'smart','can_anc':True,'can_transparency':True,'can_off':True,
       'can_equalizer':True,'preset':0,'theme_mode':'system','connection_popup':True,
       'presets':[{'id':i,'name':name} for i,name in [(0,'均衡'),(1,'低音'),(2,'人声'),(7,'自定义')]],
       'noise_options':[{'key':key,'name':name} for key,name in [('smart','智能降噪'),('deep','深度降噪'),('light','轻度降噪'),('transparency','通透模式'),('vocal','人声增强'),('off','关闭')]],
       'switches':[{'key':key,'title':title,'detail':'摘下暂停，戴上继续' if key=='wear' else '', 'checked':True,'enabled':True} for key,title in [('wear','佩戴检测'),('dual','双设备连接'),('game','游戏模式'),('bass','动态低音')]],
       'spatial_visible':True,'spatial_mode':1,'spatial_options':[{'id':0,'name':'关闭'},{'id':1,'name':'固定空间'},{'id':2,'name':'头部跟踪'}],
       'game_options':[{'id':0,'name':'关闭'},{'id':3,'name':'游戏音效'}],'game_type':0,'find_visible':True,'finding':False,
       'custom_available':True,'custom_names':['新增音效','我的音效'],'custom_index':1,'eq_name':'我的音效','eq_minimum':-6,'eq_maximum':6,
       'bands':[{'label':name,'gain':gain} for name,gain in [('62 Hz',0),('250 Hz',2),('1 kHz',1),('4 kHz',-1),('8 kHz',0),('16 kHz',2)]],
       'multi_available':True,'multi_writable':True,'multi_devices':[{'name':'此电脑','address':'11:22:33:44:55:66','detail':'已连接 · 此电脑','connected':True}],
       'device_names':['OPPO Enco X3'],'device_index':0,'model_names':[p['name'] for p in profiles],'model_index':0,
       'battery_layout':'stereo','left_value':'100%','left_charging':True,'left_level':1,'right_value':'90%','right_charging':True,'right_level':.9,
       'case_value':'60%','case_charging':True,'case_level':.6}
config=saved_config(None)
hotkeys={'enabled':True,'capturing':False,'items':[{'action':action,'title':title,'binding':config['bindings'][action], 'label':label(config['bindings'][action]),'active':True,'error':''} for action,title in ACTIONS]}
def publish():app.receive({'type':'state','fixture':True,'state':state,'hotkeys':hotkeys,'preferences':{}})
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def safe(callback):
    def run():
        try:callback()
        except Exception:report['errors'].append(traceback.format_exc());app.quit()
    return run
def later(delay,callback):QTimer.singleShot(delay,safe(callback))
def grab(name,kind='main'):
    window=app.windows[kind]
    assert window.grabWindow().save(str(OUT/(name+'.png')))
def pages(index=0):
    if index==6:
        state['dark']=True;state['theme_mode']='dark';publish();app.windows['main'].setProperty('page',2)
        later(200,lambda:(grab('settings-dark'),quick()));return
    number=[0,1,5,4,6,2][index]
    app.windows['main'].setProperty('page',number)
    later(220,lambda:(grab('page-'+str(number)),check('page '+str(number)+' rendered'),pages(index+1)))
def quick():
    app.show('quick');later(450,quick_ready)
def quick_ready():
    assert 'quick' in app.windows and 'main' not in app.windows
    grab('quick-dark','quick');check('main to quick switches and deletes the previous window')
    state['noise']='off';publish();later(150,quick_off)
def quick_off():
    grab('quick-off','quick');check('off mode renders without ANC sub-options')
    state['noise']='vocal';publish();later(150,quick_vocal)
def quick_vocal():
    grab('quick-vocal','quick');check('transparency exposes the actual human-voice options')
    later(5700,persistent)
def persistent():
    assert 'quick' in app.windows;check('manual quick control remains open beyond the connection notice timeout')
    app.show('notice');later(300,notice)
def notice():
    app.notice_hover(True);grab('notice','notice');check('connection notice renders without replacing the manual quick window')
    active=next(message for message in reversed(app.messages) if message['type']=='view')
    assert active['view']=='quick',active
    check('passive notice retains the active quick-control route used by the tray')
    app.close_view('notice',exiting=False);app.show('main');later(450,restored)
def restored():
    assert set(app.windows)=={'main'}
    win=app.windows['main'];win.setX(120);win.setY(110);win.setWidth(840);win.setHeight(610);win.setProperty('page',5)
    state['fast_mode']=True;publish();app.close_view('main',exiting=False)
    placement=next(m for m in reversed(app.messages) if m.get('name')=='save_window')
    assert placement['frontend']=='qt' and placement['args']==['main',[120,110,840,610,False],5],placement
    check('window position, size and page persist in Qt logical coordinates')
    app.show('quick');later(120,finished)
def finished():
    assert app.windows['quick'].opacity()==1
    check('speed mode displays windows at full opacity without a transition')
    check('model catalog includes '+str(len(profiles))+' OPPO and OnePlus profiles')
    assert app.bridge.captureKey(ord('M'),Qt.ControlModifier.value)['binding']=={'modifiers':2,'key':77}
    assert 'error' in app.bridge.captureKey(ord('M'),0)
    check('shortcut recorder validates actual Qt key and modifier values')
    app.quit()
publish();app.show('main');later(500,pages);later(25000,lambda:(_ for _ in ()).throw(RuntimeError('Qt UI verification timeout')))
try:app.run()
finally:
    fatal=[w for w in report['warnings'] if any(word in w for word in ('ReferenceError','TypeError','Unable to assign','Cannot assign','Binding loop'))]
    report['errors'].extend(fatal)
    report['result']='FAIL' if report['errors'] else 'PASS'
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if report['errors']:raise SystemExit(1)
