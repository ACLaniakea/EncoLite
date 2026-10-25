import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from encolite.appearance import saved_theme_mode
from encolite.controller import Controller
from encolite.session import DemoSession


class AppearanceTests(unittest.TestCase):
    def controller(self,path=None,system=(False,True)):
        with patch('encolite.appearance.read_system_appearance',return_value=system):
            controller=Controller(session=DemoSession(),preferences=path)
        self.addCleanup(controller.close)
        return controller

    def test_new_preferences_follow_system_and_legacy_manual_choice_survives(self):
        self.assertEqual(saved_theme_mode({}),'system')
        self.assertEqual(saved_theme_mode({'dark':True}),'dark')
        self.assertEqual(saved_theme_mode({'dark':False}),'light')
        self.assertEqual(saved_theme_mode({'dark':'false','theme_mode':'invalid'}),'system')
        self.assertEqual(saved_theme_mode({'theme_mode':'system','dark':True}),'system')
        controller=self.controller(system=(True,False))
        self.assertTrue(controller.dark)
        self.assertFalse(controller.system_motion)

    def test_system_changes_follow_only_automatic_mode_without_writing_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json';controller=self.controller(path)
            controller.change_theme_mode('system');saved=path.read_bytes()
            with patch('encolite.appearance.read_system_appearance',return_value=(True,False)):
                controller.refresh_system_appearance()
            self.assertTrue(controller.dark)
            self.assertFalse(controller.system_motion)
            self.assertEqual(path.read_bytes(),saved)
            controller.change_theme_mode('light')
            with patch('encolite.appearance.read_system_appearance',return_value=(True,True)):
                controller.refresh_system_appearance()
            self.assertFalse(controller.dark)
            self.assertTrue(controller.system_motion)

    def test_speed_and_notice_do_not_disable_system_follow_or_erase_window_placement(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json'
            placement={'bounds':[12,24,864,640,False],'page':2}
            path.write_text(json.dumps({'theme_mode':'system','web_main':placement}),'utf-8')
            controller=self.controller(path,system=(True,True))
            controller.change_fast_mode(True);controller.change_connection_popup(False)
            self.assertEqual(controller.theme_mode,'system')
            data=json.loads(path.read_text('utf-8'))
            self.assertEqual(data['web_main'],placement)
            restarted=self.controller(path,system=(False,True))
            self.assertEqual(restarted.theme_mode,'system')
            self.assertTrue(restarted.fast_mode)
            self.assertFalse(restarted.dark or restarted.connection_popup)
            with self.assertRaises(ValueError):restarted.change_fast_mode('false')
            with self.assertRaises(ValueError):restarted.change_theme_mode('arbitrary')

    def test_fast_launch_is_opt_in_persistent_and_independent_of_animation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json';controller=self.controller(path)
            self.assertFalse(controller.fast_launch)
            controller.change_fast_launch(True)
            self.assertTrue(self.controller(path).fast_launch)
            self.assertFalse(controller.fast_mode)
            controller.change_fast_launch(False)
            self.assertFalse(self.controller(path).fast_launch)
            with self.assertRaises(ValueError):controller.change_fast_launch('true')

    def test_quick_topmost_defaults_on_and_persists_explicit_off(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json';controller=self.controller(path)
            self.assertTrue(controller.quick_topmost)
            controller.change_quick_topmost(False)
            self.assertFalse(self.controller(path).quick_topmost)
            self.assertEqual(controller.theme_mode,'system')
            for value in ('false',0,None):
                with self.assertRaises(ValueError):controller.change_quick_topmost(value)
            self.assertFalse(controller.quick_topmost)
            controller.change_quick_topmost(True)
            self.assertTrue(self.controller(path).quick_topmost)

    def test_quick_idle_duration_and_enable_are_saved_independently(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json';controller=self.controller(path)
            self.assertFalse(controller.quick_auto_hide);self.assertEqual(controller.quick_idle_seconds,30)
            controller.change_quick_idle_seconds(37);controller.change_quick_auto_hide(True)
            restarted=self.controller(path)
            self.assertTrue(restarted.quick_auto_hide);self.assertEqual(restarted.quick_idle_seconds,37)
            controller.change_quick_auto_hide(False)
            restarted=self.controller(path)
            self.assertFalse(restarted.quick_auto_hide);self.assertEqual(restarted.quick_idle_seconds,37)
            self.assertTrue(restarted.quick_topmost)

    def test_quick_idle_invalid_values_do_not_change_state(self):
        controller=self.controller()
        for value in (0,4,3601,True,30.0,'30',None):
            with self.assertRaises(ValueError):controller.change_quick_idle_seconds(value)
        for value in ('false',0,None):
            with self.assertRaises(ValueError):controller.change_quick_auto_hide(value)
        self.assertFalse(controller.quick_auto_hide);self.assertEqual(controller.quick_idle_seconds,30)
        for value in (5,3600,17):
            controller.change_quick_idle_seconds(value);self.assertEqual(controller.quick_idle_seconds,value)

if __name__=='__main__':unittest.main()
