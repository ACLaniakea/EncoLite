"""Package unmodified CPython and the required Qt Quick dependency closure."""
from pathlib import Path
import hashlib,json,shutil,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.build-deps'))
import pefile
DEST=ROOT/'dist/EncoLite-qt'
VERSION='0.5.0-preview.15'
PYTHON_VERSION='3.13.17'
PYTHON_SHA256='9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
QT_VERSION='6.12.0'

def package():
    archive=ROOT/f'.tools/python-{PYTHON_VERSION}-embed-amd64.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==PYTHON_SHA256
    source=ROOT/'.tools/qt-probe/packages';qt=source/'PySide6'
    assert (qt/'QtCore.pyd').exists(),'Prepare the official Qt wheels first'
    if DEST.exists():shutil.rmtree(DEST)
    python=DEST/'python';python.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:z.extractall(python)
    ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo','*.pdb')
    shutil.copytree(ROOT/'encolite',DEST/'encolite',ignore=ignore)
    for name in ('desktop.py','tk_desktop.py','window_capture.py','web_desktop.py','webview_native.py'):
        (DEST/'encolite'/name).unlink(missing_ok=True)
    shutil.copytree(ROOT/'ui/assets',DEST/'ui/assets',ignore=ignore)
    shutil.rmtree(DEST/'ui/assets/thumbs',ignore_errors=True)
    shutil.copytree(ROOT/'ui/qt',DEST/'ui/qt',ignore=ignore)
    for name in ('desktop_entry.py','qt_entry.py','README.md','LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,DEST/name)
    shutil.copytree(ROOT/'docs',DEST/'docs')
    out=DEST/'qt/PySide6';out.mkdir(parents=True)
    for path in qt.glob('*.py'):shutil.copy2(path,out/path.name)
    shutil.copytree(qt/'support',out/'support',ignore=ignore)
    for name in ('QtCore','QtGui','QtNetwork','QtQml','QtOpenGL','QtQuick','QtQuickControls2'):
        shutil.copy2(qt/(name+'.pyd'),out/(name+'.pyd'))
    for path in source.glob('*.dist-info'):shutil.copytree(path,DEST/'qt'/path.name,ignore=ignore)
    shutil.copytree(source/'shiboken6',DEST/'qt/shiboken6',ignore=ignore)
    qml=qt/'qml';qmlout=out/'qml'
    for name in ('QtQml','QtQuick/Window','QtQuick/Layouts','QtQuick/Templates','QtQuick/Controls/Basic','QtQuick/Controls/impl'):
        shutil.copytree(qml/name,qmlout/name,ignore=ignore)
    for name in ('QtQuick','QtQuick/Controls'):
        folder=qmlout/name;folder.mkdir(exist_ok=True,parents=True)
        for path in (qml/name).iterdir():
            if path.is_file():shutil.copy2(path,folder/path.name)
    plugins=out/'plugins';(plugins/'platforms').mkdir(parents=True)
    shutil.copy2(qt/'plugins/platforms/qwindows.dll',plugins/'platforms/qwindows.dll')
    for name in ('imageformats','iconengines'):shutil.copytree(qt/'plugins'/name,plugins/name)
    if (qt/'resources').exists():shutil.copytree(qt/'resources',out/'resources')
    available={path.name.lower():path for path in qt.glob('*.dll')}
    queue=[p for p in (DEST/'qt').rglob('*') if p.suffix.lower() in ('.pyd','.dll')];seen=set()
    while queue:
        path=queue.pop()
        if path in seen:continue
        seen.add(path);pe=pefile.PE(str(path),fast_load=True);pe.parse_data_directories(directories=[1,13])
        for entry in list(getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]))+list(getattr(pe,'DIRECTORY_ENTRY_DELAY_IMPORT',[])):
            name=entry.dll.decode('ascii').lower()
            if name in available:
                target=out/available[name].name
                if not target.exists():shutil.copy2(available[name],target);queue.append(target)
        pe.close()
    licenses=DEST/'licenses';licenses.mkdir();shutil.copy2(python/'LICENSE.txt',licenses/'Python.txt')
    cached=ROOT/'.tools/qt-probe/licenses'
    if not (cached/'SOURCES.json').exists():raise RuntimeError('Run tools/prepare_qt_licenses.py first')
    shutil.copytree(cached,licenses/'Qt');shutil.copy2(ROOT/'.tools/qt-probe/provenance.json',licenses/'Qt/provenance.json')
    binaries={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob('*') if p.suffix.lower() in ('.dll','.pyd','.exe')}
    manifest={'version':VERSION,'python':PYTHON_VERSION,'qt':QT_VERSION,
        'framework':'Qt Quick / PySide6; custom Basic controls; GUI released by default; optional fast launch retains the GUI process',
        'entry_point':'python/pythonw.exe','entry_arguments':'"[INSTALLDIR]desktop_entry.py"',
        'dependencies':{'PySide6-Essentials':QT_VERSION,'shiboken6':QT_VERSION},
        'webview2_distributed':False,'slint_distributed':False,'binary_sha256':binaries,
        'security_changes':False,'status':'built; validation records are in docs/VALIDATION.md'}
    (DEST/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    for name,args in (('启动 Enco Lite.cmd',''),('快捷控制.cmd',' --quick')):
        (DEST/name).write_bytes(('@echo off\r\nstart "" "%~dp0python\\pythonw.exe" "%~dp0desktop_entry.py"'+args+'\r\n').encode('ascii'))
    assert not list(DEST.rglob('*WebView2*')) and not list(DEST.rglob('*WebEngine*'))
    print(json.dumps({'bundle':str(DEST),'bytes':sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file()),'binaries':len(binaries)}),flush=True)
    return DEST

if __name__=='__main__':package()
