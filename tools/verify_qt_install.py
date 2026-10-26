"""Install a distinct validation product; never upgrade the user's installed app."""
from pathlib import Path
import ctypes as C,json,os,shutil,subprocess,sys,time,uuid,winreg
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
sys.stdout.reconfigure(encoding='utf-8')
from encolite import windows_shell as shell
from build_msi import MSI_VERSION
from encolite.autostart import WindowsStartup
assert not shell.FindWindow('EncoLiteTray','Enco Lite tray'),'Exit the active client before isolated installation verification'
OUT=ROOT/'verification/qt-install';OUT.mkdir(exist_ok=True,parents=True)
TARGET=ROOT/'.install-test/Enco Lite Qt Validation';DATA=ROOT/'.install-test/qt-installed-data'
UPGRADE='{6144F9B9-7D81-46AB-882E-15A4E85E5DE8}';VERSION='0.5.0-qt-validation';NAME='Enco Lite Qt Validation'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
COMPONENT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),'python\\pythonw.exe')).upper()+'}'
api=C.WinDLL('msi');api.MsiGetComponentPathW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)]
api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
EXE=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
MSI=ROOT/'.tools/qt-probe/validation.msi'
GROUP=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs'/NAME
report={'checks':[],'errors':[],'isolated_upgrade_code':UPGRADE,'security_changes':False}
startup=WindowsStartup(TARGET)
def startup_value():return startup.path.read_bytes() if startup.path.exists() else None
original_startup=startup_value()
def restore_startup():
 if original_startup is not None:
  startup.path.parent.mkdir(parents=True,exist_ok=True);startup.path.write_bytes(original_startup)
 else:startup.path.unlink(missing_ok=True)
 assert startup_value()==original_startup
def check(name):report['checks'].append(name);print('PASS',name,flush=True)
def location():
 text=C.create_unicode_buffer(32768);size=C.c_uint32(len(text))
 status=api.MsiGetComponentPathW(PRODUCT,COMPONENT,text,C.byref(size))
 return Path(text.value).parent.parent if status in (3,4) and text.value else None
def uninstall():
 actual=location()
 if actual is None:return
 assert actual.resolve()==TARGET.resolve(),'Unexpected validation installation path'
 p=subprocess.run([str(EXE),'/x',PRODUCT,'/qn','/norestart','/L*v',str(OUT/'uninstall.log')],timeout=120)
 assert p.returncode in (0,3010),p.returncode
def install(stage):
 # Windows Installer expects quotes around a property's value, rather than
 # the entire NAME=value argument produced by subprocess.list2cmdline.
 p=subprocess.run(f'"{EXE}" /i "{MSI}" /qn /norestart INSTALLDIR="{TARGET}" CREATE_DESKTOP_SHORTCUT=0 REINSTALLMODE=amus /L*v "{OUT/(stage+".log")}"',timeout=120)
 assert p.returncode in (0,3010),p.returncode
 assert location() and location().resolve()==TARGET.resolve(),str(location())
def ui(stage):
 subprocess.run([sys.executable,str(ROOT/'tools/verify_qt_bundle.py'),str(TARGET)],check=True,timeout=45)
 shutil.copy2(ROOT/'verification/qt-bundle/report.json',OUT/(stage+'-ui.json'))
 check(stage+': installed Qt renders all six pages and both popup types')
def entry(stage):
 output=OUT/(stage+'-backend.json')
 env={**os.environ,'ENCOLITE_DATA_DIR':str(DATA)}
 args=[str(TARGET/'python/pythonw.exe'),str(TARGET/'desktop_entry.py')]
 process=subprocess.Popen([*args,'--fixture','--tray-only','--test-timeout','20','--test-report',str(output)],env=env,cwd=TARGET)
 try:
  for _ in range(60):
   if shell.FindWindow('EncoLiteTray','Enco Lite tray'):break
   assert process.poll() is None;time.sleep(.1)
  else:raise RuntimeError('installed tray did not appear')
  subprocess.run([*args,'--fixture','--quick'],env=env,check=True,timeout=10)
  quick=None
  for _ in range(100):
   quick=shell.FindWindow(None,'Enco Lite · 快捷控制')
   if quick and shell.IsWindowVisible(quick):break
   assert process.poll() is None;time.sleep(.1)
  else:raise RuntimeError('second launch did not open Qt quick control')
  assert shell.IsWindowVisible(quick)
  subprocess.run([*args,'--quit'],env=env,check=True,timeout=10)
  assert process.wait(timeout=12)==0
  result=json.loads(output.read_text('utf-8'))
  assert result['gui_starts']==1 and not result['errors'] and not result['slint_loaded'],result
  saved=json.loads((DATA/'preferences.json').read_text('utf-8'))
  assert saved.get('qt_quick',{}).get('bounds'),saved
  check(stage+': pythonw IPC opens one Qt process and saves placement during tray exit')
 finally:
  if process.poll() is None:
   subprocess.run([*args,'--quit'],env=env,timeout=10);process.wait(timeout=15)
