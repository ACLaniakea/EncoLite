"""Verify the candidate setup/MSI only in this workspace's isolated directory."""
from pathlib import Path
import ctypes as C
import os,sys,subprocess,json,time,uuid
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.3.0-preview.2'
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
EXE_COMPONENT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),'EncoLite.exe')).upper()+'}'
setup=ROOT/'release'/f'EncoLite-{VERSION}-win-x64-setup.exe'
target=ROOT/'.install-test/Enco Lite'
prefs_root=ROOT/'.install-test/userdata'
env={**os.environ,'APPDATA':str(prefs_root)}
report={'checks':[],'errors':[]}
api=C.WinDLL('msi')
api.MsiGetComponentPathW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)]
api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]

def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def installed_location(product=PRODUCT):
    text=C.create_unicode_buffer(32768);length=C.c_uint32(len(text))
    state=api.MsiGetComponentPathW(product,EXE_COMPONENT,text,C.byref(length))
    return Path(text.value).parent if state in (3,4) and text.value else None

def check_existing():
    index=0
    while True:
        text=C.create_unicode_buffer(39)
        status=api.MsiEnumRelatedProductsW(UPGRADE,0,index,text)
        if status==259:break
        assert status==0,('MsiEnumRelatedProducts',status)
        location=installed_location(text.value)
        assert location and location.resolve()==target.resolve(),'Refusing to replace a non-test Enco Lite installation'
        index+=1

def install(label):
    subprocess.run([str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
        '/LANG=chinesesimplified',f'/DIR={target}','/TASKS=',
        f'/LOG={ROOT/"verification"/(label+".log")}'],check=True,timeout=90)

def uninstall():
    location=installed_location()
    if location is None:return
    assert location.resolve()==target.resolve(),'Refusing to uninstall a non-test installation'
    exe=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
    log=ROOT/'verification/installer-msi-uninstall.log'
    command=f'"{exe}" /x {PRODUCT} /qn /norestart /L*v "{log}"'
    result=subprocess.run(command,timeout=60)
    assert result.returncode in (0,3010),('uninstall',result.returncode)

try:
    assert setup.exists(),'Build the candidate installer first'
    check_existing()
    install('installer-install')
    assert (target/'EncoLite.exe').exists() and (target/'python313.dll').exists()
    assert (target/'runtime/python313.zip').exists()
    assert not (target/'app/.build-deps/slint/slint.pyd').exists()
    assert installed_location().resolve()==target.resolve()
    assert (target/'Source'/f'EncoLite-{VERSION}-source.zip').exists()
    check('per-user MSI install contains native app, signed runtime and corresponding source')
    group=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Enco Lite'
    assert (group/'Enco Lite.lnk').exists() and (group/'快捷控制.lnk').exists()
    check('main and quick-control start-menu shortcuts created')
    subprocess.run([sys.executable,str(ROOT/'tools/verify_bundle.py'),str(target)],check=True,env=env,timeout=35)
    check('installed native app passes seven-page UI smoke without external Python')
    preferences=prefs_root/'EncoLite/preferences.json';preferences.parent.mkdir(parents=True,exist_ok=True)
    preferences.write_text('{"dark":true,"connection_popup":false}','utf-8');saved=preferences.read_bytes()
    install('installer-upgrade')
    assert preferences.read_bytes()==saved
    subprocess.run([sys.executable,str(ROOT/'tools/verify_bundle.py'),str(target)],check=True,env=env,timeout=35)
    check('same-version reinstall preserves preferences and still starts successfully')
    uninstall()
    assert not (target/'EncoLite.exe').exists() and installed_location() is None
    assert not group.exists() and preferences.read_bytes()==saved
    check('system MSI uninstall removes application, shortcuts and registration; preferences retained')
except Exception as error:report['errors'].append(repr(error))
finally:
    try:uninstall()
    except Exception as error:report['errors'].append('cleanup: '+repr(error))
    report['result']='FAIL' if report['errors'] else 'PASS'
    (ROOT/'verification/installer.json').write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)
    if report['errors']:raise SystemExit(1)
