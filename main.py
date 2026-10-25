"""Enco Lite: native tray and on-demand Qt Quick windows."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from desktop_entry import run as main
if __name__=="__main__":main()
