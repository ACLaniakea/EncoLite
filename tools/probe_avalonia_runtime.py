"""Compare a minimal Avalonia app after copying and MSI installation.

This is a framework experiment only: no Bluetooth or production UI is migrated.
"""
from pathlib import Path
import ctypes as C,json,os,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.tools/avalonia-runtime';BUNDLE=WORK/'bundle'
TARGET=ROOT/'.install-test/avalonia installed'
SDK=ROOT.parent/'构建工具/dotnet-10.0.302'
VERSION='0.3.0-avalonia-probe'
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
COMPONENT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),'runtime\\dotnet.exe')).upper()+'}'
api=C.WinDLL('msi')
api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
api.MsiGetComponentPathW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)]
product=C.create_unicode_buffer(39)
assert api.MsiEnumRelatedProductsW(UPGRADE,0,0,product)==259,'Refusing to replace an existing installation'
if BUNDLE.exists():shutil.rmtree(BUNDLE)
shutil.copytree(ROOT/'.tools/avalonia-probe/bin/Release/net10.0/win-x64/publish',BUNDLE,ignore=shutil.ignore_patterns('*.pdb'))
runtime=BUNDLE/'runtime';runtime.mkdir()
shutil.copy2(SDK/'dotnet.exe',runtime/'dotnet.exe')
shutil.copytree(SDK/'host/fxr/10.0.10',runtime/'host/fxr/10.0.10')
shutil.copytree(SDK/'shared/Microsoft.NETCore.App/10.0.10',runtime/'shared/Microsoft.NETCore.App/10.0.10')
(BUNDLE/'runtime-manifest.json').write_text(json.dumps({'entry_point':'runtime/dotnet.exe','entry_arguments':'"[INSTALLDIR]Probe.dll"'}),'utf-8')
report={'runs':[],'security_changes':False,'real_device_tested':False}
def run(root,label):
    output=ROOT/'verification'/f'avalonia-{label}.json';output.unlink(missing_ok=True)
    p=subprocess.run([str(root/'runtime/dotnet.exe'),str(root/'Probe.dll')],capture_output=True,timeout=25,
        env={**os.environ,'ENCOLITE_PROBE_REPORT':str(output)})
    item={'label':label,'exit':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
    if output.exists():item['window_report']=json.loads(output.read_text('utf-8'))
    report['runs'].append(item);print(json.dumps(item,ensure_ascii=True),flush=True)
    assert p.returncode==0 and item.get('window_report',{}).get('result')=='PASS'
def location():
    text=C.create_unicode_buffer(32768);size=C.c_uint32(len(text))
    state=api.MsiGetComponentPathW(PRODUCT,COMPONENT,text,C.byref(size))
    return Path(text.value).parent.parent if state in (3,4) and text.value else None
exe=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
try:
    for i in range(3):run(BUNDLE,f'copy-{i+1}')
    msi=WORK/'avalonia-probe.msi'
    subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py'),'--bundle',str(BUNDLE),'--output',str(msi),'--version',VERSION,'--msi-version','0.3.5'],check=True)
    p=subprocess.run(f'"{exe}" /i "{msi}" /qn /norestart INSTALLDIR="{TARGET}" /L*v "{ROOT/"verification/avalonia-install.log"}"',timeout=90)
    assert p.returncode in (0,3010),p.returncode
    assert location() and location().resolve()==TARGET.resolve()
    for i in range(2):run(TARGET,f'installed-{i+1}')
except Exception:report['error']=__import__('traceback').format_exc()
finally:
    if location():
        assert location().resolve()==TARGET.resolve(),'Refusing to remove an unexpected installation'
        p=subprocess.run(f'"{exe}" /x {PRODUCT} /qn /norestart /L*v "{ROOT/"verification/avalonia-uninstall.log"}"',timeout=60)
        report['uninstall_exit']=p.returncode
    report['result']='FAIL' if 'error' in report else 'PASS'
    (ROOT/'verification/avalonia-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    if 'error' in report:raise SystemExit(1)
