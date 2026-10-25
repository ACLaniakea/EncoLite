"""Verify the packaged frontend without development Qt paths or real devices."""
from pathlib import Path
import json,os,queue,subprocess,sys,threading,time
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'dist/EncoLite-qt'
OUT=ROOT/'verification/qt-bundle';OUT.mkdir(exist_ok=True,parents=True)
sys.stdout.reconfigure(encoding='utf-8')
messages=queue.Queue();report={'bundle':str(BUNDLE),'errors':[]}
env={**os.environ,'ENCOLITE_DIAGNOSTICS':'1','ENCOLITE_DATA_DIR':str(ROOT/'.install-test/qt-bundle-data'),'ENCOLITE_CAPTURE_DIR':str(OUT)}
env.pop('PYTHONPATH',None);env.pop('QML_IMPORT_PATH',None);env.pop('QML2_IMPORT_PATH',None);env.pop('QT_PLUGIN_PATH',None)
log=(OUT/'stderr.log').open('wb')
process=subprocess.Popen([str(BUNDLE/'python/python.exe'),str(BUNDLE/'qt_entry.py')],cwd=BUNDLE,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8')
def read():
 for line in process.stdout:
  try:messages.put(json.loads(line))
  except ValueError:pass
threading.Thread(target=read,daemon=True).start()
def send(value):process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
try:
 send({'type':'state','fixture':True,'state':{'connected':False,'model_name':'未连接耳机','status':'等待连接','noise_options':[],'dark':False,'fast_mode':False,'system_motion':True},'preferences':{}})
 send({'type':'inspect','id':'packaged-qt'})
 deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  if process.poll() is not None:raise RuntimeError('Packaged Qt exited: '+str(process.returncode))
  try:message=messages.get(timeout=.25)
  except queue.Empty:continue
  if message.get('type')=='diagnostic':
   report['ui']=message['data'];assert report['ui']['result']=='PASS' and report['ui']['pages']==6,report['ui'];break
 else:raise TimeoutError('packaged Qt rendering timeout')
 send({'type':'show','view':'quick'});time.sleep(.7)
 send({'type':'show','view':'notice'});time.sleep(.5)
 send({'type':'quit'});process.wait(timeout=8);assert process.returncode==0
 report['result']='PASS'
except Exception as error:
 report['errors'].append(str(error));report['result']='FAIL'
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=8)
 log.close();report['stderr']=(OUT/'stderr.log').read_text('utf-8',errors='replace')
 if any(x in report['stderr'] for x in ('TypeError','ReferenceError','is not installed','not found','DLL load failed')):report['result']='FAIL'
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps(report,ensure_ascii=False),flush=True)
 if report['result']!='PASS':raise SystemExit(1)
