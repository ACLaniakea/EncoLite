"""Bundle unmodified application-local CPython, Slint and source into a ZIP."""
from pathlib import Path
import sys,shutil,zipfile,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.3.0-preview.1'
FOLDER='EncoLite-portable'
DEST=ROOT/'dist'/FOLDER
RELEASE=ROOT/'release'

def ignore(path,names):
    return [name for name in names if name=='__pycache__' or name.endswith(('.pyc','.pyo'))]

def build():
    assert sys.platform=='win32','Run with Windows Python 3.12 x64'
    assert sys.version_info[:2]==(3,12)
    if DEST.exists():shutil.rmtree(DEST)
    runtime=DEST/'runtime';runtime.mkdir(parents=True)
    source=Path(sys.base_prefix)
    originals={}
    for name in ('python.exe','pythonw.exe','python3.dll','python312.dll','vcruntime140.dll','vcruntime140_1.dll'):
        path=source/name;shutil.copy2(path,runtime/name)
        originals[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    native=runtime/'DLLs';native.mkdir()
    for path in (source/'DLLs').iterdir():
        if (path.suffix.lower() in ('.pyd','.dll') and not path.name.startswith(('_test','_ctypes_test'))
                and path.name not in ('_tkinter.pyd','tcl86t.dll','tk86t.dll')):
            shutil.copy2(path,native/path.name)
    # Slint's MSVC runtime dependency, kept byte-for-byte as collected by the
    # existing Windows build. No PE edits, signing or trust/policy changes.
    msvcp=ROOT/'dist/EncoLite/_internal/MSVCP140.dll'
    if msvcp.exists():shutil.copy2(msvcp,runtime/msvcp.name)
    excluded={'site-packages','test','tests','ensurepip','idlelib','tkinter','turtledemo','venv','__pycache__'}
    with zipfile.ZipFile(runtime/'python312.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((source/'Lib').rglob('*.py')):
            relative=path.relative_to(source/'Lib')
            if not (set(relative.parts)&excluded) and relative.name!='turtle.py':
                archive.write(path,relative.as_posix())
    (runtime/'python312._pth').write_text('python312.zip\nDLLs\n.\n',encoding='ascii')
    app=DEST/'app';app.mkdir()
    for name in ('encolite','ui','tests','tools','docs'):
        shutil.copytree(ROOT/name,app/name,ignore=ignore)
    for name in ('main.py','requirements.txt','README.md','LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,app/name)
    packages=app/'.build-deps';packages.mkdir()
    for name in ('slint','slint-1.18.1b1.dist-info'):
        shutil.copytree(ROOT/'.build-deps'/name,packages/name,ignore=ignore)
    shutil.copy2(ROOT/'tools/portable_entry.py',DEST/'run.py')
    (DEST/'Data').mkdir()
    shutil.copy2(ROOT/'docs/PORTABLE.txt',DEST/'使用说明.txt')
    licenses=DEST/'licenses';licenses.mkdir()
    shutil.copy2(source/'LICENSE.txt',licenses/'Python.txt')
    shutil.copy2(ROOT/'LICENSE',DEST/'LICENSE')
    shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.md',DEST/'THIRD_PARTY_NOTICES.md')
    for name,args in (('启动 Enco Lite.cmd',''),('快捷控制.cmd','--quick ')):
        (DEST/name).write_bytes(('@echo off\r\nsetlocal\r\n'
            'if not exist "%~dp0runtime\\pythonw.exe" exit /b 1\r\n'
            f'start "" /D "%~dp0" "%~dp0runtime\\pythonw.exe" "%~dp0run.py" {args}%*\r\n').encode('ascii'))
    manifest={'version':VERSION,'python':sys.version.split()[0],'slint':'1.18.1b1',
              'format':'application-local CPython with source','runtime_sha256':originals}
    (DEST/'build-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    RELEASE.mkdir(exist_ok=True)
    target=RELEASE/f'EncoLite-{VERSION}-win-x64-portable.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(DEST.rglob('*')):
            if path.is_file():archive.write(path,Path(FOLDER)/path.relative_to(DEST))
        archive.writestr(FOLDER+'/Data/','')
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (target.with_suffix('.zip.sha256')).write_text(f'{digest}  {target.name}\n','utf-8')
    print(json.dumps({'file':str(target),'bytes':target.stat().st_size,'sha256':digest}),flush=True)

if __name__=='__main__':build()
