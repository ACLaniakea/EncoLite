"""Probe the official WebView2 loader after MSI installation, with no security changes."""
from pathlib import Path
import ctypes as C, json, os, shutil, subprocess, sys, time, uuid
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.4.0-webview-probe.1'
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
bundle=ROOT/'build/webview-probe';target=ROOT/'.install-test/WebView installed'
output=ROOT/'verification/webview-runtime.json';msi=ROOT/'build/webview-probe.msi'
api=C.WinDLL('msi');api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
exe=str(Path(os.environ['SystemRoot'])/'System32/msiexec.exe')
report={'checks':[],'errors':[],'security_changes':False};installed=False
try:
    product=C.create_unicode_buffer(39)
    assert api.MsiEnumRelatedProductsW(UPGRADE,0,0,product)==259, 'An existing installation must be preserved'
    bundle.mkdir(parents=True,exist_ok=True)
    import zipfile
    with zipfile.ZipFile(ROOT/'.tools/python-3.13.17-embed-amd64.zip') as archive:archive.extractall(bundle/'python')
    (bundle/'encolite').mkdir(exist_ok=True);(bundle/'tools').mkdir(exist_ok=True)
    for name in ('windows_shell.py','native_loop.py','webview_native.py','__init__.py'):
        shutil.copy2(ROOT/'encolite'/name,bundle/'encolite'/name)
    shutil.copy2(ROOT/'tools/probe_webview_host.py',bundle/'tools/probe_webview_host.py')
    shutil.copy2(ROOT/'.tools/webview2/WebView2Loader.dll',bundle/'WebView2Loader.dll')
    command="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-AuthenticodeSignature -LiteralPath '"+str(bundle/'WebView2Loader.dll')+"' | Select-Object Status,@{n='Signer';e={$_.SignerCertificate.Subject}} | ConvertTo-Json"
    signature=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-Command',command],encoding='utf-8'))
    assert signature['Status']==0,signature
    report['loader_signature']=signature
    (bundle/'runtime-manifest.json').write_text(json.dumps({'entry_point':'python/pythonw.exe','entry_arguments':'"[INSTALLDIR]tools\\probe_webview_host.py"'}),'utf-8')
    subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py'),'--bundle',str(bundle),'--output',str(msi),'--version',VERSION,'--msi-version','0.4.1'],check=True,timeout=120)
    p=subprocess.run(f'"{exe}" /i "{msi}" /qn /norestart INSTALLDIR="{target}" /L*v "{ROOT/"verification/webview-probe-install.log"}"',timeout=90)
    assert p.returncode in (0,3010),p.returncode
    installed=True
    for i in range(3):
        result=ROOT/'verification'/f'webview-probe-{i}.json';result.unlink(missing_ok=True)
        with (ROOT/'verification/webview-probe-error.log').open('w') as log:
            p=subprocess.run([str(target/'python/pythonw.exe'),str(target/'tools/probe_webview_host.py'),str(result)],stdout=log,stderr=log,timeout=20)
        assert p.returncode==0 and result.exists(),('installed WebView launch',i,p.returncode)
        assert json.loads(result.read_text('utf-8'))['result']=='PASS'
        report['checks'].append(f'installed WebView2 rendering + UTF-8 IPC launch {i+1}')
        print('PASS',report['checks'][-1],flush=True)
except Exception:report['errors'].append(__import__('traceback').format_exc())
finally:
    if installed:
        p=subprocess.run(f'"{exe}" /x {PRODUCT} /qn /norestart',timeout=90)
        if p.returncode not in (0,3010):report['errors'].append('uninstall '+str(p.returncode))
        else:report['checks'].append('system MSI uninstall')
    report['result']='FAIL' if report['errors'] else 'PASS'
    output.write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)
    if report['errors']:raise SystemExit(1)
