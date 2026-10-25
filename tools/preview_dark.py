"""Render our Slint component with the dark palette; no desktop capture."""
from pathlib import Path
import sys,os
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
os.environ.setdefault('SLINT_BACKEND','headless-software')
import slint
from slint._native import native
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.desktop import Desktop
controller=Controller(session=DemoSession(),dispatch=native.invoke_from_event_loop)
controller.dark=True
desktop=Desktop(ROOT,controller,tray_enabled=False)
if '--quick' in sys.argv:desktop.show_quick()
else:desktop.show_main()
try:native.run_event_loop()
finally:controller.close();desktop.close()
