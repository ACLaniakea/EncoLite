"""Compare old Slint loading after Windows Installer file extraction."""
from pathlib import Path
import ctypes as C,json,os,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.tools/old-runtime-msi';BUNDLE=WORK/'bundle'
TARGET=ROOT/'.install-test/old runtime installed'
VERSION='0.3.0-runtime-probe'
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
COMPONENT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),'runtime\\pythonw.exe')).upper()+'}'
VERSIONS=('1.16.1b1','1.14.1b1','1.12.1b1')
api=C.WinDLL('msi')
api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
api.MsiGetComponentPathW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,C.POINTER(C.c_uint32)]
product=C.create_unicode_buffer(39)
assert api.MsiEnumRelatedProductsW(UPGRADE,0,0,product)==259,'Refusing to replace an existing installation'
if BUNDLE.exists():shutil.rmtree(BUNDLE)
BUNDLE.mkdir(parents=True)
shutil.copytree(ROOT/'.tools/python-3.13.17-embed-amd64',BUNDLE/'runtime')
for version in VERSIONS:
    shutil.copytree(ROOT/'.tools/slint-candidates'/version/'package',BUNDLE/'deps'/version,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
(BUNDLE/'probe.py').write_text('''import sys,json
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'/sys.argv[1]))
import slint
print(json.dumps({'result':'PASS','module':slint.native.__file__}),flush=True)
''','utf-8')
(BUNDLE/'runtime-manifest.json').write_text(json.dumps({'entry_point':'runtime/pythonw.exe','entry_arguments':'"[INSTALLDIR]probe.py"'}),'utf-8')
msi=WORK/'runtime-probe.msi'
subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py'),'--bundle',str(BUNDLE),'--output',str(msi),'--version',VERSION,'--msi-version','0.3.4'],check=True)
exe=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
report={'versions':[],'security_changes':False}
def location():
    text=C.create_unicode_buffer(32768);size=C.c_uint32(len(text))
    state=api.MsiGetComponentPathW(PRODUCT,COMPONENT,text,C.byref(size))
    return Path(text.value).parent.parent if state in (3,4) and text.value else None
try:
    command=f'"{exe}" /i "{msi}" /qn /norestart INSTALLDIR="{TARGET}" /L*v "{ROOT/"verification/old-runtime-msi-install.log"}"'
    p=subprocess.run(command,timeout=90);assert p.returncode in (0,3010),p.returncode
    assert location() and location().resolve()==TARGET.resolve()
    for version in VERSIONS:
        p=subprocess.run([str(TARGET/'runtime/python.exe'),str(TARGET/'probe.py'),version],capture_output=True,timeout=25,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        item={'version':version,'exit':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
        report['versions'].append(item);print(json.dumps(item,ensure_ascii=True),flush=True)
finally:
    if location():
        assert location().resolve()==TARGET.resolve(),'Refusing to remove an unexpected installation'
        p=subprocess.run(f'"{exe}" /x {PRODUCT} /qn /norestart /L*v "{ROOT/"verification/old-runtime-msi-uninstall.log"}"',timeout=60)
        report['uninstall_exit']=p.returncode
    (ROOT/'verification/older-slint-msi.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
