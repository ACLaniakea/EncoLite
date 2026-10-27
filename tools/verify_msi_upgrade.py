"""One-invocation major-upgrade regression with isolated product registrations.

No REINSTALLMODE/REINSTALL override. --full exercises the complete runtime;
the default compact fixture keeps real Python binaries and changed/removed files.
"""
from pathlib import Path
import argparse,ctypes as C,hashlib,json,os,shutil,subprocess,sys,traceback,uuid,winreg
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
sys.stdout.reconfigure(encoding='utf-8')
parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');parser.add_argument('--legacy-target',action='store_true');parser.add_argument('--local-programs',action='store_true')
args=parser.parse_args()
OUT=ROOT/'verification/msi-upgrade';OUT.mkdir(parents=True,exist_ok=True)
WORK=ROOT/'.install-test/msi-upgrade-v2';BUNDLE=WORK/'payload';TARGET=WORK/'已安装客户端';WRONG=WORK/'must-not-be-used'
if args.local_programs:TARGET=Path(os.environ['LOCALAPPDATA'])/'Programs/Enco Lite Upgrade Validation'
UPGRADE='{'+str(uuid.uuid5(uuid.NAMESPACE_URL,'https://github.com/ACLaniakea/EncoLite/tests/major-upgrade-v2')).upper()+'}'
NAME='Enco Lite Upgrade Validation'
OLD='0.5.0-upgrade-baseline';NEW='0.5.0-upgrade-target'
FAILED='0.5.0-upgrade-failed'
products={name:'{'+str(uuid.uuid5(uuid.UUID(UPGRADE),name)).upper()+'}' for name in (OLD,NEW,FAILED)}
EXE=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
api=C.WinDLL('msi');api.MsiQueryProductStateW.argtypes=[C.c_wchar_p];api.MsiQueryProductStateW.restype=C.c_int
api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
source=ROOT/'tools/build_msi.py';legacy=ROOT/'tools/fixtures/msi_preview21.py'
report={'checks':[],'errors':[],'full_runtime':args.full,'legacy_target':args.legacy_target,'local_programs':args.local_programs,'directory':str(TARGET),'upgrade_code':UPGRADE,
        'scope':'Isolated per-user products and installation directory; one msiexec /i per upgrade; no forced file reinstall, real-app upgrade, Bluetooth operation or security change.'}