def startup_entry():
 from encolite import shell_link
 output=OUT/'startup-backend.json';output.unlink(missing_ok=True)
 env_dir=os.environ.get('ENCOLITE_DATA_DIR');os.environ['ENCOLITE_DATA_DIR']=str(DATA)
 link=OUT/'启动验证.lnk'
 arguments=subprocess.list2cmdline([str(TARGET/'desktop_entry.py'),'--tray-only','--fixture','--fixture-data',str(DATA),'--test-timeout','2','--test-report',str(output)])
 shell_link.write(link,startup.host(),arguments,TARGET)
 try:
  os.startfile(str(link))
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   if output.exists():
    try:result=json.loads(output.read_text('utf-8'));break
    except ValueError:pass
   time.sleep(.1)
  else:raise TimeoutError('startup shortcut did not finish')
  assert result['gui_starts']==0 and not result['qt_loaded'] and not result['slint_loaded'] and not result['errors'],result
  check('Windows Shell executes the installed startup shortcut with only the native tray loaded')
 finally:
  link.unlink(missing_ok=True)
  if shell.FindWindow('EncoLiteTray','Enco Lite tray'):
   subprocess.run([str(TARGET/'python/pythonw.exe'),str(TARGET/'desktop_entry.py'),'--quit'],env={**os.environ,'ENCOLITE_DATA_DIR':str(DATA)},timeout=10)
  if env_dir is None:os.environ.pop('ENCOLITE_DATA_DIR',None)
  else:os.environ['ENCOLITE_DATA_DIR']=env_dir

try:
 product=C.create_unicode_buffer(39);status=api.MsiEnumRelatedProductsW(UPGRADE,0,0,product)
 assert status==259 or product.value==PRODUCT and location() and location().resolve()==TARGET.resolve()
 uninstall();assert not GROUP.exists() or not any(GROUP.iterdir())
 subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py'),'--bundle',str(ROOT/'dist/EncoLite-qt'),'--output',str(MSI),'--version',VERSION,'--msi-version',MSI_VERSION,'--upgrade-code',UPGRADE,'--name',NAME],check=True,timeout=120)
 install('install');assert (GROUP/(NAME+'.lnk')).exists() and (GROUP/'快捷控制.lnk').exists()
 assert startup_value()==original_startup
 check('isolated MSI installs the bundled Qt runtime and both shortcuts')
 arp_key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\EncoLite.'+UPGRADE.strip('{}')
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,arp_key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
  command=winreg.QueryValueEx(key,'UninstallString')[0];assert '/qf' in command and PRODUCT in command and '/norestart' in command,command
  assert winreg.QueryValueEx(key,'DisplayName')[0]==NAME
 check('Windows app-list uninstall entry explicitly opens the full Chinese wizard')
 startup.set_enabled(True);startup_entry();registered=startup_value()
 ui('first');entry('first');saved=(DATA/'preferences.json').read_bytes()
 install('reinstall');assert (DATA/'preferences.json').read_bytes()==saved
 assert startup_value()==registered
 check('same-version reinstall preserves an enabled startup registration')
 ui('reinstalled');check('same-version reinstall preserves preferences')
 uninstall();assert location() is None and not (TARGET/'python/pythonw.exe').exists()
 assert (DATA/'preferences.json').read_bytes()==saved and not GROUP.exists()
 assert startup_value() is None
 check('uninstall removes the startup command belonging to this installation')
 check('MSI uninstall removes app and test shortcuts while retaining preferences')
 try:winreg.OpenKey(winreg.HKEY_CURRENT_USER,arp_key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY)
 except FileNotFoundError:pass
 else:raise AssertionError('The app-list uninstall entry was left behind')
 check('uninstall removes its own app-list registration without leaving a duplicate entry')
 install('foreign-registration')
 foreign=WindowsStartup(ROOT);foreign.set_enabled(True);foreign_value=startup_value()
 uninstall();assert startup_value()==foreign_value
 check('uninstall preserves a startup command belonging to another portable copy')
except Exception:report['errors'].append(__import__('traceback').format_exc())
finally:
 try:uninstall()
 except Exception:report['errors'].append('cleanup: '+__import__('traceback').format_exc())
 try:restore_startup();report['original_startup_restored']=True
 except Exception:report['errors'].append('startup cleanup: '+__import__('traceback').format_exc())
 report['result']='FAIL' if report['errors'] else 'PASS'
 (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
