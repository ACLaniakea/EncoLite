"""Qt mouse press/release regressions for menus and the consolidated navigation."""
from pathlib import Path
import json,os,sys,time,traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.tools/qt-probe/packages')]
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QObject,QPointF,QTimer,Qt,qInstallMessageHandler
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from shiboken6 import isValid
from encolite.qt_desktop import Desktop,plain
GUI_ROOT=Path(os.environ.get('ENCOLITE_UI_TEST_ROOT',ROOT))
OUT=Path(os.environ.get('ENCOLITE_UI_TEST_OUT',ROOT/'verification/qt-navigation'));OUT.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'warnings':[],'ui_root':str(GUI_ROOT),'input':'Qt QTest mouse press/release and keyboard events directed only to this test window','real_hardware':False}
qInstallMessageHandler(lambda kind,context,text:report['warnings'].append(text))
app=Desktop(GUI_ROOT,read_pipe=False)
profiles=json.loads((ROOT/'encolite/oppo_models.json').read_text('utf-8'))
state={'connected':True,'busy':False,'model_name':'OPPO Enco X3','firmware':'143.143.39',
 'noise':'smart','anc_level':'smart','noise_options':[{'key':k,'name':n} for k,n in [('smart','智能降噪'),('deep','深度降噪'),('transparency','通透'),('vocal','人声通透'),('off','关闭')]],
 'can_anc':True,'can_transparency':True,'can_off':True,'can_equalizer':True,'presets':[{'id':0,'name':'均衡'},{'id':2,'name':'低音'},{'id':7,'name':'自定义'}],'preset':0,
 'switches':[{'key':'wear','title':'佩戴检测','checked':True,'enabled':True,'detail':''}],
 'custom_available':True,'custom_names':['新增音效','我的音效'],'custom_index':0,'bands':[{'label':name,'gain':0} for name in ['62 Hz','250 Hz','1 kHz','4 kHz','8 kHz','16 kHz']],
 'eq_minimum':-6,'eq_maximum':6,'device_names':['OPPO Enco X3'],'device_index':0,'model_names':[p['name'] for p in profiles],'model_index':0,
 'fast_mode':True,'system_motion':True,'dark':False,'theme_mode':'system','left_value':'90%','right_value':'90%','case_value':'—'}
def publish():app.receive({'type':'state','state':state,'preferences':{},'hotkeys':{'items':[]}})
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def safe(fn):
 def run():
  try:fn()
  except Exception:report['errors'].append(traceback.format_exc());app.quit()
 return run
def later(ms,fn):QTimer.singleShot(ms,safe(fn))
def until(predicate,fn,label,timeout=3000):
 deadline=time.monotonic()+timeout/1000
 def poll():
  if predicate():fn()
  elif time.monotonic()>deadline:raise TimeoutError(label)
  else:later(15,poll)
 later(0,poll)
def objects():
 win=app.windows['main'];pending=[win,win.contentItem()];seen=set();rows=[]
 while pending:
  item=pending.pop()
  if id(item) in seen or not isValid(item):continue
  seen.add(id(item));rows.append(item);pending.extend(item.children())
  if isinstance(item,QQuickItem):pending.extend(item.childItems())
  for key in ('contentItem','background'):
   child=item.property(key)
   if isinstance(child,QObject):pending.append(child)
 return rows
def select(name):return next(o for o in objects() if o.property('accessibleName')==name and o.property('popupVisible') is not None and o.property('visible'))
def button(text):return next(o for o in objects() if o.property('text')==text and o.property('primary') is not None and o.property('visible'))
def nav(index):return next(o for o in objects() if isinstance(plain(o.property('modelData')),dict) and plain(o.property('modelData')).get('id')==index and o.property('selected') is not None)
def point(item):return item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint()
def click(item):
 p=point(item)
 report.setdefault('clicks',[]).append({'class':item.metaObject().className(),'text':item.property('text'),'name':item.property('accessibleName'),'x':p.x(),'y':p.y(),'width':item.width(),'height':item.height()})
 QTest.mouseClick(app.windows['main'],Qt.LeftButton,Qt.NoModifier,p)
def open_count():return sum(bool(o.property('popupVisible')) for o in objects() if o.property('popupVisible') is not None)
def chosen():return [m for m in app.messages if m.get('type')=='action' and m.get('name') in ('change_noise','change_preset','select_model')]
def start():
 app.windows['main'].setProperty('page',1);later(100,start_menu)
def start_menu():
 noise=next(o for o in objects() if o.property('visible') and o.metaObject().className().startswith('NoiseControl_'))
 assert 45<=noise.height()<=60,noise.height()
 check('listening buttons retain a compact height instead of stretching with the page')
 click(select('耳机音效'));later(80,pressed)
def pressed():
 item=select('耳机音效')
 app.windows['main'].grabWindow().save(str(OUT/'initial-menu.png'))
 assert item.property('popupVisible')
 win=app.windows['main'];pos=point(item);QTest.mousePress(win,Qt.LeftButton,Qt.NoModifier,pos)
 try:assert item.property('popupVisible'),'PressOutside closed the list before its trigger received the release'
 finally:QTest.mouseRelease(win,Qt.LeftButton,Qt.NoModifier,pos)
 later(80,toggled)
