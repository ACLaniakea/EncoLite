"""Offscreen-only notification layout fixture, never a desktop notification."""
from pathlib import Path
import sys,os
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-deps')]
import slint
from slint._native import native
window=slint.load_file(ROOT/'ui/notice.slint',style='fluent').ConnectionNotice()
window.model_name='OPPO Enco X3'
window.battery_text='左耳 50% · 右耳 50%'
window.product_picture=slint.Image.load_from_path(ROOT/'ui/assets/models/067410.png')
window.dark='--dark' in sys.argv
window.dismiss=native.quit_event_loop
window.show()
try:native.run_event_loop()
finally:window.hide()
