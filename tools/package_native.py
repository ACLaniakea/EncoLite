"""Package a statically linked Slint EXE and unmodified official Python runtime."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
PYTHON_VERSION='3.13.17'
PYTHON_SHA256='9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
SLINT_VERSION='1.18.0b1'
DEST=ROOT/'dist/EncoLite'

def package(executable):
    archive=ROOT/f'.tools/python-{PYTHON_VERSION}-embed-amd64.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==PYTHON_SHA256,'Unexpected Python archive'
    if DEST.exists():shutil.rmtree(DEST)
    runtime=DEST/'runtime';runtime.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:z.extractall(runtime)
    # The loader finds the Python DLL next to EncoLite.exe; stdlib stays private.
    
    for name in ('python313.dll','vcruntime140.dll','vcruntime140_1.dll'):
        shutil.move(runtime/name,DEST/name)
    for name in ('python.exe','pythonw.exe'):
        (runtime/name).unlink()
    (DEST/'python313._pth').write_text('runtime/python313.zip\nruntime\n.\n','ascii')
    shutil.copy2(executable,DEST/'EncoLite.exe')
    app=DEST/'app';app.mkdir()
    ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo')
    for name in ('encolite','ui'):shutil.copytree(ROOT/name,app/name,ignore=ignore)
    shutil.copy2(ROOT/'main.py',app/'main.py')
    deps=app/'.build-deps';deps.mkdir()
    for name in ('slint',f'slint-{SLINT_VERSION}.dist-info'):
        shutil.copytree(ROOT/'.tools/native-python-packages'/name,deps/name,ignore=ignore)
    (deps/'slint/slint.pyd').unlink(missing_ok=True)
    glue=deps/'slint/_native.py'
    original=glue.read_text('utf-8')
    assert 'def _load_native() -> ModuleType:' in original
    glue.write_text(original.replace('import importlib\n','import importlib\nimport sys\n').replace(
        'def _load_native() -> ModuleType:',
        'def _load_native() -> ModuleType:\n    # Enco Lite: binding compiled into the executable.\n    if "_encolite_slint" in sys.builtin_module_names:\n        return importlib.import_module("_encolite_slint")'),'utf-8')
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md'):shutil.copy2(ROOT/name,DEST/name)
    shutil.copytree(ROOT/'docs',DEST/'docs')
    licenses=DEST/'licenses';licenses.mkdir()
    shutil.copy2(runtime/'LICENSE.txt',licenses/'Python.txt')
    binaries={str(p.relative_to(DEST)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in DEST.rglob('*') if p.suffix.lower() in ('.exe','.dll','.pyd')}
    manifest={'python':PYTHON_VERSION,'python_archive_sha256':PYTHON_SHA256,'slint':SLINT_VERSION,
              'binding':'statically linked into EncoLite.exe; no external slint.pyd',
              'binary_sha256':binaries}
    (DEST/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    print('Packaged:',DEST,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('executable',type=Path)
    package(parser.parse_args().executable)
