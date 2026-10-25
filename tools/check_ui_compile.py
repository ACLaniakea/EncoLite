from pathlib import Path
import sys,os
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'.build-deps')]
os.environ['SLINT_BACKEND']='headless-software'
import slint
for name in ('app','quick','notice'):
 try:slint.load_file(root/f'ui/{name}.slint');print('PASS',name,flush=True)
 except Exception as error:
  print('FAIL',name,repr(error),flush=True)
  for attr in ('diagnostics','errors','args'):
   print(attr,getattr(error,attr,None),flush=True)
  for d in getattr(error,'diagnostics',[]):
   print('diagnostic',str(d),[(a,getattr(d,a)) for a in ('message','line_number','column_number') if hasattr(d,a)],flush=True)
