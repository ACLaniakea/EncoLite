"""Entry copied to the root of an application-local Python distribution."""
from pathlib import Path
import os,runpy,sys

ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
os.environ['ENCOLITE_DATA_DIR']=str(ROOT/'Data')
sys.path.insert(0,str(ROOT/'app'))
try:
    runpy.run_path(str(ROOT/'app/main.py'),run_name='__main__')
except Exception:
    if sys.stderr is None:
        import traceback,ctypes
        log=ROOT/'Data/startup-error.log'
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text(traceback.format_exc(),encoding='utf-8')
        if '--smoke-test' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None,f'Enco Lite could not start.\n{log}','Enco Lite',0x10)
    raise
