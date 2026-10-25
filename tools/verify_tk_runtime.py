"""Probe the official Tk binaries after MSI installation, with no security changes."""
from pathlib import Path
import ctypes as C, json, os, shutil, subprocess, sys, time, uuid
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.4.0-tk-probe.1'
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
bundle=ROOT/'build/tk-probe';target=ROOT/'.install-test/Tk installed'
output=ROOT/'verification/tk-runtime.json';msi=ROOT/'build/tk-probe.msi'
api=C.WinDLL('msi');api.MsiEnumRelatedProductsW.argtypes=[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_wchar_p]
exe=str(Path(os.environ['SystemRoot'])/'System32/msiexec.exe')
report={'checks':[],'errors':[],'security_changes':False};installed=False
try:
    product=C.create_unicode_buffer(39)
    assert api.MsiEnumRelatedProductsW(UPGRADE,0,0,product)==259, 'An existing installation must be preserved'
    bundle.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'.tools/tk-runtime',bundle/'runtime',dirs_exist_ok=True)
    powershell="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-ChildItem -LiteralPath '"+str(bundle/'runtime')+"' | Where-Object { $_.Name -in @('_tkinter.pyd','tcl86t.dll','tk86t.dll','zlib1.dll','pythonw.exe') } | Get-AuthenticodeSignature | Select-Object Path,Status,@{n='Signer';e={$_.SignerCertificate.Subject}} | ConvertTo-Json"
    signatures=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-Command',powershell],encoding='utf-8'))
    assert len(signatures)==5 and all(s['Status']==0 for s in signatures),signatures
    report['signatures']=signatures
    print('PASS official Python/Tk signatures',flush=True)
    (bundle/'probe.py').write_text('''from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parent
os.environ['TCL_LIBRARY']=str(root/'runtime/tcl/tcl8.6')
os.environ['TK_LIBRARY']=str(root/'runtime/tcl/tk8.6')
import tkinter as tk
from tkinter import ttk
import sv_ttk
window=tk.Tk();window.title('Enco Lite · runtime check');sv_ttk.set_theme('light')
ttk.Label(window,text='Enco Lite · 耳机控制',font=('Microsoft YaHei UI',16)).pack(padx=30,pady=18)
ttk.Button(window,text='降噪').pack(padx=30,pady=12)
ttk.Checkbutton(window,text='入耳检测').pack(padx=30,pady=12)
window.after(1200,window.destroy);window.mainloop()
Path(sys.argv[1]).write_text(json.dumps({'result':'PASS','tk':tk.TkVersion,'theme':sv_ttk.get_theme()}),'utf-8')
''','utf-8')
    (bundle/'runtime-manifest.json').write_text(json.dumps({'entry_point':'runtime/pythonw.exe','entry_arguments':'"[INSTALLDIR]probe.py"'}),'utf-8')
    subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py'),'--bundle',str(bundle),'--output',str(msi),'--version',VERSION,'--msi-version','0.4.1'],check=True,timeout=120)
    p=subprocess.run(f'"{exe}" /i "{msi}" /qn /norestart INSTALLDIR="{target}" /L*v "{ROOT/"verification/tk-probe-install.log"}"',timeout=90)
    assert p.returncode in (0,3010),p.returncode
    installed=True
    for i in range(3):
        result=ROOT/'verification'/f'tk-probe-{i}.json';result.unlink(missing_ok=True)
        with (ROOT/'verification/tk-probe-error.log').open('w') as log:
            p=subprocess.run([str(target/'runtime/pythonw.exe'),str(target/'probe.py'),str(result)],stdout=log,stderr=log,timeout=20)
        assert p.returncode==0 and result.exists(),('installed Tk launch',i,p.returncode)
        assert json.loads(result.read_text('utf-8'))['result']=='PASS'
        report['checks'].append(f'installed Tk + Sun Valley theme launch {i+1}')
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
