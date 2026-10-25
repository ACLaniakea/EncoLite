"""Build the current Qt client, source archive, MSI and portable ZIP."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
from package_qt import ROOT,VERSION,package
OUTPUT=ROOT/'release'


def source_archive():
    output=OUTPUT/f'EncoLite-{VERSION}-source.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for folder in ('encolite','ui','tests','tools','docs'):
            for path in sorted((ROOT/folder).rglob('*')):
                relative=path.relative_to(ROOT)
                if path.is_file() and not set(relative.parts)&{'__pycache__','bin','obj','thumbs'} and path.suffix!='.pyc' and path.name not in ('tk_desktop.py','window_capture.py'):
                    archive.write(path,Path('EncoLite')/relative)
        for name in ('main.py','desktop_entry.py','qt_entry.py','requirements.txt','README.md','LICENSE','THIRD_PARTY_NOTICES.md','launch.cmd'):
            archive.write(ROOT/name,Path('EncoLite')/name)
    return output


def build():
    from prepare_icon import prepare
    prepare(ROOT)
    bundle=package();OUTPUT.mkdir(exist_ok=True)
    source=source_archive();sources=bundle/'Source';sources.mkdir()
    shutil.copy2(source,sources/source.name)
    msi=OUTPUT/f'EncoLite-{VERSION}-win-x64.msi'
    subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py'),'--bundle',str(bundle),
        '--output',str(msi),'--version',VERSION,'--msi-version','0.5.14'],check=True)
    # Optional historical EXE wrapper: it is blocked by application control here.
    # MSI and portable are the supported production outputs.
    if '--with-exe' in sys.argv:
        notes=ROOT/'docs/INSTALL-NOTES.txt'
        subprocess.run([str(ROOT/'.tools/InnoSetup/ISCC.exe'),'/Qp',
            f'/DReleaseVersion={VERSION}',f'/DArtifactsFolder={OUTPUT}','/DFileVersion=0.4.0.2',
            '/DNativeDesktopRuntime',f'/DInstallNotes={notes}',str(ROOT/'tools/installer.iss')],check=True)
    portable=OUTPUT/f'EncoLite-{VERSION}-win-x64-portable.zip'
    with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():archive.write(path,Path('EncoLite')/path.relative_to(bundle))
    entries=[]
    outputs=[source,msi,portable]
    if '--with-exe' in sys.argv:outputs.append(OUTPUT/f'EncoLite-{VERSION}-win-x64-setup.exe')
    for path in outputs:
        entries.append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUTPUT/'SHA256SUMS.txt').write_text(''.join(f"{entry['sha256']}  {entry['file']}\n" for entry in entries),'utf-8')
    (OUTPUT/'build-manifest.json').write_text(json.dumps({'version':VERSION,
        'status':'installation verification pending','runtime':json.loads((bundle/'runtime-manifest.json').read_text('utf-8')),
        'files':entries},indent=2),'utf-8')
    print(json.dumps(entries),flush=True)

if __name__=='__main__':build()
