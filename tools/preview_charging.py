"""Offscreen charging edge cases: all cells at 100%, using our own UI only."""
from pathlib import Path
import os,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
os.environ.setdefault('SLINT_BACKEND','headless-software')
from slint._native import native
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.protocol import Battery
from encolite.desktop import Desktop
session=DemoSession();session.battery={key:Battery(100,True) for key in ('left','right','case')}
controller=Controller(session=session,dispatch=native.invoke_from_event_loop)
controller.dark='--dark' in sys.argv
desktop=Desktop(ROOT,controller,tray_enabled=False)
if '--quick' in sys.argv:desktop.show_quick()
else:desktop.show_main()
try:native.run_event_loop()
finally:controller.close();desktop.close()
