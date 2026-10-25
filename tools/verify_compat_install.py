"""Install, run, reinstall and uninstall only the isolated compatibility candidate."""
from pathlib import Path
import ctypes as C,json,os,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.3.0-preview.3'
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
COMPONENT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),'runtime\\pythonw.exe')).upper()+'}'
target=ROOT/'.install-test/compat installed'
setup=ROOT/'.tools/compat-release'/f'EncoLite-{VERSION}-win-x64-setup.exe'
api=C.WinDLL('msi')
api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
api.MsiGetComponentPathW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)]
report={'checks':[],'errors':[],'security_changes':False,'pending':['foreground/window interaction after unlock','real X3 connection']}
env={**os.environ,'APPDATA':str(ROOT/'.install-test/compat userdata'),'PYTHONIOENCODING':'utf-8'}
msiexec=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
group=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Enco Lite'
def location():
    text=C.create_unicode_buffer(32768);size=C.c_uint32(len(text))
    state=api.MsiGetComponentPathW(PRODUCT,COMPONENT,text,C.byref(size))
    return Path(text.value).parent.parent if state in (3,4) and text.value else None
def check(label):
    report['checks'].append(label);print('PASS',label,flush=True)
def install(label):
    subprocess.run([str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
        '/LANG=chinesesimplified',f'/DIR={target}','/TASKS=',
        f'/LOG={ROOT/"verification"/(label+".log")}'],check=True,timeout=90)
    assert location() and location().resolve()==target.resolve(),('installed component location',str(location()),str(target))
def uninstall():
    actual=location()
    if actual is None:return
    assert actual.resolve()==target.resolve(),'Refusing to remove a non-test installation'
    result=subprocess.run(f'"{msiexec}" /x {PRODUCT} /qn /norestart /L*v "{ROOT/"verification/compat-uninstall.log"}"',timeout=60)
    assert result.returncode in (0,3010),('uninstall',result.returncode)
def smoke(label):
    path=ROOT/'verification'/f'compat-{label}.json';path.unlink(missing_ok=True)
    p=subprocess.run([str(target/'runtime/pythonw.exe'),str(target/'run.py'),
        '--smoke-test','--no-tray','--test-report',str(path)],env=env,capture_output=True,timeout=40)
    assert p.returncode==0,(label,p.returncode,p.stderr.decode('utf-8',errors='replace'))
    assert path.exists() and json.loads(path.read_text('utf-8'))['result']=='PASS'
    check(label+': installed pythonw entry and all seven pages')
try:
    # Never upgrade/replace the user's actual app during candidate verification.
    index=0
    while True:
        product=C.create_unicode_buffer(39)
        status=api.MsiEnumRelatedProductsW(UPGRADE,0,index,product)
        if status==259:break
        assert status==0
        assert product.value==PRODUCT and location() and location().resolve()==target.resolve(), 'An Enco Lite installation already exists; isolated test refused'
        index+=1
    uninstall()  # Clean up only this exact candidate if a previous test stopped.
    install('compat-install')
    assert (target/'runtime/pythonw.exe').exists() and (target/'.build-deps/slint/slint.pyd').exists()
    assert (group/'Enco Lite.lnk').exists() and (group/'快捷控制.lnk').exists()
    check('setup.exe installs runtime, app and both shortcuts')
    for index in range(3):smoke(f'start-{index+1}')
    prefs=Path(env['APPDATA'])/'EncoLite/preferences.json';prefs.parent.mkdir(parents=True,exist_ok=True)
    prefs.write_text('{"dark":true,"connection_popup":false}','utf-8');saved=prefs.read_bytes()
    install('compat-reinstall')
    assert prefs.read_bytes()==saved
    smoke('after-reinstall')
    check('reinstall preserves existing preferences')
    uninstall()
    assert location() is None and not (target/'runtime/pythonw.exe').exists()
    assert not group.exists() and prefs.read_bytes()==saved
    check('system MSI uninstall removes app and shortcuts, preserving preferences')
except Exception as error:report['errors'].append(__import__('traceback').format_exc())
finally:
    try:uninstall()
    except Exception as error:report['errors'].append('cleanup: '+repr(error))
    report['result']='FAIL' if report['errors'] else 'PASS_WITH_PENDING_CHECKS'
    (ROOT/'verification/compat-installer.json').write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)
    if report['errors']:raise SystemExit(1)
