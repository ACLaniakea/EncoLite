"""Disposable Qt Quick frontend; the tray owns Bluetooth and global shortcuts."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
sys.stderr.reconfigure(encoding='utf-8')
packages = ROOT / 'qt'
if not packages.exists():
    packages = ROOT / '.tools/qt-probe/packages'
sys.path.insert(0, str(packages))
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('EncoLite.Desktop')
from encolite.qt_desktop import Desktop
Desktop(ROOT).run()
