"""Prepare an app-local Tk runtime from official Python packages; no system install."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='3.13.17'
CACHE=ROOT/'.tools/python-tk-packages';RUNTIME=ROOT/'.tools/tk-runtime'


def prepare():
    CACHE.mkdir(parents=True,exist_ok=True)
    for name in ('tcltk.msi',):
        path=CACHE/name
        if not path.exists():
            with urllib.request.urlopen(f'https://www.python.org/ftp/python/{VERSION}/amd64/{name}',timeout=45) as response:
                path.write_bytes(response.read())
    # Administrative extraction copies files to a workspace directory only.
    extracted=CACHE/'extracted'
    if not extracted.exists():
        msi=CACHE/'tcltk.msi'
        import msilib
        database=msilib.OpenDatabase(str(msi),msilib.MSIDBOPEN_READONLY)
        query=database.OpenView('SELECT `Action` FROM `AdminExecuteSequence`');query.Execute(None)
        actions=[]
        while (row:=query.Fetch()) is not None:actions.append(row.GetString(1))
        query.Close()
        assert set(actions)<={'LaunchConditions','CostInitialize','FileCost','CostFinalize','InstallValidate',
            'InstallInitialize','InstallAdminPackage','AdminExecuteSequence','InstallFiles','InstallFinalize','AdminInitialize'},actions
        exe=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
        p=subprocess.run(f'"{exe}" /a "{msi}" /qn TARGETDIR="{extracted}" /L*v "{CACHE/"extract.log"}"',timeout=60)
        assert p.returncode in (0,3010),p.returncode
    if not RUNTIME.exists():
        with zipfile.ZipFile(ROOT/f'.tools/python-{VERSION}-embed-amd64.zip') as z:z.extractall(RUNTIME)
    for name in ('_tkinter.pyd','tcl86t.dll','tk86t.dll','zlib1.dll'):
        source=next(extracted.rglob(name))
        shutil.copy2(source,RUNTIME/name)
    library=next(extracted.rglob('tkinter/__init__.py'),None)
    if library is None:
        # Python's source archive provides the pure-Python wrapper, not native code.
        import tarfile
        source=CACHE/f'Python-{VERSION}.tar.xz'
        if not source.exists():
            with urllib.request.urlopen(f'https://www.python.org/ftp/python/{VERSION}/Python-{VERSION}.tar.xz',timeout=60) as response:
                source.write_bytes(response.read())
        with tarfile.open(source) as archive:
            prefix=f'Python-{VERSION}/Lib/tkinter/'
            for entry in archive.getmembers():
                if entry.isfile() and entry.name.startswith(prefix) and '..' not in Path(entry.name).parts:
                    path=RUNTIME/'Lib/tkinter'/entry.name[len(prefix):]
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(archive.extractfile(entry).read())
    else:shutil.copytree(library.parent,RUNTIME/'Lib/tkinter',dirs_exist_ok=True)
    tcl=next(extracted.rglob('init.tcl')).parent
    tk=next(extracted.rglob('tk.tcl')).parent
    for directory in (tcl,tk):shutil.copytree(directory,RUNTIME/'tcl'/directory.name,dirs_exist_ok=True)
    (RUNTIME/'python313._pth').write_text('python313.zip\n.\nLib\nLib/site-packages\n','ascii')
    with urllib.request.urlopen('https://pypi.org/pypi/sv-ttk/json',timeout=30) as response:metadata=json.load(response)
    package=next(item for item in metadata['urls'] if item['filename'].endswith('py3-none-any.whl'))
    wheel=CACHE/package['filename']
    if not wheel.exists():
        with urllib.request.urlopen(package['url'],timeout=45) as response:wheel.write_bytes(response.read())
    assert hashlib.sha256(wheel.read_bytes()).hexdigest()==package['digests']['sha256']
    with zipfile.ZipFile(wheel) as archive:archive.extractall(RUNTIME/'Lib/site-packages')
    (CACHE/'provenance.json').write_text(json.dumps({'python':VERSION,'sv_ttk':metadata['info']['version'],
        'wheel_sha256':package['digests']['sha256'],
        'native_sha256':{name:hashlib.sha256((RUNTIME/name).read_bytes()).hexdigest() for name in ('_tkinter.pyd','tcl86t.dll','tk86t.dll')}},indent=2),'utf-8')
    print(json.dumps({'runtime':str(RUNTIME),'theme':metadata['info']['version']}),flush=True)
    return RUNTIME

if __name__=='__main__':prepare()
