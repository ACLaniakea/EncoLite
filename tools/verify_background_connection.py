"""Own native tray/message loop: ACL -> connection notice with no Qt process.

Uses simulated protocol completion, real Win32 registration and messages; never
disconnects Windows Bluetooth or writes a real earbud setting.
"""
from pathlib import Path
import ctypes as C
import json
import sys
import time
import traceback
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
from encolite.bluetooth_notifications import BroadcastHandle,HCI_EVENT
from encolite.controller import Controller
from encolite.live_session import LiveSession
from encolite.native_loop import NativeLoop
from encolite.notifications import ConnectionNoticePolicy
from encolite.presentation import JsonPresentation
from encolite.windows_shell import Tray,api,user

out=ROOT/'verification/qt-background';out.mkdir(parents=True,exist_ok=True)
report={'checks':[],'errors':[],'hardware_writes':False,'scope':'Real Windows Bluetooth radio notification registration, hidden tray window and native message loop; simulated control handshake. No GUI loaded or real Bluetooth reconnect performed.'}
loop=NativeLoop();session=LiveSession()
c=Controller(session=session,presentation=JsonPresentation(),scheduler=loop,dispatch=loop.post)
session.on_changed=c._changed_from_worker
c.devices=[SimpleNamespace(address=123,name='OPPO Enco X3',connected=False)]
c.device_index=0;c.want_connection=True;c._retry_timer=loop.timer();c._retry_delay=60
def connect(device,cancel):
    session.cancel=cancel;session.connected=session.ready=True
    session._generation+=1;session._changed()
session.connect=connect
tray=Tray(ROOT/'ui/assets/app-icon.ico',lambda:None,lambda:None,loop.quit,lambda _:None,
          loop.post,test_mode=True,on_dispatch=loop.drain,on_bluetooth=c.bluetooth_changed)
loop.hwnd=tray.hwnd
policy=ConnectionNoticePolicy();notices=[];times=[];started=time.monotonic()
def changed():
    if policy.observe(session.ready,session._generation,busy=c.busy):
        notices.append(session._generation);times.append(time.monotonic()-started)
c.on_changed=changed
send=api(user,'SendMessageW',C.c_ssize_t,C.c_void_p,C.c_uint,C.c_size_t,C.c_ssize_t)
def event(connected):
    monitor=tray.bluetooth_notifications
    assert monitor.handles,'No Bluetooth radio notification registration succeeded'
    handle,notification=next(iter(monitor.handles.items()))
    offset=BroadcastHandle.data.offset
    record=BroadcastHandle(size=offset+16,kind=6,handle=handle,notification=notification,
                           guid=(C.c_ubyte*16).from_buffer_copy(HCI_EVENT))
    raw=bytes(record)[:offset]+(123).to_bytes(8,'little')+bytes((1,int(connected)))+bytes(6)
    buffer=C.create_string_buffer(raw)
    send(tray.hwnd,0x219,0x8006,C.addressof(buffer))
stage=0
def tick():
    global stage
    try:
        if stage==0 and len(notices)==1:
            assert times[0]<2 and not c.windows,(times,c.windows)
            report['checks'].append('ACL connect cancels a 60-second retry and emits one notice with no graphical window')
            event(False);stage=1
        elif stage==1 and not session.connected:
            report['checks'].append('ACL disconnect clears ready state in the hidden background process')
            event(True);stage=2
        elif stage==2 and len(notices)==2:
            assert notices==[1,2],notices
            report['checks'].append('A subsequent ACL reconnect re-arms exactly one connection notice')
            c.want_connection=False;event(False);event(True);stage=3
        elif stage==3:
            assert notices==[1,2] and not c._connection_hint
            assert not any(name.startswith('PySide6') for name in sys.modules)
            report['checks'].append('Manual disconnect intent is respected and the background path never imports Qt')
            report['radio_registrations']=len(tray.bluetooth_notifications.handles)
            report['notice_times_seconds']=times
            loop.quit()
        if time.monotonic()-started>6:raise TimeoutError((stage,notices,c.status))
    except Exception:
        report['errors'].append(traceback.format_exc());loop.quit()
timer=loop.timer();timer.start(.05,tick,repeat=True)
try:
    c._schedule_reconnect();event(True);loop.run()
finally:
    c.close();tray.close()
    report['result']='FAIL' if report['errors'] else 'PASS'
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
sys.exit(report['result']!='PASS')
