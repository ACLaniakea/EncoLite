"""Prepare the pinned official, project-local Windows embedded Python runtime."""
from pathlib import Path
import hashlib,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='3.13.17'
SHA256='9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'

def prepare():
    folder=ROOT/'.tools';folder.mkdir(exist_ok=True)
    filename=f'python-{VERSION}-embed-amd64.zip';archive=folder/filename
    if not archive.exists():
        temporary=archive.with_suffix('.download')
        try:
            with urllib.request.urlopen(f'https://www.python.org/ftp/python/{VERSION}/{filename}',timeout=60) as response,temporary.open('wb') as target:
                while chunk:=response.read(1024*1024):target.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest()!=SHA256:raise ValueError('Official Python archive hash mismatch')
            temporary.replace(archive)
        finally:temporary.unlink(missing_ok=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise ValueError('Cached Python archive hash mismatch')
    output=folder/filename.removesuffix('.zip')
    if not (output/'pythonw.exe').is_file() or not (output/'python313.dll').is_file():
        with zipfile.ZipFile(archive) as source:
            if not all((output/name).resolve().is_relative_to(output.resolve()) for name in source.namelist()):raise ValueError('Unsafe archive path')
            source.extractall(output)
    print(f'Official Python {VERSION} ready in .tools/{output.name}',flush=True)

if __name__=='__main__':prepare()
