"""Build the native Slint host, then bundle signed Python runtime files."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys
from prepare_native import prepare,ROOT
from package_native import package

def build(native_exe=None,target=None):
    prepare()
    if native_exe is None:
        cargo=os.environ.get('CARGO',shutil.which('cargo'))
        if not cargo:raise RuntimeError('Rust is required. See docs/BUILD.md, or supply --native-exe.')
        target=target or ('x86_64-pc-windows-msvc' if sys.platform=='win32' else 'x86_64-pc-windows-gnu')
        env={**os.environ,'PYO3_CROSS':'1','PYO3_CROSS_PYTHON_VERSION':'3.13'}
        subprocess.run([cargo,'build','--locked','--release','--target',target],cwd=ROOT/'native',env=env,check=True)
        folder=Path(os.environ.get('CARGO_TARGET_DIR',ROOT/'native/target'))
        native_exe=folder/target/'release/encolite-native.exe'
    package(Path(native_exe))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--native-exe',type=Path)
    parser.add_argument('--target')
    args=parser.parse_args();build(args.native_exe,args.target)
