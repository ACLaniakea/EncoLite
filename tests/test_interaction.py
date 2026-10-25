import unittest,threading,tempfile,json
from pathlib import Path
from concurrent.futures import Future
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from encolite.notifications import ConnectionNoticePolicy
from encolite.controller import Controller

class Session:
    is_live=True
    def __init__(self):
        self.connected=False;self.noise='off';self.preset=0
        self.noise_modes={};self.presets=[];self.cancel=threading.Event();self.channel=None
        self.error='';self.on_changed=None;self.attempted=0;self.writes=[]
    def connect(self,device,cancel=None):
        if cancel.is_set():raise ConnectionAbortedError('连接已取消')
        self.attempted+=1
    def set_noise(self,mode):self.writes.append(mode)
    def set_preset(self,preset):self.writes.append(preset)
    def disconnect(self):self.connected=False
    def close(self):pass

class DeferredExecutor:
    def __init__(self):self.queue=[]
    def submit(self,fn):
        future=Future();self.queue.append((fn,future));return future
    def run(self):
        fn,future=self.queue.pop(0)
        try:future.set_result(fn())
        except Exception as error:future.set_exception(error)
    def shutdown(self,**kwargs):pass

class InteractionTests(unittest.TestCase):
    def controller(self,preferences=None):
        callbacks=[];s=Session();c=Controller(session=s,dispatch=callbacks.append,preferences=preferences)
        c._executor.shutdown(wait=False);c._executor=DeferredExecutor()
        self.addCleanup(c.close)
        return c,s,callbacks

    def test_busy_connect_does_not_get_stuck_connecting(self):
        c,s,q=self.controller();c.busy=True
        c.connect_selected()
        self.assertFalse(c.connecting)
        self.assertFalse(c.want_connection)

    def test_cancel_before_worker_start_never_establishes_connection(self):
        c,s,q=self.controller()
        from types import SimpleNamespace
        c.devices=[SimpleNamespace(name='OPPO Enco X3')];c.device_index=0
        c.connect_selected();self.assertTrue(c.busy)
        c.change_connection();self.assertTrue(c.cancel_requested)
        c._executor.run()
        for callback in q:callback()
        self.assertEqual(s.attempted,0)
        self.assertEqual(c.status,'已取消连接')
        self.assertFalse(c.busy or c.connecting or c.want_connection or c.cancel_requested)

    def test_cancel_after_handshake_before_ui_completion_disconnects(self):
        c,s,q=self.controller()
        from types import SimpleNamespace
        c.devices=[SimpleNamespace(name='OPPO Enco X3')];c.device_index=0
        c.connect_selected();c._executor.run();s.connected=True
        c.change_connection()
        q.pop(0)()
        self.assertTrue(c.busy)
        c._executor.run();q.pop(0)()
        self.assertFalse(s.connected or c.busy or c.want_connection)
        self.assertEqual(c.status,'已取消连接')

    def test_selected_controls_do_not_write_again(self):
        c,s,q=self.controller();s.connected=True
        c.change_noise('off');c.change_preset(0)
        self.assertEqual(s.writes,[])
        self.assertFalse(c.busy)

    def test_background_read_keeps_controls_available_and_never_floods_queue(self):
        c,s,q=self.controller();s.connected=s.ready=True;s.dirty=set()
        reads=[];s.refresh_due=lambda interactive,force=False:reads.append((interactive,force))
        c.refresh_background();c.refresh_background();c._refresh_tick()
        self.assertFalse(c.busy)
        self.assertEqual(len(c._executor.queue),1)
        c.change_noise('deep')
        self.assertTrue(c.busy)
        self.assertEqual(len(c._executor.queue),2)
        c._executor.run();q.pop(0)()
        self.assertTrue(c.busy)  # Poll completion must not finish the user's write.
        c._executor.run();q.pop(0)()
        self.assertFalse(c.busy or c._refreshing)
        self.assertEqual(s.writes,['deep'])
        self.assertEqual(reads,[(False,False)])

    def test_notification_during_user_action_is_drained_after_completion(self):
        c,s,q=self.controller();s.connected=s.ready=True;s.dirty=set()
        s.refresh_due=lambda *args,**kwargs:s.dirty.clear()
        c.change_noise('deep');s.dirty.add('multi');c._drain_notifications()
        self.assertEqual(len(c._executor.queue),1)
        c._executor.run();q.pop(0)()
        self.assertTrue(c._refreshing)
        c._executor.run();q.pop(0)()
        self.assertFalse(s.dirty or c._refreshing)

    def test_popup_preference_survives_theme_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'preferences.json';c,s,q=self.controller(p)
            c.change_connection_popup(False);c.change_theme(True)
            data=json.loads(p.read_text('utf-8'))
            self.assertEqual(data,{'dark':True,'theme_mode':'dark','connection_popup':False})
            other,_,_=self.controller(p)
            self.assertTrue(other.dark);self.assertFalse(other.connection_popup)

    def test_notice_only_after_handshake_once_per_connection(self):
        p=ConnectionNoticePolicy();token=(1,'X3')
        self.assertFalse(p.observe(False,token))
        self.assertFalse(p.observe(True,token,busy=True))
        self.assertTrue(p.observe(True,token))
        self.assertFalse(p.observe(True,token))
        self.assertFalse(p.observe(False,token))
        self.assertTrue(p.observe(True,(2,'X3')))

    def test_enabling_preference_does_not_replay_old_connection(self):
        p=ConnectionNoticePolicy();token=(1,'X3')
        self.assertFalse(p.observe(True,token,enabled=False))
        self.assertFalse(p.observe(True,token,enabled=True))
        self.assertFalse(p.observe(False,token))
        self.assertTrue(p.observe(True,(2,'X3')))


class PlacementTests(unittest.TestCase):
    def test_bounds_validate_and_support_negative_monitor_positions(self):
        from encolite.preferences import window_state
        self.assertEqual(window_state({'bounds':[-1800,100,1600,1200,False],'page':5}),((-1800,100,1600,1200,False),5))
        for bounds in ([0,0,-1,600,False],[True,0,800,640,False],[0,0,800,640,'false'],[0,0,800]):
            self.assertIsNone(window_state({'bounds':bounds})[0])

    def test_disconnected_display_restores_inside_visible_work_area(self):
        from encolite.preferences import fit_bounds
        self.assertEqual(fit_bounds((-3000,100,1800,1200,False),(0,0,1920,1080)),(0,0,1800,1080,False))
        self.assertEqual(fit_bounds((4000,2000,800,640,False),(0,0,1920,1080)),(1120,440,800,640,False))

    def test_theme_and_notice_changes_preserve_saved_placement(self):
        from encolite.preferences import write_preferences
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'preferences.json'
            placement={'bounds':[120,80,1728,1280,False],'page':4}
            write_preferences(p,{'main_window':placement})
            c=Controller(session=Session(),preferences=p)
            try:
                c.change_theme(True);c.change_connection_popup(False)
                self.assertEqual(json.loads(p.read_text('utf-8'))['main_window'],placement)
            finally:c.close()

if __name__=='__main__':unittest.main()
