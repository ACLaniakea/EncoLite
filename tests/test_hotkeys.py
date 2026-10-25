import json,tempfile,unittest,sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from encolite.hotkeys import Hotkeys,binding,saved_config,execute_shortcut,ACTIONS

class Registration:
    def __init__(self):self.values={};self.conflicts=[]
    def register(self,key,value):
        if value in self.conflicts:return False
        if any(value==current for current in self.values.values()):return False
        self.values[key]=deepcopy(value);return True
    def unregister(self,key):self.values.pop(key,None)

class HotkeyTests(unittest.TestCase):
    def manager(self,config=None,save=None):
        registration=Registration();actions=[];saved=[]
        manager=Hotkeys(registration,config,save or (lambda value:saved.append(deepcopy(value))),actions.append)
        self.addCleanup(manager.close)
        return manager,registration,actions,saved

    def test_defaults_and_invalid_preferences(self):
        config=saved_config(None)
        self.assertTrue(config['enabled']);self.assertEqual(config['bindings']['show_quick'],{'modifiers':3,'key':81})
        invalid=saved_config({'enabled':'no','bindings':{'toggle_noise':{'modifiers':8,'key':65},'show_quick':None}})
        self.assertTrue(invalid['enabled']);self.assertIsNone(invalid['bindings']['toggle_noise']);self.assertIsNone(invalid['bindings']['show_quick'])
        duplicate={'modifiers':3,'key':65}
        self.assertIsNone(saved_config({'bindings':{'show_quick':duplicate,'toggle_noise':duplicate}})['bindings']['show_quick'])
        for value in ({'modifiers':0,'key':65},{'modifiers':4,'key':65},{'modifiers':3,'key':123},{'modifiers':True,'key':65},{'modifiers':3,'key':65,'extra':1},{'modifiers':1,'key':115},{'modifiers':3,'key':46}):
            with self.assertRaises(ValueError):binding(value)

    def test_conflicts_preserve_previous_registration_and_preferences(self):
        manager,registration,_,saved=self.manager();before=deepcopy(manager.config);old=manager.active.copy()
        current={'modifiers':7,'key':88};registration.conflicts.append(current)
        with self.assertRaises(ValueError):manager.set_binding('toggle_noise',current)
        self.assertEqual(manager.config,before);self.assertEqual(manager.active,old);self.assertFalse(saved)
        with self.assertRaisesRegex(ValueError,'已用于'):manager.set_binding('toggle_noise',manager.config['bindings']['show_quick'])
        self.assertEqual(len(registration.values),2)

    def test_replace_clear_and_stale_messages(self):
        manager,registration,actions,_=self.manager();old=manager.active['toggle_noise']
        value={'modifiers':7,'key':128};manager.set_binding('toggle_noise',value)
        self.assertFalse(manager.handle(old[0],old[1]['modifiers']|old[1]['key']<<16))
        current=manager.active['toggle_noise'];self.assertTrue(manager.handle(current[0],7|128<<16));self.assertEqual(actions,['toggle_noise'])
        manager.set_binding('toggle_noise',None);self.assertNotIn('toggle_noise',manager.active)
        self.assertEqual(len(registration.values),1)

    def test_write_failure_rolls_back_native_binding(self):
        def reject(_):raise OSError('disk full')
        manager,registration,_,_=self.manager(save=reject);before=deepcopy(manager.config);old=manager.active.copy()
        with self.assertRaises(OSError):manager.set_binding('toggle_noise',{'modifiers':7,'key':128})
        self.assertEqual(manager.config,before);self.assertEqual(manager.active,old);self.assertEqual(len(registration.values),2)
        with self.assertRaises(OSError):manager.set_enabled(False)
        self.assertEqual(manager.active,old)

    def test_suspension_disable_and_cleanup(self):
        manager,registration,actions,_=self.manager();old=manager.active['toggle_noise'];manager.suspend()
        self.assertFalse(registration.values);self.assertFalse(manager.handle(old[0],3|78<<16))
        manager.set_binding('toggle_noise',{'modifiers':7,'key':128});self.assertFalse(registration.values)
        manager.resume();self.assertEqual(len(registration.values),2)
        manager.set_enabled(False);self.assertFalse(registration.values)
        manager.set_binding('show_main',{'modifiers':7,'key':129});self.assertFalse(registration.values)
        manager.set_enabled(True);self.assertEqual(len(registration.values),3)
        manager.close();self.assertFalse(registration.values);self.assertFalse(actions)

    def test_startup_conflict_reports_only_failed_binding_and_preserves_config(self):
        registration=Registration();registration.conflicts.append({'modifiers':3,'key':78})
        manager=Hotkeys(registration,None,lambda _:None,lambda _:None);self.addCleanup(manager.close)
        self.assertIn('toggle_noise',manager.errors);self.assertIn('show_quick',manager.active)
        self.assertEqual(manager.config['bindings']['toggle_noise'],{'modifiers':3,'key':78})
        registration.conflicts=[];manager.suspend();manager.resume();self.assertFalse(manager.errors)

    def test_persistence_keeps_explicit_unbound_and_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json'
            manager,_,_,_=self.manager(save=lambda value:path.write_text(json.dumps(value),'utf-8'))
            manager.set_binding('toggle_noise',None);manager.set_binding('show_main',{'modifiers':6,'key':69});manager.set_enabled(False)
            restarted,registration,_,_=self.manager(json.loads(path.read_text('utf-8')))
            self.assertEqual(restarted.config,manager.config);self.assertFalse(registration.values)
            self.assertIsNone(restarted.config['bindings']['toggle_noise'])

    def controller(self):
        return SimpleNamespace(session=SimpleNamespace(connected=True,ready=True,noise='deep',noise_modes={'deep':4,'off':0,'vocal':9,'transparency':8}),
            live=True,busy=False,connecting=False,anc_level='deep',change_noise=Mock(),set_status=Mock(),sync=Mock(),next_preset=Mock(),_presets=lambda:[{'id':7}])

    def test_noise_toggle_uses_real_modes_and_remembered_anc(self):
        controller=self.controller();execute_shortcut(controller,'toggle_noise',Mock());controller.change_noise.assert_called_once_with('transparency')
        for current in ('vocal','transparency','off'):
            controller.change_noise.reset_mock();controller.session.noise=current
            execute_shortcut(controller,'toggle_noise',Mock());controller.change_noise.assert_called_once_with('deep')
        controller.session.noise='deep';controller.anc_level='smart';execute_shortcut(controller,'toggle_noise',Mock());controller.change_noise.assert_called_with('transparency')
        controller.session.noise_modes={'off':0,'transparency':8};controller.change_noise.reset_mock()
        execute_shortcut(controller,'toggle_noise',Mock());controller.change_noise.assert_not_called();controller.set_status.assert_called()

    def test_busy_disconnected_and_capability_guards(self):
        controller=self.controller();controller.busy=True;execute_shortcut(controller,'toggle_noise',Mock());controller.change_noise.assert_not_called()
        controller.busy=False;controller.session.connected=False;execute_shortcut(controller,'noise_off',Mock());controller.change_noise.assert_not_called()
        controller.session.connected=True;execute_shortcut(controller,'noise_off',Mock());controller.change_noise.assert_called_once_with('off')
        controller.session.noise_modes={'deep':4};controller.change_noise.reset_mock();execute_shortcut(controller,'noise_off',Mock());controller.change_noise.assert_not_called()
        controller.session.ready=False;execute_shortcut(controller,'next_preset',Mock());controller.next_preset.assert_not_called()

    def test_window_shortcuts_work_without_connection_and_presets_keep_real_ids(self):
        controller=self.controller();controller.session.connected=False;controller.busy=True;show=Mock()
        execute_shortcut(controller,'show_main',show);execute_shortcut(controller,'show_quick',show)
        self.assertEqual([call.args for call in show.call_args_list],[('main',),('quick',)])
        controller.session.connected=True;controller.busy=False;execute_shortcut(controller,'next_preset',show);controller.next_preset.assert_called_once()

if __name__=='__main__':unittest.main()
