"""Drive Qt's own controls and events; no Bluetooth or other app automation."""
from pathlib import Path
import json,sys,traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.tools/qt-probe/packages')]
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QObject,QTimer,QMetaObject,Q_ARG,Qt,qInstallMessageHandler
from PySide6.QtTest import QTest
from encolite.qt_desktop import Desktop,plain
from encolite.hotkeys import ACTIONS,saved_config,label
OUT=ROOT/'verification/qt-controls';OUT.mkdir(exist_ok=True,parents=True)
report={'checks':[],'errors':[],'warnings':[]}
def logging(kind,ctx,text):report['warnings'].append(text);print(text,file=sys.stderr,flush=True)
qInstallMessageHandler(logging)
app=Desktop(ROOT,read_pipe=False)
state={'connected':True,'busy':False,'model_name':'OnePlus Buds Pro 3','noise':'smart','anc_level':'deep','can_anc':True,'can_off':True,'can_transparency':True,'can_equalizer':True,
 'noise_options':[{'key':k,'name':n} for k,n in [('smart','智能降噪'),('deep','深度降噪'),('off','关闭'),('transparency','通透'),('vocal','人声增强')]],
 'presets':[{'id':0,'name':'均衡'},{'id':7,'name':'自定义'}],'preset':0,'switches':[{'key':'wear','title':'佩戴检测','detail':'摘下暂停，戴上继续','enabled':True,'checked':False}],
 'spatial_visible':True,'spatial_options':[{'id':0,'name':'关闭'},{'id':2,'name':'头部跟踪'}],'spatial_mode':0,'game_options':[{'id':0,'name':'关闭'},{'id':3,'name':'游戏音效'}],'game_type':0,
 'find_visible':True,'finding':False,'custom_available':True,'custom_names':['新增音效','我的音效'],'custom_index':1,'eq_name':'我的音效','eq_minimum':-6,'eq_maximum':6,
 'bands':[{'label':f'{f} Hz','gain':0} for f in [62,250,1000,4000,8000,16000]],
 'multi_available':True,'multi_writable':True,'multi_devices':[{'name':'电脑','detail':'已连接','address':'11:22:33:44:55:66','connected':True}],
 'device_names':['OnePlus Buds Pro 3'],'device_index':0,'model_names':['OnePlus Buds Pro 3']+[f'耳机 {i}' for i in range(40)],'model_index':0,
 'dark':False,'system_motion':True,'fast_mode':True,'theme_mode':'light','connection_popup':True}
config=saved_config(None)
hotkeys={'enabled':True,'capturing':False,'items':[{'action':a,'title':t,'binding':config['bindings'][a],'label':label(config['bindings'][a]),'error':''} for a,t in ACTIONS]}
def publish():app.receive({'type':'state','fixture':True,'state':state,'preferences':{},'hotkeys':hotkeys})
def safe(fn):
 def run():
  try:fn()
  except Exception:report['errors'].append(traceback.format_exc());app.quit()
 return run
def later(ms,fn):QTimer.singleShot(ms,safe(fn))
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def objects():
 rows=[];pending=[app.windows['main'],app.windows['main'].contentItem()];seen=set()
 while pending:
  item=pending.pop()
  if id(item) in seen:continue
  seen.add(id(item));rows.append(item);pending.extend(item.children())
  if hasattr(item,'childItems'):pending.extend(item.childItems())
  for prop in ('contentItem','background'):
   child=item.property(prop)
   if isinstance(child,QObject):pending.append(child)
 return rows
def find(prop,value,extra=None):
 rows=[o for o in objects() if o.property(prop)==value and (extra is None or o.property(extra) is not None)]
 assert rows,(prop,value)
 return rows[0]
def invoke(obj,name,*args):
 assert QMetaObject.invokeMethod(obj,name,Qt.DirectConnection,*args),(obj,name)
def click(text):invoke(find('text',text,'primary'),'clicked')
def action(name):return next(m for m in reversed(app.messages) if m.get('name')==name)
def page(number,fn):app.windows['main'].setProperty('page',number);later(120,fn)
def main():
 click('断开控制连接');assert action('change_connection')['args']==[];check('connection button uses the existing controller action')
 page(1,sounds)
