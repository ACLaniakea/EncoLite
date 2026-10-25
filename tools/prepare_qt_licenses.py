"""Preserve Qt's original open-source license texts and source locations."""
from pathlib import Path
import json,urllib.request
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.tools/qt-probe/licenses';OUT.mkdir(parents=True,exist_ok=True)
sources=[]
for repo in ('qtbase','qtdeclarative','qtsvg','pyside-setup'):
    org='pyside' if repo=='pyside-setup' else 'qt'
    url=f'https://api.github.com/repos/{org}/{repo}/contents/LICENSES?ref=v6.12.0'
    request=urllib.request.Request(url,headers={'User-Agent':'EncoLite-source-notices'})
    entries=json.loads(urllib.request.urlopen(request,timeout=30).read())
    folder=OUT/repo;folder.mkdir(exist_ok=True)
    for entry in entries:
        if entry['type']=='file':
            target=folder/entry['name']
            if not target.exists():target.write_bytes(urllib.request.urlopen(entry['download_url'],timeout=30).read())
    sources.append({'module':repo,'source':f'https://github.com/{org}/{repo}/tree/v6.12.0','source_archive':f'https://github.com/{org}/{repo}/archive/refs/tags/v6.12.0.tar.gz'})
    print(repo,'license notices saved',flush=True)
(OUT/'SOURCES.json').write_text(json.dumps(sources,indent=2),'utf-8')
(OUT/'README.txt').write_text('Qt, PySide6 and Shiboken6 6.12.0 are unmodified dynamic libraries.\nThe official wheels declare LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only.\nThe application uses the open-source licensing options. Compatible replacement libraries may be used.\nUpstream license texts are preserved per module; source locations are in SOURCES.json.\nQt third-party license notices are retained here.\n','utf-8')
