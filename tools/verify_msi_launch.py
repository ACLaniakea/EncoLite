"""Exercise the Finish button's MSI actions with an isolated fixture command.

The MSI copy adds test flags only to the launch action. Installed files and the
published MSI are never changed, and the action runs a tray-only test process.
"""
from pathlib import Path
import ctypes as C,json,shutil,sys,time,warnings
warnings.filterwarnings('ignore',category=DeprecationWarning)
import msilib as m
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from build_msi import VERSION
from encolite import windows_shell as shell
sys.stdout.reconfigure(encoding='utf-8')
assert not shell.FindWindow('EncoLiteTray','Enco Lite tray'),'Exit the active client before launch verification'
OUT=ROOT/'verification/qt-msi-launch';OUT.mkdir(parents=True,exist_ok=True)
STAGE=ROOT/'.install-test/msi-finish';STAGE.mkdir(parents=True,exist_ok=True)
package=STAGE/'launch.msi';output=OUT/'backend.json';output.unlink(missing_ok=True)
shutil.copy2(ROOT/'release'/f'EncoLite-{VERSION}-win-x64.msi',package)
fixture=' --fixture --fixture-data "'+str(STAGE/'data')+'" --tray-only --test-timeout 2 --test-report "'+str(output)+'"'
db=m.OpenDatabase(str(package),m.MSIDBOPEN_TRANSACT)
view=db.OpenView("SELECT `Target` FROM `CustomAction` WHERE `Action`='LaunchApplication'");view.Execute(None);command=view.Fetch().GetString(1);view.Close()
view=db.OpenView("UPDATE `CustomAction` SET `Target`=? WHERE `Action`='LaunchApplication'");record=m.CreateRecord(1);record.SetString(1,command+fixture);view.Execute(record);view.Close();db.Commit();del view,record,db
api=C.WinDLL('msi')
for name,types in {
 'MsiOpenPackageExW':[C.c_wchar_p,C.c_uint32,C.POINTER(C.c_uint32)],
 'MsiDoActionW':[C.c_uint32,C.c_wchar_p],
 'MsiSetTargetPathW':[C.c_uint32,C.c_wchar_p,C.c_wchar_p],
 'MsiGetPropertyW':[C.c_uint32,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)],
 'MsiCloseHandle':[C.c_uint32],
}.items():getattr(api,name).argtypes=types
previous=api.MsiSetInternalUI(2,None);handle=C.c_uint32();report={'checks':[],'errors':[],'scope':'MSI Finish actions, with fixture flags appended only to a temporary MSI copy; no real-device writes'}
try:
 status=api.MsiOpenPackageExW(str(package),0,C.byref(handle));assert status==0,('open launch test package',status)
 for name in ('CostInitialize','FileCost','CostFinalize'):assert api.MsiDoActionW(handle,name)==0,name
 bundle=ROOT/'dist/EncoLite-qt'
 assert api.MsiSetTargetPathW(handle,'INSTALLDIR',str(bundle)+'\\')==0
 assert api.MsiDoActionW(handle,'SetLauncher')==0
 value=C.create_unicode_buffer(32768);length=C.c_uint32(len(value))
 assert api.MsiGetPropertyW(handle,'INSTALLER_PYTHON',value,C.byref(length))==0
 assert Path(value.value).resolve()==(bundle/'python/pythonw.exe').resolve(),value.value
 report['checks'].append('Finish resolves the bundled official pythonw executable in the MSI installation directory')
 status=api.MsiDoActionW(handle,'LaunchApplication');assert status==0,('LaunchApplication',status)
 deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  if output.exists():
   try:result=json.loads(output.read_text('utf-8'));break
   except ValueError:pass
  time.sleep(.1)
 else:raise TimeoutError('MSI launch action did not produce a backend report')
 assert not result['errors'] and not result['qt_loaded'] and not result['slint_loaded'] and result['gui_starts']==0,result
 report['checks'].append('Windows Installer actually starts the entry; the fixture tray exits cleanly without loading a GUI')
except Exception:report['errors'].append(__import__('traceback').format_exc())
finally:
 if handle.value:api.MsiCloseHandle(handle)
 api.MsiSetInternalUI(previous,None)
 report['result']='FAIL' if report['errors'] else 'PASS'
 (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
 if report['errors']:raise SystemExit(1)
