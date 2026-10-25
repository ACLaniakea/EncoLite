"""Build the native Windows candidate, full source, MSI and setup wrapper."""
from pathlib import Path
import sys,subprocess,zipfile,hashlib,json,os,shutil
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.3.0-preview.2'

def source_archive():
    output=ROOT/'release';output.mkdir(exist_ok=True)
    target=output/f'EncoLite-{VERSION}-source.zip'
    upstream=ROOT/'.tools/slint-1.18.0b1.tar.gz'
    dependencies=ROOT/'.tools/corresponding-source'
    if not upstream.exists() or not (dependencies/'rust-crates.json').exists():
        raise RuntimeError('Corresponding native dependency sources are required; see docs/BUILD.md')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for folder in ('encolite','ui','tests','tools','docs','native'):
            for path in sorted((ROOT/folder).rglob('*')):
                relative=path.relative_to(ROOT)
                if (path.is_file() and not set(relative.parts)&{'__pycache__','target','.cargo'}
                        and path.suffix not in ('.pyc','.spec')):
                    archive.write(path,Path('EncoLite')/relative)
        for name in ('main.py','requirements.txt','README.md','LICENSE','THIRD_PARTY_NOTICES.md','launch.cmd'):
            archive.write(ROOT/name,Path('EncoLite')/name)
        archive.write(upstream,Path('EncoLite/third-party')/upstream.name,compress_type=zipfile.ZIP_STORED)
        for path in sorted(dependencies.rglob('*')):
            if path.is_file():
                archive.write(path,Path('EncoLite/third-party')/path.relative_to(dependencies),compress_type=zipfile.ZIP_STORED)
    return target

if __name__=='__main__':
    if '--skip-app' not in sys.argv:
        subprocess.run([sys.executable,str(ROOT/'tools/build_windows.py')],check=True)
    bundle=ROOT/'dist/EncoLite'
    assert (bundle/'runtime-manifest.json').exists(),'A native candidate bundle is required'
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,bundle/name)
    shutil.copytree(ROOT/'docs',bundle/'docs',dirs_exist_ok=True)
    source=source_archive()
    sources=bundle/'Source';sources.mkdir(exist_ok=True)
    shutil.copy2(source,sources/source.name)
    subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py')],check=True)
    compiler=Path(os.environ.get('ISCC',ROOT/'.tools/InnoSetup/ISCC.exe'))
    subprocess.run([str(compiler),'/Qp',str(ROOT/'tools/installer.iss')],check=True)
    setup=ROOT/'release'/f'EncoLite-{VERSION}-win-x64-setup.exe'
    msi=ROOT/'release'/f'EncoLite-{VERSION}-win-x64.msi'
    entries=[]
    for path in (setup,msi,source):
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({'file':path.name,'bytes':path.stat().st_size,'sha256':digest})
    (ROOT/'release/SHA256SUMS.txt').write_text(''.join(f"{item['sha256']}  {item['file']}\n" for item in entries),'utf-8')
    (ROOT/'release/build-manifest.json').write_text(json.dumps({'version':VERSION,
        'status':'unsigned candidate; repeat Smart App Control checks currently fail',
        'runtime':json.loads((bundle/'runtime-manifest.json').read_text('utf-8')),
        'files':entries},indent=2),'utf-8')
    print(json.dumps(entries,indent=2),flush=True)