author_manifest=ROOT/'build/msi-manifest.json'
saved_manifest=author_manifest.read_bytes() if author_manifest.exists() else None
protected=[Path(os.environ['APPDATA'])/'EncoLite/preferences.json',Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup/Enco Lite.lnk']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
original={p:digest(p) for p in protected}
def check(text):report['checks'].append(text);print('PASS',text,flush=True)
def installed(name):return api.MsiQueryProductStateW(products[name])==5
def uninstall(name):
    # A failed legacy rollback can leave an advertised product (state 1).
    # Remove that test registration too, using the installer rather than registry edits.
    if api.MsiQueryProductStateW(products[name])<1:return
    command=[str(EXE),'/x',products[name],'/qn','/norestart']
    if name==FAILED:command.append('UPGRADINGPRODUCTCODE='+products[NEW])
    p=subprocess.run([*command,'/L*v',str(OUT/('cleanup-'+name+'.log'))],timeout=120)
    assert p.returncode in (0,3010),(name,p.returncode)
def build(name,number,old_builder=False):
    author=legacy if old_builder else source
    assert author.is_file(),str(author)
    output=WORK/(name+'.msi')
    config={'BUNDLE':str(BUNDLE),'VERSION':name,'MSI_VERSION':number,'UPGRADE':UPGRADE,'APP_NAME':NAME,'PRODUCT':products[name],'OUTPUT':str(output)}
    # msilib keeps identifier/short-name state globally. Use separate processes,
    # just as real release builds do, rather than sharing it across two databases.
    code="from pathlib import Path;import json,sys;source=Path(sys.argv[1]);sys.path.insert(0,str(source.parent));d={'__name__':'upgrade_fixture_builder','__file__':str(source)};exec(compile(Path(sys.argv[2]).read_text('utf-8'),str(source),'exec'),d);config=json.loads(sys.argv[3]);config.update(BUNDLE=Path(config['BUNDLE']),OUTPUT=Path(config['OUTPUT']));d.update(config);d['build']()"
    subprocess.run([sys.executable,'-c',code,str(source),str(author),json.dumps(config)],check=True,timeout=120)
    return output
def install(msi,stage,directory=None,expected=0):
    location='' if directory is None else ' INSTALLDIR="'+str(directory)+'"'
    cmd='"'+str(EXE)+'" /i "'+str(msi)+'" /qn /norestart CREATE_DESKTOP_SHORTCUT=0'+location+' /L*v "'+str(OUT/(stage+'.log'))+'"'
    p=subprocess.run(cmd,timeout=120)
    report[stage+'_exit_code']=p.returncode
    assert p.returncode in ((0,3010) if expected==0 else (expected,)),(stage,p.returncode)
def expected_files():return {str(p.relative_to(BUNDLE)):digest(p) for p in BUNDLE.rglob('*') if p.is_file()}
def verify_versions(msi):
    import msilib as m
    from build_msi import file_version
    db=m.OpenDatabase(str(msi),m.MSIDBOPEN_READONLY)
    assert db.GetSummaryInformation(0).GetProperty(m.PID_WORDCOUNT)==10
    def rows(sql):
        view=db.OpenView(sql);view.Execute(None);result=[]
        while (record:=view.Fetch()) is not None:
            result.append(tuple(record.GetString(i+1) for i in range(record.GetFieldCount())))
        view.Close();return result
    dirs={name:(parent,default) for name,parent,default in rows('SELECT `Directory`,`Directory_Parent`,`DefaultDir` FROM `Directory`')}
    components=dict(rows('SELECT `Component`,`Directory_` FROM `Component`'))
    def relative(name):
        if name=='INSTALLDIR':return Path('.')
        parent,folder=dirs[name]
        return relative(parent)/folder.split('|')[-1].split(':')[0]
    api.MsiGetFileVersionW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32),C.c_wchar_p,C.POINTER(C.c_uint32)]
    api.MsiGetFileVersionW.restype=C.c_uint32
    count=0
    for filename,component,version,language in rows('SELECT `FileName`,`Component_`,`Version`,`Language` FROM `File`'):
        path=BUNDLE/relative(components[component])/filename.split('|')[-1]
        expected=file_version(path,api)
        assert (version or None,language or None)==expected,(str(path),version,language,expected)
        if expected[0]:count+=1
    assert count>0;report['versioned_files_verified']=count
    check('MSI file-version and language fields match every packaged version resource')
def failure_copy(msi):
    import msilib as m
    output=WORK/'intentional-failure.msi';shutil.copy2(msi,output)
    db=m.OpenDatabase(str(output),m.MSIDBOPEN_TRANSACT)
    for prop,value in (('ProductCode',products[FAILED]),('ProductRelease',FAILED)):
        view=db.OpenView("UPDATE `Property` SET `Value`='"+value+"' WHERE `Property`='"+prop+"'");view.Execute(None);view.Close()
    m.add_data(db,'CustomAction',[('IntentionalUpgradeFailure',19,None,'Isolated upgrade rollback test')])
    m.add_data(db,'InstallExecuteSequence',[('IntentionalUpgradeFailure','NOT Installed',1505)])
    summary=db.GetSummaryInformation(1);summary.SetProperty(m.PID_REVNUMBER,'{'+str(uuid.uuid4()).upper()+'}');summary.Persist();db.Commit()
    return output
def assert_payload(expected):
    missing=[name for name in expected if not (TARGET/name).is_file()]
    different=[name for name,value in expected.items() if (TARGET/name).is_file() and digest(TARGET/name)!=value]
    report['missing_files']=missing;report['different_files']=different
    assert not missing and not different,{'missing':missing[:12],'different':different[:12]}
    assert not WRONG.exists(),'The existing installation directory was not retained'
def arp_version():
    key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\EncoLite.'+UPGRADE.strip('{}')
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as handle:
        return winreg.QueryValueEx(handle,'DisplayVersion')[0],winreg.QueryValueEx(handle,'UninstallString')[0]