def sounds():
 select=find('accessibleName','耳机音效')
 invoke(select,'chosen',Q_ARG('QVariant',7))
 assert action('change_preset')['args']==[7] and type(action('change_preset')['args'][0]) is int
 check('sound selector forwards the protocol preset ID as an integer')
 invoke(select,'openMenu');later(80,menu)
def menu():
 QTest.keyClick(app.windows['main'],Qt.Key_Down);QTest.keyClick(app.windows['main'],Qt.Key_Return)
 assert action('change_preset')['args']==[7]
 check('themed option popup supports keyboard selection')
 spatial=find('accessibleName','空间音频')
 invoke(spatial,'chosen',Q_ARG('QVariant',2));assert action('change_spatial')['args']==[2]
 check('spatial controls forward the real option ID')
 page(4,features)
def features():
 switch=next(o for o in objects() if 'UiSwitch' in o.metaObject().className())
 invoke(switch,'clicked');assert action('change_feature')['args']==['wear',True]
 check('feature switch forwards a boolean and retains its pending state')
 click('播放提示音');assert not any(m.get('name')=='find_device' for m in app.messages)
 click('确认');assert action('find_device')['args']==[True]
 check('find-earbuds confirmation gates the sound command')
 page(5,eq)
def eq():
 primary=find('text','保存并使用','primary')
 report['primary_button_color']=primary.property('contentItem').property('color').name()
 assert report['primary_button_color']=='#ffffff',report['primary_button_color']
 report['primary_details']={'primary':primary.property('primary'),'content':primary.property('contentItem').metaObject().className()}
 slider=next(o for o in objects() if 'Slider' in o.metaObject().className() and o.property('from')==-6)
 slider.setProperty('value',3);invoke(slider,'moved');assert action('edit_gain')['args'][1]==3
 field=find('placeholderText','音效名称');field.setProperty('text','测试音效');click('保存并使用')
 assert action('edit_custom_name')['args']==['测试音效'] and action('write_custom')['args']==['save']
 check('vertical EQ gain, Unicode name and save reach the controller')
 old=slider;state['bands'][0]['gain']=3;publish()
 assert old in objects();check('band updates retain the slider being edited')
 page(6,devices)
def devices():
 click('优先连接');assert action('operate_multi')['args']==['priority','11:22:33:44:55:66']
 click('取消配对');click('确认');assert action('operate_multi')['args']==['unpair','11:22:33:44:55:66']
 check('multi-device actions retain addresses and require unpair confirmation')
 click('手动选择型号')
 later(100,settings)
def settings():
 model=next(o for o in objects() if o.property('searchable') is True and plain(o.property('choices')) and len(plain(o.property('choices')))>30)
 invoke(model,'openMenu');later(100,search)
def search():
 field=find('placeholderText','搜索');field.setProperty('text','OnePlus')
 QTest.keyClick(app.windows['main'],Qt.Key_Return)
 assert action('select_model')['args']==[0];check('long model menu searches and selects the original model index')
 page(2,shortcut)
def shortcut():
 item=hotkeys['items'][0]
 invoke(app.windows['main'],'editHotkey',Q_ARG('QVariant',item))
 hotkeys['capturing']=True;publish();later(100,record)
def record():
 QTest.keyClick(app.windows['main'],Qt.Key_M,Qt.ControlModifier)
 click('保存')
 result=action('set_hotkey');assert result['args'][1]=={'modifiers':2,'key':77},result
 check('Qt key events record and save a validated shortcut object')
 hotkeys['result']={'request':result['args'][2],'ok':True};publish();later(100,finish)
def finish():
 assert action('end_hotkey_capture')['args']==[];check('shortcut save acknowledgement releases the capture lease')
 app.quit()
publish();app.show('main');later(300,main);later(15000,lambda:(_ for _ in ()).throw(RuntimeError('control test timeout')))
try:app.run()
finally:
 report['errors'].extend(w for w in report['warnings'] if any(x in w for x in ['TypeError','ReferenceError','Unable to assign','Binding loop']))
 report['result']='FAIL' if report['errors'] else 'PASS'
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
 if report['errors']:raise SystemExit(1)
