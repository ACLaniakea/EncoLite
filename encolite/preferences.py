"""Small, merged preferences and validated window placement."""
import json
import os
from pathlib import Path


def data_directory():
    portable=os.environ.get('ENCOLITE_DATA_DIR')
    return Path(portable) if portable else Path(os.environ.get('APPDATA',Path.home()/'.config'))/'EncoLite'


def image_directory():
    portable=os.environ.get('ENCOLITE_DATA_DIR')
    return Path(portable)/'images' if portable else Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'EncoLite/images'

def read_preferences(path):
    if not path:return {}
    try:
        value=json.loads(path.read_text('utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}

def write_preferences(path,data):
    if not path:return
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    temporary.replace(path)

def window_state(value):
    if not isinstance(value,dict):return None,0
    page=value.get('page',0)
    page=page if type(page) is int and 0<=page<=6 else 0
    bounds=value.get('bounds')
    if not isinstance(bounds,list) or len(bounds)!=5:return None,page
    x,y,w,h,maximized=bounds
    if (any(type(n) is not int for n in (x,y,w,h)) or not isinstance(maximized,bool)
            or abs(x)>200000 or abs(y)>200000 or not 320<=w<=30000 or not 240<=h<=30000):
        return None,page
    return tuple(bounds),page

def fit_bounds(bounds,work):
    x,y,width,height,maximized=bounds
    left,top,right,bottom=work
    width=min(width,max(1,right-left));height=min(height,max(1,bottom-top))
    return (max(left,min(x,right-width)),max(top,min(y,bottom-height)),width,height,maximized)