def toggled():
 assert not select('耳机音效').property('popupVisible') and not chosen()
 check('a second real mouse click closes the same menu without selecting or reopening')
 toggle_cycle(0)
def toggle_cycle(index):
 if index==8:return other_menu()
 item=select('耳机音效');click(item)
 def done():
  assert bool(item.property('popupVisible'))==(index%2==0)
  assert not chosen();toggle_cycle(index+1)
 later(35,done)
def other_menu():
 check('eight successive trigger clicks reliably alternate open and closed')
 click(select('耳机音效'));click(select('降噪强度'));later(80,same_page)
def same_page():
 assert select('降噪强度').property('popupVisible') and not select('耳机音效').property('popupVisible') and open_count()==1
 check('opening another list closes the previous list with one click')
 global retained
 retained=select('降噪强度');click(nav(1));later(80,same_done)
def same_done():
 assert app.windows['main'].property('page')==1 and isValid(retained) and not retained.property('popupVisible')
 check('clicking the current sidebar entry closes menus without rebuilding its page')
 click(select('耳机音效'));click(button('均衡器'));later(100,changed_page)
def changed_page():
 assert app.windows['main'].property('page')==5 and not open_count()
 check('switching sidebar pages dismisses the old page menu')
 assert [r['id'] for r in plain(app.windows['main'].property('pages'))]==[0,1,4,6,2]
 assert app.windows['main'].property('sectionPage')==1 and nav(1).property('selected')
 check('five sidebar sections place EQ inside sound without a duplicate sidebar entry')
 click(nav(1));assert app.windows['main'].property('page')==5
 check('clicking the selected sound section retains its current EQ subpage')
 click(button('聆听与音效'));later(100,pick_option)
def pick_option():
 click(select('耳机音效'));later(80,pick_mouse)
def pick_mouse():
 click(button('低音'));later(80,picked)
def picked():
 messages=chosen();assert len(messages)==1 and messages[0]['name']=='change_preset' and messages[0]['args']==[2],messages
 assert type(messages[0]['args'][0]) is int and not open_count()
 check('a mouse-selected option closes the menu and sends its integer ID exactly once')
 click(select('耳机音效'));state['left_value']='89%';publish();later(80,battery_update)
def battery_update():
 assert select('耳机音效').property('popupVisible')
 check('an unrelated battery update leaves the open list intact')
 state['busy']=True;publish();later(80,disabled)
def disabled():
 global hidden_selector
 assert not open_count();check('busy state closes a menu whose control becomes disabled')
 state['busy']=False;publish();hidden_selector=select('降噪强度');click(hidden_selector);state['noise']='off';publish();later(80,hidden_detail)
def hidden_detail():
 assert not open_count() and not hidden_selector.property('visible')
 check('turning listening mode off hides and closes its obsolete strength list')
 state['noise']='vocal';publish();later(80,transparency)
def transparency():
 item=select('通透模式');assert item.property('visible')
 assert [r['value'] for r in plain(item.property('choices'))]==['transparency','vocal']
 check('transparency replaces ANC choices with only its own supported submodes')
 click(nav(6));later(100,manual)
def manual():
 click(button('手动选择型号'));later(80,manual_open)
def manual_open():
 click(select('耳机型号'));later(80,manual_collapse)
def manual_collapse():
 global model_selector
 model_selector=select('耳机型号');assert model_selector.property('popupVisible')
 click(button('收起型号选择'));later(80,manual_done)
def manual_done():
 assert not open_count() and not model_selector.property('visible')
 check('collapsing manual model selection also dismisses its open dropdown')
 app.windows['main'].setProperty('page',3);later(100,legacy_about)
def legacy_about():
 assert app.windows['main'].property('page')==2
 assert any(o.property('text')=='协议来源' for o in objects())
 check('the former About route now opens settings with the retained license and source information')
 app.windows['main'].setProperty('page',4);later(100,finish)
def finish():
 assert app.windows['main'].property('page')==4
 assert any(o.property('text')=='佩戴检测' for o in objects())
 check('earbud feature controls retain an independent sidebar page')
 click(nav(0));later(100,capture)
def capture():
 assert not any(o.property('visible') and o.metaObject().className().startswith(('NoiseControl_','UiSelect_','UiSwitch_')) for o in objects())
 check('overview shows device state without duplicating sound selectors or feature switches')
 app.windows['main'].grabWindow().save(str(OUT/'earbuds.png'));app.quit()
publish();app.show('main');until(lambda:'main' in app.ready and app.windows['main'].opacity()==1,start,'initial Qt frame')
later(20000,lambda:(_ for _ in ()).throw(TimeoutError('navigation test timeout')))
try:app.run()
finally:
 report['errors'].extend(w for w in report['warnings'] if any(key in w for key in ('ReferenceError','TypeError','Binding loop','Unable to assign','Cannot assign')))
 report['result']='FAIL' if report['errors'] else 'PASS'
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps(report,ensure_ascii=True),flush=True)
 if report['errors']:raise SystemExit(1)