try:
    for index in range(8):
        code=C.create_unicode_buffer(39);status=api.MsiEnumRelatedProductsW(UPGRADE,0,index,code)
        if status==259:break
        assert status==0 and code.value in products.values(),(status,code.value)
    for name in products:uninstall(name)
    if WORK.exists():shutil.rmtree(WORK)
    BUNDLE.mkdir(parents=True)
    if args.full:
        shutil.copytree(ROOT/'dist/EncoLite-qt',BUNDLE,dirs_exist_ok=True)
    else:
        shutil.copytree(ROOT/'dist/EncoLite-qt/python',BUNDLE/'python')
        (BUNDLE/'ui/assets').mkdir(parents=True)
        shutil.copy2(ROOT/'ui/assets/app-icon.ico',BUNDLE/'ui/assets/app-icon.ico')
        (BUNDLE/'desktop_entry.py').write_text('# Isolated installer fixture, no startup changes.\n','utf-8')
        (BUNDLE/'runtime-manifest.json').write_text(json.dumps({'entry_point':'python/pythonw.exe','entry_arguments':'"[INSTALLDIR]desktop_entry.py"'}),'utf-8')
    (BUNDLE/'revision.txt').write_text('old payload\n','utf-8')
    (BUNDLE/'obsolete.txt').write_text('remove on upgrade\n','utf-8')
    old_msi=build(OLD,'0.5.21',old_builder=True)
    install(old_msi,'baseline',TARGET)
    assert installed(OLD) and (TARGET/'python/pythonw.exe').is_file()
    check('the older product installs normally with standard MSI defaults')
    old_expected=expected_files()
    (BUNDLE/'revision.txt').write_text('new payload\n','utf-8')
    (BUNDLE/'desktop_entry.py').write_bytes((BUNDLE/'desktop_entry.py').read_bytes()+b'\n# upgraded source marker\n')
    if (BUNDLE/'docs/BUILD.md').is_file():
        (BUNDLE/'docs/BUILD.md').write_bytes((BUNDLE/'docs/BUILD.md').read_bytes()+b'\nUpgrade verification marker.\n')
    (BUNDLE/'obsolete.txt').unlink();(BUNDLE/'added.txt').write_text('new file\n','utf-8')
    new_msi=build(NEW,'0.5.22',old_builder=args.legacy_target)
    expected=expected_files()
    if not args.legacy_target:
        verify_versions(new_msi)
        install(failure_copy(new_msi),'intentional-failure',expected=1603)
        report['old_retained_after_failure']=installed(OLD)
        report['failed_test_registration_after_rollback']=installed(FAILED)
        assert installed(OLD)
        assert_payload(old_expected)
        assert arp_version()[0]==OLD
        check('a failure before old-product removal preserves the old product and every original file')
        uninstall(FAILED)
        assert installed(OLD);assert_payload(old_expected)
    install(new_msi,'upgrade-once',WRONG)
    report['old_registered_after_upgrade']=installed(OLD);report['new_registered_after_upgrade']=installed(NEW)
    assert installed(NEW) and api.MsiQueryProductStateW(products[OLD])==-1,report
    assert_payload(expected)
    assert not (TARGET/'obsolete.txt').exists()
    check('one invocation replaces the old product and retains every expected file, including unchanged binaries and changed source')
    check('upgrade keeps the previous directory, adds new files and removes obsolete files')
    version,command=arp_version();assert version==NEW and products[NEW] in command
    check('the single application-list entry points to the new version and uninstaller')
    install(old_msi,'downgrade-blocked',expected=1603)
    assert installed(NEW);assert_payload(expected)
    check('attempting a downgrade leaves the working new version intact')
    install(new_msi,'same-version-repair')
    assert installed(NEW);assert_payload(expected)
    check('same-version maintenance also succeeds without command-line repair flags')
    if args.full:
        subprocess.run([sys.executable,str(ROOT/'tools/verify_qt_bundle.py'),str(TARGET)],check=True,timeout=45)
        check('the upgraded full runtime renders all pages and popup windows')
    uninstall(NEW);assert not installed(NEW) and not (TARGET/'python/pythonw.exe').exists()
    check('the upgraded product uninstalls normally')
except Exception:report['errors'].append(traceback.format_exc())
finally:
    for name in products:
        try:uninstall(name)
        except Exception:report['errors'].append('cleanup: '+traceback.format_exc())
    report['user_files_unchanged']=all(digest(p)==value for p,value in original.items())
    assert report['user_files_unchanged'],'User preferences/startup link unexpectedly changed'
    if saved_manifest is not None:author_manifest.write_bytes(saved_manifest)
    report['result']='FAIL' if report['errors'] else 'PASS'
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if report['errors']:raise SystemExit(1)
