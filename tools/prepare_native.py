"""Obtain pinned upstream sources and apply the small static-embedding changes."""
from pathlib import Path
import hashlib,json,tarfile,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
SLINT='1.18.0b1'
SOURCE_URL='https://files.pythonhosted.org/packages/af/61/d474ce252f59026a9a79e131083357b54c405dcb8c6930682689109484e5/slint-1.18.0b1.tar.gz'
SOURCE_SHA='e57d6f3c52f0d02c67885d2e1fa443fc19c6359446bbb2b7de641cbd888f4c3e'
PYTHON_URL='https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip'
PYTHON_SHA='9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
WHEEL_URL='https://files.pythonhosted.org/packages/4b/0d/ae97ac831eaa14bfba30aeae93c360ea3dc72829fff8ecea77bc4ed50268/slint-1.18.0b1-cp311-abi3-win_amd64.whl'
WHEEL_SHA='f6b46a3854d4a0e2db7f4298c3289703ae091f47fdb12c649bd439a5e5db4f1d'

def obtain(name,url,expected):
    path=ROOT/'.tools'/name
    path.parent.mkdir(exist_ok=True)
    bundled=ROOT/'third-party'/name
    if not path.exists() and bundled.exists():path.write_bytes(bundled.read_bytes())
    if not path.exists():
        with urllib.request.urlopen(url,timeout=90) as stream:data=stream.read()
        assert hashlib.sha256(data).hexdigest()==expected,'Upstream download hash mismatch'
        path.write_bytes(data)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,name+' hash mismatch'
    return path

def prepare():
    archive=obtain(f'slint-{SLINT}.tar.gz',SOURCE_URL,SOURCE_SHA)
    source=ROOT/'.tools/slint-source'/f'slint-{SLINT}'
    if not source.exists():
        with tarfile.open(archive) as t:t.extractall(source.parent,filter='data')
    cargo=source/'api/python/slint/Cargo.toml'
    text=cargo.read_text('utf-8').replace('crate-type = ["cdylib", "rlib"]','crate-type = ["rlib"]')
    text=text.replace('"extension-module", ','').replace(', "abi3-py311"','')
    text=text.replace('"backend-default", "renderer-femtovg", "renderer-software"','"backend-winit", "renderer-software"')
    cargo.write_text(text,'utf-8')
    library=source/'api/python/slint/lib.rs'
    text=library.read_text('utf-8').replace('#[pymodule]\nfn slint(', '#[pymodule(name = "_encolite_slint")]\nfn slint(')
    if 'pub fn register_embedded_module()' not in text:
        text+='\n// Enco Lite: register the statically linked module before Python initialization.\npub fn register_embedded_module() { pyo3::append_to_inittab!(slint); }\n'
    library.write_text(text,'utf-8')
    obtain('python-3.13.17-embed-amd64.zip',PYTHON_URL,PYTHON_SHA)
    wheel=obtain(f'slint-{SLINT}-cp311-abi3-win_amd64.whl',WHEEL_URL,WHEEL_SHA)
    deps=ROOT/'.tools/native-python-packages';deps.mkdir(exist_ok=True)
    with zipfile.ZipFile(wheel) as z:
        for name in z.namelist():
            if not name.endswith('.pyd'):z.extract(name,deps)
    print('Prepared pinned Slint source, Python runtime and Python binding glue',flush=True)
    return source

if __name__=='__main__':prepare()
