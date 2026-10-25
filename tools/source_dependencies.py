"""Collect exact Rust crate source archives for GPL corresponding-source delivery."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]

def collect(metadata,cache):
    data=json.loads(Path(metadata).read_text('utf-8'))
    used={n['id'] for n in data['resolve']['nodes']}
    dest=ROOT/'.tools/corresponding-source/rust-crates';dest.mkdir(parents=True,exist_ok=True)
    index=[]
    for item in data['packages']:
        if item['id'] not in used or not item['source']:continue
        name=item['name']+'-'+item['version']+'.crate'
        source=next(Path(cache).glob('*/'+name))
        target=dest/name
        shutil.copy2(source,target)
        index.append({'crate':item['name'],'version':item['version'],'file':name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'license':item['license']})
    (dest.parent/'rust-crates.json').write_text(json.dumps(index,indent=2),'utf-8')
    print('Collected',len(index),'crate sources',flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('metadata',type=Path);p.add_argument('cache',type=Path)
    a=p.parse_args();collect(a.metadata,a.cache)
