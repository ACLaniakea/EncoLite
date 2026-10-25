"""Package the Slint 1.17 candidate with unmodified official Python binaries.

The application entry is a normal Python script; no custom launcher EXE is built.
This does not change Windows trust, certificate stores, or application control.
"""
from pathlib import Path
import hashlib,json,shutil,zipfile
from compat_ui import backport
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'dist/EncoLite-compat'
VERSION='0.3.0-preview.3'
PYTHON_VERSION='3.13.17'
SLINT_VERSION='1.17.1b2'
PYTHON_SHA256='9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
SLINT_SHA256='68cbb5365a69b28b70e354e98fdc541f6584f3a41be79b336b4b70e8f280db29'

def package():
    python=ROOT/f'.tools/python-{PYTHON_VERSION}-embed-amd64.zip'
    wheel=ROOT/f'.tools/slint-candidates/{SLINT_VERSION}/slint-{SLINT_VERSION}-cp311-abi3-win_amd64.whl'
    for path,digest in ((python,PYTHON_SHA256),(wheel,SLINT_SHA256)):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Unexpected dependency archive: {path.name}')
    if DEST.exists():shutil.rmtree(DEST)
    runtime=DEST/'runtime';runtime.mkdir(parents=True)
    with zipfile.ZipFile(python) as archive:archive.extractall(runtime)
    ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo')
    for name in ('encolite','ui'):shutil.copytree(ROOT/name,DEST/name,ignore=ignore)
    shutil.copy2(ROOT/'main.py',DEST/'main.py')
    with zipfile.ZipFile(wheel) as archive:archive.extractall(DEST/'.build-deps')
    backport(DEST)
    (DEST/'run.py').write_text('''from pathlib import Path
import ctypes,runpy,sys
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
# Do this before Slint creates a window. Keep the PSF binary signatures intact.
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EncoLite.Desktop")
runpy.run_path(str(root/"main.py"),run_name="__main__")
''','utf-8')
    (DEST/'启动 Enco Lite.cmd').write_bytes(b'@echo off\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0run.py" %*\r\n')
    (DEST/'快捷控制.cmd').write_bytes(b'@echo off\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0run.py" --quick\r\n')
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md'):shutil.copy2(ROOT/name,DEST/name)
    shutil.copytree(ROOT/'docs',DEST/'docs')
    binaries={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in DEST.rglob('*') if p.suffix.lower() in ('.exe','.dll','.pyd')}
    manifest={'version':VERSION,'status':'candidate; foreground and real-device verification pending',
        'python':PYTHON_VERSION,'slint':SLINT_VERSION,
        'entry_point':'runtime/pythonw.exe','entry_arguments':'"[INSTALLDIR]run.py"',
        'archives':{python.name:PYTHON_SHA256,wheel.name:SLINT_SHA256},'binary_sha256':binaries,
        'security_changes':False}
    (DEST/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    print(json.dumps({'bundle':str(DEST),'bytes':sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file()),'slint':SLINT_VERSION}),flush=True)
    return DEST

if __name__=='__main__':package()
