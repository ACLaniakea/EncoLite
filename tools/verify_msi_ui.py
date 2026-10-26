"""Validate the authored wizard with Windows Installer, without installing it.

This checks MSI dialog references, conditions, directory resolution, launch
arguments and native dialog creation. It does not simulate user button clicks.
"""
from pathlib import Path
import ctypes as C,json,sys,warnings,struct
warnings.filterwarnings('ignore',category=DeprecationWarning)
import msilib as m
ROOT=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(ROOT/'tools'))
from build_msi import VERSION
PATH=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'release'/f'EncoLite-{VERSION}-win-x64.msi'
OUT=ROOT/'verification/qt-msi-ui';OUT.mkdir(parents=True,exist_ok=True)
report={'package':PATH.name,'checks':[],'errors':[],'scope':'MSI database, native conditions/directory costing and authoring dialog preview; no automated mouse or keyboard input'}
def check(name):report['checks'].append(name);print('PASS '+name,flush=True)
C.OleDLL('ole32').CoInitialize(None)
db=m.OpenDatabase(str(PATH),m.MSIDBOPEN_READONLY)
def rows(table,columns=None):
 select=','.join('`'+c+'`' for c in columns) if columns else '*'
 view=db.OpenView('SELECT '+select+' FROM `'+table+'`');view.Execute(None)
 names=view.GetColumnInfo(m.MSICOLINFO_NAMES);names=[names.GetString(i) for i in range(1,names.GetFieldCount()+1)]
 result=[]
 while record:=view.Fetch():result.append(dict(zip(names,[record.GetString(i) for i in range(1,len(names)+1)])))
 view.Close();return result
api=C.WinDLL('msi')
for name,types in {
 'MsiOpenDatabaseW':[C.c_wchar_p,C.c_void_p,C.POINTER(C.c_uint32)],
 'MsiEnableUIPreview':[C.c_uint32,C.POINTER(C.c_uint32)],
 'MsiPreviewDialogW':[C.c_uint32,C.c_wchar_p],
 'MsiOpenPackageExW':[C.c_wchar_p,C.c_uint32,C.POINTER(C.c_uint32)],
 'MsiDoActionW':[C.c_uint32,C.c_wchar_p],
 'MsiSetPropertyW':[C.c_uint32,C.c_wchar_p,C.c_wchar_p],
 'MsiGetPropertyW':[C.c_uint32,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)],
 'MsiGetTargetPathW':[C.c_uint32,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)],
 'MsiSetTargetPathW':[C.c_uint32,C.c_wchar_p,C.c_wchar_p],
 'MsiEvaluateConditionW':[C.c_uint32,C.c_wchar_p],
 'MsiCloseHandle':[C.c_uint32],
 'MsiDatabaseOpenViewW':[C.c_uint32,C.c_wchar_p,C.POINTER(C.c_uint32)],
 'MsiViewExecute':[C.c_uint32,C.c_uint32],
 'MsiViewFetch':[C.c_uint32,C.POINTER(C.c_uint32)],
 'MsiRecordReadStream':[C.c_uint32,C.c_uint32,C.c_void_p,C.POINTER(C.c_uint32)],
 'MsiGetLastErrorRecord':[],
 'MsiFormatRecordW':[C.c_uint32,C.c_uint32,C.c_wchar_p,C.POINTER(C.c_uint32)],
}.items():getattr(api,name).argtypes=types
handle=C.c_uint32();database=C.c_uint32();preview=C.c_uint32()
previous=api.MsiSetInternalUI(2,None)
def get(name):
 value=C.create_unicode_buffer(32768);length=C.c_uint32(len(value))
 assert api.MsiGetPropertyW(handle,name,value,C.byref(length))==0
 return value.value
