"""State notifications, polling budget and subscription fallback regressions."""
import sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from encolite.live_session import LiveSession,model_for
from encolite.protocol import Frame,Battery


class UpdateTests(unittest.TestCase):
    def session(self):
        s=LiveSession();s.connected=s.ready=True
        s.profile=model_for('067410','');s.bitmap=bytes.fromhex('FF777AEEE68F8E04')
        return s

    def test_partial_charge_event_preserves_other_components_and_clears_missing(self):
        s=self.session();s.battery={'left':Battery(90,False),'right':Battery(80,False),'case':Battery(60,False)}
        s._receive(Frame(0x0204,bytes((1,1,1,0x80|100))),0)
        self.assertEqual(s.battery,{'left':Battery(100,True),'right':Battery(80,False),'case':Battery(60,False)})
        s._receive(Frame(0x8202,bytes((0,1,1,1,100))),0)
        self.assertEqual(s.battery['left'],Battery(100,False))
        s._receive(Frame(0x0204,bytes((1,1,3,0))),0)
        self.assertIsNone(s.battery['case'])
        before=s.battery.copy()
        s._receive(Frame(0x0204,bytes((1,3,1,80))),0)
        self.assertEqual(s.battery,before)

    def test_visible_poll_is_fast_and_tray_only_reads_battery(self):
        s=self.session();commands=[];s.request=lambda command,payload=b'':commands.append(command)
        with patch('encolite.live_session.time.monotonic',return_value=100):
            s.refresh_due(True,now=100)
        self.assertIn(0x0106,commands);self.assertIn(0x010C,commands);self.assertIn(0x0109,commands)
        self.assertIn(0x0122,commands)
        commands.clear()
        with patch('encolite.live_session.time.monotonic',return_value=102):
            s.refresh_due(True,now=102)
        self.assertEqual(commands,[0x0106,0x010C,0x0109])
        commands.clear()
        s.refresh_due(False,now=105);self.assertEqual(commands,[])
        s.refresh_due(False,now=113);self.assertEqual(commands,[0x0106])

    def test_fresh_notifications_skip_redundant_reads(self):
        s=self.session();now=time.monotonic()
        s._last_updates={command:now for command in (0x0106,0x010C,0x0109,0x010F,0x010D,0x012A,0x012B,0x0122,0x0114,0x0112)}
        s.request=lambda *args:self.fail('fresh state was polled again')
        s.refresh_due(True,now=now+1)

    def test_multi_event_arriving_during_read_is_not_erased(self):
        s=self.session();s.dirty.add('multi')
        def request(command,payload=b''):
            if command==0x0112:s.dirty.add('multi')
        s.request=request;s.refresh_due(False)
        self.assertIn('multi',s.dirty)

    def test_batch_subscription_retries_only_failed_events(self):
        s=self.session();calls=[]
        def request(command,payload=b'',**kwargs):
            calls.append((command,payload))
            if command==0x0200:return bytes((0,3,1,2,3))
            if command==0x0205:return bytes((0,3,1,0,2,1,3,0))
            return b'\0'
        s.request=request;s._register_notifications()
        self.assertEqual(s.registered_events,{1,2,3})
        self.assertEqual([payload for command,payload in calls if command==0x0201],[b'\2'])

if __name__=='__main__':unittest.main()
