"""Populate the curated official product image catalog; never run at app startup."""
from pathlib import Path
import json,urllib.request,gzip
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]/'ui/assets/models'
manifest=json.loads((ROOT/'manifest.json').read_text('utf-8'))
def fetch(item):
 identifier,record=item;path=ROOT/record['file']
 if path.exists() and path.read_bytes().startswith(b'\x89PNG'):return identifier,'cached'
 req=urllib.request.Request(record['url'],headers={'User-Agent':'Mozilla/5.0','Referer':record['source']})
 try:
  data=urllib.request.urlopen(req,timeout=20).read()
  if data[:2]==b'\x1f\x8b':data=gzip.decompress(data)
  if not data.startswith(b'\x89PNG'):raise ValueError('not PNG')
  path.write_bytes(data);return identifier,len(data)
 except Exception as e:return identifier,str(e)
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=5) as pool:
  for item in pool.map(fetch,manifest.items()):print(*item,flush=True)