def set_(name,value):assert api.MsiSetPropertyW(handle,name,value)==0
def action(name):assert api.MsiDoActionW(handle,name)==0,name
try:
 dialogs={r['Dialog']:r for r in rows('Dialog')};controls=rows('Control',['Dialog_','Control','Type','Control_Next']);events=rows('ControlEvent')
 keys={(r['Dialog_'],r['Control']) for r in controls}
 assert len(dialogs)>=11 and len(controls)>=80
 for row in controls:
  assert row['Dialog_'] in dialogs
  if row['Control_Next']:assert (row['Dialog_'],row['Control_Next']) in keys,row
 for name in dialogs:
  links={r['Control']:r['Control_Next'] for r in controls if r['Dialog_']==name and r['Control_Next']}
  if links:
   assert set(links)==set(links.values()) and len(set(links.values()))==len(links),(name,'tab order must be a cycle',links)
   first=next(iter(links));visited={first};current=links[first]
   while current not in visited:visited.add(current);current=links[current]
   assert visited==set(links) and current==first,(name,'disconnected tab order',links)
 for row in dialogs.values():
  for column in ('Control_First','Control_Default','Control_Cancel'):
   if row[column]:assert (row['Dialog'],row[column]) in keys,row
 for row in events:
  assert (row['Dialog_'],row['Control_']) in keys
  if row['Event'] in ('NewDialog','SpawnDialog'):assert row['Argument'] in dialogs,row
 assert {r['Argument'] for r in events if r['Dialog_']=='ErrorDlg'}=={'Error'+n for n in ('Ok','Cancel','Abort','Retry','Ignore','Yes','No')}
 check('wizard pages, navigation, tab targets and native error buttons have valid references')
 properties={r['Property']:r['Value'] for r in rows('Property')}
 assert properties['ProductLanguage']=='2052' and properties['ARPSYSTEMCOMPONENT']=='1'
 assert '2052' in str(db.GetSummaryInformation(0).GetProperty(m.PID_TEMPLATE))
 assert any(r['Name']=='UninstallString' and '/qf' in r['Value'] for r in rows('Registry'))
 assert any(r['Dialog_']=='RemoveDlg' and r['Control']=='ProductIcon' for r in controls)
 assert any(r['Action']=='RemoveFiles' and '移除' in r['Description'] for r in rows('ActionText'))
 check('Chinese language, matching removal layout and full-UI app-list command are authored')
 sequence={r['Action']:r for r in rows('InstallUISequence')}
 assert int(sequence['AppSearch']['Sequence'])<int(sequence['UseExistingDirectory']['Sequence'])<int(sequence['LaunchConditions']['Sequence'])
 assert int(sequence['CostFinalize']['Sequence'])<int(sequence['WelcomeDlg']['Sequence'])<int(sequence['ProgressDlg']['Sequence'])<int(sequence['ExecuteAction']['Sequence'])
 assert {sequence[n]['Sequence'] for n in ('ExitDialog','FatalError','UserExit')}=={'-1','-3','-2'}
 check('full UI runs before ExecuteAction and has success, cancel and failure pages')
 mappings=rows('EventMapping')
 assert any(r['Event']=='SetProgress' and r['Attribute']=='Progress' for r in mappings)
 assert any(r['Event']=='ActionText' and r['Attribute']=='Text' for r in mappings)
 assert any(r['Event']=='ActionData' and r['Attribute']=='Text' for r in mappings)
 launch=[r for r in events if r['Event']=='DoAction' and r['Argument']=='LaunchApplication'];assert len(launch)==1
 actions={r['Action']:r for r in rows('CustomAction')}
 assert actions['SetLauncher']['Target']=='[INSTALLDIR]python\\pythonw.exe'
 assert actions['LaunchApplication']['Type']=='242' and actions['LaunchApplication']['Source']=='INSTALLER_PYTHON'
 assert actions['LaunchApplication']['Target']=='"[INSTALLDIR]desktop_entry.py" --restart'
 assert 'REMOVE' in launch[0]['Condition'] and 'LAUNCH_AFTER_INSTALL' in launch[0]['Condition']
 assert dialogs['OptionsDlg']['Control_First']=='Install'
 assert {'RemoveDlg','FilesInUse','MsiRMFilesInUse'} <= set(dialogs)
 assert any(r['Dialog_']=='MaintenanceDlg' and r['Control_']=='Repair' and r['Event']=='[REMOVE]' and r['Argument']=='{}' for r in events)
 assert any(r['Dialog_']=='RemoveDlg' and r['Control_']=='Remove' and r['Event']=='[REINSTALL]' and r['Argument']=='{}' for r in events)
 check('progress subscriptions and optional per-user finish launch are authored')
 assert api.MsiOpenPackageExW(str(PATH.resolve()),1,C.byref(handle))==0
 conditions={r['Condition'] for r in events+rows('ControlCondition')+rows('InstallUISequence')+rows('InstallExecuteSequence') if r.get('Condition')}
 for condition in conditions:assert api.MsiEvaluateConditionW(handle,condition)!=3,condition
 check('Windows Installer accepts every authored control and sequence condition')
 for name in ('FindRelatedProducts','AppSearch','UseExistingDirectory','LaunchConditions','ValidateProductID','CostInitialize','FileCost','CostFinalize','SetInstallLocation'):
  if name!='UseExistingDirectory' or get('EXISTINGINSTALLDIR'):action(name)
 target=get('INSTALLDIR');assert target and get('ARPINSTALLLOCATION')==target
 report['resolved_install_directory']=target;report['existing_install_directory']=get('EXISTINGINSTALLDIR')
 assert int(get('WINDOWSBUILD'))>=17763
 if get('EXISTINGINSTALLDIR'):
  assert Path(target).resolve()==Path(get('EXISTINGINSTALLDIR')).resolve()
  check('an installed version is found by its stable component and upgrades retain its folder')
 else:
  selected=str(ROOT/'.install-test/Installer Path With Spaces')+'\\'
  assert api.MsiSetTargetPathW(handle,'INSTALLDIR',selected)==0
  assert Path(get('INSTALLDIR')).resolve()==Path(selected).resolve()
  check('a fresh installation accepts a custom folder containing spaces')
 set_('UILevel','5');set_('Installed','')
 assert api.MsiEvaluateConditionW(handle,sequence['WelcomeDlg']['Condition'])==1
 assert api.MsiEvaluateConditionW(handle,sequence['DefaultDesktopShortcut']['Condition'])==1
 action('DefaultDesktopShortcut');assert get('CREATE_DESKTOP_SHORTCUT')=='1'
 set_('CREATE_DESKTOP_SHORTCUT','0')
 assert api.MsiEvaluateConditionW(handle,sequence['DefaultDesktopShortcut']['Condition'])==0
 set_('Installed','1');set_('REMOVE','')
 assert api.MsiEvaluateConditionW(handle,sequence['MaintenanceDlg']['Condition'])==1
 assert api.MsiEvaluateConditionW(handle,sequence['WelcomeDlg']['Condition'])==0
 set_('REMOVE','ALL');action('RememberRemoveRequest');assert api.MsiEvaluateConditionW(handle,launch[0]['Condition'])==0
 assert api.MsiEvaluateConditionW(handle,sequence['RemoveDlg']['Condition'])==1
 assert api.MsiEvaluateConditionW(handle,sequence['MaintenanceDlg']['Condition'])==0
 check('fresh install, explicit shortcut opt-out, maintenance and uninstall launch conditions behave correctly')
 api.MsiCloseHandle(handle);handle=C.c_uint32()
 assert api.MsiOpenDatabaseW(str(PATH.resolve()),C.c_void_p(0),C.byref(database))==0
 assert all(c['Type']=='Bitmap' for c in controls if c['Control']=='Icon')
 for key,dimensions in [('InstallerIcon',(256,256)),('InstallerHeader',(740,112))]:
  view=C.c_uint32();record=C.c_uint32()
  try:
   assert api.MsiDatabaseOpenViewW(database,"SELECT `Data` FROM `Binary` WHERE `Name`='"+key+"'",C.byref(view))==0
   assert api.MsiViewExecute(view,0)==0 and api.MsiViewFetch(view,C.byref(record))==0
   data=C.create_string_buffer(54);length=C.c_uint32(len(data))
   assert api.MsiRecordReadStream(record,1,data,C.byref(length))==0 and length.value==54
   assert data.raw[:2]==b'BM' and struct.unpack_from('<ii',data.raw,18)==dimensions
   assert struct.unpack_from('<H',data.raw,28)[0]==24
  finally:
   if record.value:api.MsiCloseHandle(record)
   if view.value:api.MsiCloseHandle(view)
 check('MSI embeds a full 256 px icon and high-resolution header as native 24-bit bitmaps')
 api.MsiSetInternalUI(5,None)
 status=api.MsiEnableUIPreview(database,C.byref(preview));assert status==0,('MsiEnableUIPreview',status)
 for name in dialogs:
  status=api.MsiPreviewDialogW(preview,name)
  if status:
   error=api.MsiGetLastErrorRecord();text=C.create_unicode_buffer(32768);length=C.c_uint32(len(text))
   if error:api.MsiFormatRecordW(0,error,text,C.byref(length));api.MsiCloseHandle(error)
   raise RuntimeError((name,status,text.value))
 assert api.MsiPreviewDialogW(preview,'')==0
 check('Windows Installer creates every native wizard dialog through its authoring preview API')
except Exception:report['errors'].append(__import__('traceback').format_exc())
finally:
 for value in (preview,handle,database):
  if value.value:api.MsiCloseHandle(value)
 api.MsiSetInternalUI(previous,None)
 report['result']='FAIL' if report['errors'] else 'PASS'
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps(report,ensure_ascii=False),flush=True)
 if report['errors']:raise SystemExit(1)
