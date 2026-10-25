"""Extract the Microsoft-signed WebView2 loader from its official SDK package."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='1.0.4258.31'
def prepare():
    folder=ROOT/'.tools/webview2';folder.mkdir(parents=True,exist_ok=True)
    archive=folder/f'microsoft.web.webview2.{VERSION}.nupkg'
    if not archive.exists():
        url=f'https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/{VERSION}/microsoft.web.webview2.{VERSION}.nupkg'
        with urllib.request.urlopen(url,timeout=60) as response:archive.write_bytes(response.read())
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name in ('build/native/x64/WebView2Loader.dll','build/native/include/WebView2.h') or name.lower().endswith(('license.txt','license.md')):
                (folder/Path(name).name).write_bytes(z.read(name))
    assert (folder/'WebView2Loader.dll').exists()
    (folder/'provenance.json').write_text(json.dumps({'sdk':VERSION,'package_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2),'utf-8')
    print(str(folder),flush=True)
if __name__=='__main__':prepare()
