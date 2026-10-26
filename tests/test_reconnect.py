"""Background reconnect, native ACL decoding and manual disconnect regressions."""
import ctypes as C
import sys
import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import patch

from encolite.bluetooth_notifications import BroadcastHandle, HCI_EVENT, decode_hci_event
from encolite.controller import Controller
from encolite.live_session import LiveSession
from encolite.notifications import ConnectionNoticePolicy
from encolite.presentation import JsonPresentation


class Timer:
    running=False
    def start(self,seconds,callback,repeat=False):
        self.running=True;self.seconds=seconds;self.callback=callback
    def stop(self):self.running=False
    def fire(self):
        self.running=False;self.callback()


class Executor:
    def __init__(self):self.queue=[]
    def submit(self,callback):
        future=Future();self.queue.append((callback,future));return future
    def complete(self):
        callback,future=self.queue.pop(0)
        try:future.set_result(callback())
        except Exception as error:future.set_exception(error)
    def shutdown(self,**kwargs):pass


def device(connected=True):
    return SimpleNamespace(address=123,name='OPPO Enco X3',connected=connected)


class ReconnectTests(unittest.TestCase):
    def controller(self):
        pending=[]
        session=LiveSession()
        controller=Controller(session=session,presentation=JsonPresentation(),
            scheduler=SimpleNamespace(timer=Timer),dispatch=pending.append)
        controller._executor.shutdown(wait=False)
        controller._executor=Executor()
        controller._retry_timer=Timer()
        controller.devices=[device(False)];controller.device_index=0;controller.want_connection=True
        controller._bluetooth_connected={123:False}
        session.on_changed=controller._changed_from_worker
        self.addCleanup(controller.close)
        return controller,session,pending

    def drain(self,pending):
        while pending:pending.pop(0)()

    def test_acl_wakes_offline_backoff_without_any_window(self):
        c,s,pending=self.controller();policy=ConnectionNoticePolicy();notices=[]
        c.on_changed=lambda:notices.append(1) if policy.observe(s.ready,s._generation,busy=c.busy) else None
        def connect(*args,**kwargs):
            s.connected=s.ready=True;s._generation+=1;s._changed()
        s.connect=connect
        c._retry_delay=60;c._schedule_reconnect();self.assertEqual(c._retry_timer.seconds,60)
        c.bluetooth_changed(123,True)
        self.assertEqual(c._retry_timer.seconds,.25)
        c._retry_timer.fire();c._executor.complete();self.drain(pending)
        self.assertEqual(c.windows,[]);self.assertEqual(notices,[1])
        c.sync();self.assertEqual(notices,[1])

    def test_hint_during_failed_attempt_is_consumed_after_completion(self):
        c,s,pending=self.controller()
        s.connect=lambda *args,**kwargs:(_ for _ in ()).throw(ConnectionError('offline'))
        c.connect_selected();c.bluetooth_changed(123,True)
        self.assertTrue(c._connection_hint)
        c._executor.complete();self.drain(pending)
        self.assertFalse(c.busy or c._connection_hint)
        self.assertEqual(c._retry_timer.seconds,.25)

    def test_retry_due_during_another_operation_is_rearmed_after_completion(self):
        c,s,pending=self.controller()
        c.perform(lambda:None,'scan finished')
        c._retry_timer.start(2,c.connect_selected);c._retry_timer.fire()
        self.assertFalse(c._retry_timer.running)
        c._executor.complete();self.drain(pending)
        self.assertTrue(c._retry_timer.running)

    def test_manual_disconnect_and_unrelated_devices_do_not_wake(self):
        c,s,_=self.controller()
        c.bluetooth_changed(999,True);self.assertFalse(c._retry_timer.running)
        c.want_connection=False;c.bluetooth_changed(123,True)
        self.assertFalse(c._retry_timer.running or c._connection_hint)

    def test_acl_disconnect_invalidates_ready_stream_without_gui_or_join(self):
        c,s,pending=self.controller();s.connected=s.ready=True
        closed=[];s.channel=SimpleNamespace(close=lambda:closed.append(True))
        c.bluetooth_changed(123,False);self.drain(pending)
        self.assertFalse(s.connected or s.ready);self.assertTrue(s.cancel.is_set())
        self.assertEqual(closed,[True]);self.assertTrue(c._retry_timer.running)
        s.channel=None

    def test_fallback_finds_reconnection_and_first_paired_device(self):
        for empty in (False,True):
            with self.subTest(empty=empty):
                c,s,pending=self.controller()
                if empty:c.devices=[];c.device_index=-1
                discovery=SimpleNamespace(discover=lambda:[device()])
                with patch.dict(sys.modules,{'encolite.bluetooth_windows':discovery}):
                    c.check_devices();c.check_devices()
                self.assertEqual(len(c._executor.queue),1)
                c._executor.complete();self.drain(pending)
                self.assertEqual(c.device_index,0);self.assertEqual(c._retry_timer.seconds,.25)

    def test_fallback_is_idle_after_manual_disconnect_or_during_work(self):
        c,s,_=self.controller()
        for name in ('busy','_refreshing','_checking_devices'):
            setattr(c,name,True);c.check_devices();setattr(c,name,False)
        c.want_connection=False;c.check_devices()
        c.want_connection=True;s.connected=True;c.check_devices()
        self.assertEqual(c._executor.queue,[])

    def test_hint_during_background_read_survives_until_read_completion(self):
        c,s,pending=self.controller();s.connected=s.ready=True
        reads=[];s.refresh_due=lambda *args,**kwargs:reads.append(kwargs.get('force'))
        c.refresh_background();c.bluetooth_changed(123,True)
        self.assertTrue(c._connection_hint)
        c._executor.complete();self.drain(pending)
        self.assertFalse(c._connection_hint)
        self.assertEqual(len(c._executor.queue),1)
        c._executor.complete();self.drain(pending)
        self.assertEqual(reads,[False,True])

    def test_connect_without_a_paired_device_preserves_connection_intent(self):
        c,s,pending=self.controller();c.devices=[];c.device_index=-1;c.want_connection=False
        with patch.object(sys,'platform','win32'),patch.dict(sys.modules,{'encolite.bluetooth_windows':SimpleNamespace(discover=lambda:[])}):
            c.connect_selected();c._executor.complete();self.drain(pending)
        self.assertTrue(c.want_connection)

    def test_start_keeps_watching_when_no_device_is_paired(self):
        c,s,pending=self.controller();c.devices=[];c.device_index=-1;c.want_connection=False
        with patch.object(sys,'platform','win32'),patch.dict(sys.modules,{'encolite.bluetooth_windows':SimpleNamespace(discover=lambda:[])}):
            c.start();c._executor.complete();self.drain(pending)
        self.assertTrue(c.want_connection and c._device_timer.running)
        self.assertFalse(c._retry_timer.running)
        self.assertEqual(c.devices,[])


class NativeEventTests(unittest.TestCase):
    def packet(self,connection_type=1,connected=1):
        offset=BroadcastHandle.data.offset
        record=BroadcastHandle(size=offset+16,kind=6,guid=(C.c_ubyte*16).from_buffer_copy(HCI_EVENT))
        return bytes(record)[:offset]+(123).to_bytes(8,'little')+bytes((connection_type,connected))+bytes(6)

    def test_hci_acl_connect_and_disconnect(self):
        self.assertEqual(decode_hci_event(self.packet()),(123,True))
        self.assertEqual(decode_hci_event(self.packet(connected=0)),(123,False))

    def test_unrelated_and_truncated_native_packets_are_ignored(self):
        for data in (b'',self.packet()[:-1],self.packet(2),self.packet(3)):
            self.assertIsNone(decode_hci_event(data))
        record=bytearray(self.packet());record[BroadcastHandle.guid.offset]=0
        self.assertIsNone(decode_hci_event(record))


if __name__=='__main__':unittest.main()
