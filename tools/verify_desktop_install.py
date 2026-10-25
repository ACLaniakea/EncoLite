"""Install only into an isolated directory, test the bundled hosts, then uninstall."""
from pathlib import Path
import argparse,ctypes as C,json,os,subprocess,time,uuid
from package_desktop import ROOT,VERSION
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
COMPONENT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),'python\\pythonw.exe')).upper()+'}'
target=ROOT/'.install-test/Enco Lite current'
data=ROOT/'.install-test/installed-desktop-userdata'
setup=ROOT/'release'/f'EncoLite-{VERSION}-win-x64-setup.exe'
parser=argparse.ArgumentParser()
parser.add_argument('--msi',action='store_true')
parser.add_argument('--setup',type=Path)
parser.add_argument('--report',type=Path,default=ROOT/'verification/desktop-installer.json')
options=parser.parse_args()
options.msi=options.msi or options.setup is None
if options.setup:setup=options.setup
api=C.WinDLL('msi')
api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
api.MsiGetComponentPathW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)]
report={'checks':[],'errors':[],'security_changes':False}
exe=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
group=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Enco Lite'
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def location():
    text=C.create_unicode_buffer(32768);size=C.c_uint32(len(text))
    state=api.MsiGetComponentPathW(PRODUCT,COMPONENT,text,C.byref(size))
    return Path(text.value).parent.parent if state in (3,4) and text.value else None
def install(label):
    if options.msi:
        msi=ROOT/'release'/f'EncoLite-{VERSION}-win-x64.msi'
        result=subprocess.run(f'"{exe}" /i "{msi}" /qn /norestart INSTALLDIR="{target}" CREATE_DESKTOP_SHORTCUT=0 REINSTALLMODE=amus /L*v "{ROOT/"verification"/(label+"-msi.log")}"',timeout=120)
        assert result.returncode in (0,3010),result.returncode
    else:
        subprocess.run([str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
            '/LANG=chinesesimplified',f'/DIR={target}','/TASKS=',
            f'/LOG={ROOT/"verification"/(label+".log")}'],check=True,timeout=120)
    assert location() and location().resolve()==target.resolve(),('install location',str(location()))
def uninstall():
    actual=location()
    if actual is None:return
    assert actual.resolve()==target.resolve(),'Refusing to remove a non-test installation'
    p=subprocess.run(f'"{exe}" /x {PRODUCT} /qn /norestart /L*v "{ROOT/"verification/desktop-uninstall.log"}"',timeout=90)
    assert p.returncode in (0,3010),('uninstall',p.returncode)
def ui_test(label):
    output=ROOT/'verification'/f'installed-{label}.json'
    subprocess.run([str(target/'python/python.exe'),str(ROOT/'tools/verify_new_desktop.py'),
        '--bundle',str(target),'--report',str(output),'--data-dir',str(data)],check=True,timeout=90)
    result=json.loads(output.read_text('utf-8'));assert result['result']=='PASS'
    check(label+': bundled Python and WebView2 pass all UI/lifetime/IPC checks')
try:
    index=0
    while True:
        product=C.create_unicode_buffer(39);status=api.MsiEnumRelatedProductsW(UPGRADE,0,index,product)
        if status==259:break
        assert status==0
        assert product.value==PRODUCT and location() and location().resolve()==target.resolve(),'Refusing to replace a non-test installation'
        index+=1
    uninstall()
    assert not group.exists() or not any(group.iterdir()),'Existing start-menu shortcuts are not owned by this test'
    install('desktop-install')
    assert (group/'Enco Lite.lnk').exists() and (group/'快捷控制.lnk').exists()
    assert not any(path.name.lower()=='slint.pyd' for path in target.rglob('*'))
    check(('system MSI' if options.msi else 'setup.exe')+' installs self-contained hosts, current client and both shortcuts, without Slint')
    ui_test('first-start')
    # Also exercise the exact pythonw production entry and single-instance IPC.
    output=ROOT/'verification/installed-pythonw.json';output.unlink(missing_ok=True)
    env={**os.environ,'ENCOLITE_DATA_DIR':str(data)}
    entry=[str(target/'python/pythonw.exe'),str(target/'desktop_entry.py')]
    process=subprocess.Popen([*entry,'--fixture','--tray-only','--test-timeout','10','--test-report',str(output)],env=env)
    try:
        time.sleep(2)
        subprocess.run([*entry,'--fixture','--quick'],check=True,env=env,timeout=15)
        assert process.wait(timeout=20)==0
    finally:
        if process.poll() is None:
            subprocess.run([*entry,'--quit'],env=env,timeout=10);process.wait(timeout=15)
    result=json.loads(output.read_text('utf-8'))
    assert result['gui_starts']==1 and not result['errors'] and not result['slint_loaded'],result
    check('pythonw entry starts once; a second launch opens quick controls in the existing session')
    preferences=data/'preferences.json';saved=preferences.read_bytes()
    install('desktop-reinstall');assert preferences.read_bytes()==saved
    ui_test('after-reinstall')
    check('same-version reinstall preserves user preferences')
    saved=preferences.read_bytes();uninstall()
    assert location() is None and not (target/'python/pythonw.exe').exists()
    assert not group.exists() and preferences.read_bytes()==saved
    check('system MSI uninstall removes app and shortcuts while retaining preferences')
except Exception:report['errors'].append(__import__('traceback').format_exc())
finally:
    try:uninstall()
    except Exception:report['errors'].append('cleanup: '+__import__('traceback').format_exc())
    report['result']='FAIL' if report['errors'] else 'PASS'
    report['installation_method']='system MSI' if options.msi else str(setup)
    options.report.write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)
    if report['errors']:raise SystemExit(1)
