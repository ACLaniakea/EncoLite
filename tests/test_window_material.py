import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from encolite.window_material import WindowMaterial
from encolite.controller import Controller
from encolite.session import DemoSession


class FakeDwm:
    supported=True
    def __init__(self):self.calls=[];self.reject=False;self.reject_frame=False
    def prepare_frame(self,hwnd):self.calls.append(('prepare',hwnd));return not self.reject_frame
    def attribute(self,hwnd,name,value):
        self.calls.append(('attribute',hwnd,name,value))
        return not(name==38 and value==3 and self.reject)
    def accent(self,hwnd,enabled,dark):self.calls.append(('accent',hwnd,enabled,dark));return not(enabled and self.reject)
    def frame(self,hwnd,extended):self.calls.append(('frame',hwnd,extended));return True
    def refresh_frame(self,hwnd):self.calls.append(('refresh_frame',hwnd))


class WindowMaterialTests(unittest.TestCase):
    def test_native_updates_are_cached_and_dark_theme_reapplies(self):
        api=FakeDwm();material=WindowMaterial(api)
        self.assertTrue(material.apply(17,True));count=len(api.calls)
        for _ in range(30):self.assertTrue(material.apply(17,True))
        self.assertEqual(len(api.calls),count)
        self.assertTrue(material.apply(17,True,True))
        self.assertIn(('attribute',17,20,1),api.calls[count:])
        self.assertFalse(material.apply(17,False,True))
        self.assertIn(('attribute',17,38,1),api.calls)
        self.assertIn(('prepare',17),api.calls)
        self.assertIn(('frame',17,False),api.calls)
        material.forget(17);self.assertFalse(material.states)

    def test_partial_native_failure_rolls_back_to_an_opaque_compatible_frame(self):
        api=FakeDwm();api.reject=True;material=WindowMaterial(api)
        self.assertFalse(material.apply(23,True))
        self.assertIn(('attribute',23,38,1),api.calls)
        self.assertEqual(api.calls[-1],('accent',23,False,False))
        count=len(api.calls);self.assertFalse(material.apply(23,True));self.assertEqual(count,len(api.calls))
        api.reject=False;self.assertTrue(material.apply(23,True,force=True))

    def test_unsupported_platform_uses_no_native_calls(self):
        api=FakeDwm();api.supported=False;material=WindowMaterial(api)
        self.assertFalse(material.apply(1,True));self.assertFalse(api.calls)

    def test_motion_hides_native_halo_and_restores_compact_frame_once(self):
        api=FakeDwm();material=WindowMaterial(api)
        material.apply(5,False)
        material.decorate(5,False)
        self.assertIn(('attribute',5,33,1),api.calls)
        self.assertIn(('attribute',5,34,0xfffffffe),api.calls)
        count=len(api.calls);material.decorate(5,False);self.assertEqual(len(api.calls),count)
        material.decorate(5,True)
        self.assertIn(('attribute',5,33,3),api.calls)
        material.forget(5);self.assertFalse(material.decorations)

    def test_opaque_windows_keep_the_system_frame_without_glass(self):
        api=FakeDwm();material=WindowMaterial(api)
        self.assertFalse(material.apply(1,False,force=True))
        self.assertTrue(material.frames[1]);self.assertNotIn(('attribute',1,38,3),api.calls)
        count=len(api.calls);material.apply(1,False);self.assertEqual(count,len(api.calls))

    def test_failed_native_frame_never_enables_a_detached_backdrop(self):
        api=FakeDwm();api.reject_frame=True;material=WindowMaterial(api)
        self.assertFalse(material.apply(1,True))
        self.assertNotIn(('attribute',1,38,3),api.calls)
        material.forget(1);self.assertFalse(material.frames);self.assertFalse(material.states)

    def test_invalid_transparency_preference_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json'
            for value in (True,-1,101,1.5,'50',None):
                path.write_text(json.dumps({'glass_transparency':value}),'utf-8')
                self.assertEqual(self.controller(path).glass_transparency,70)

    def test_transparency_is_persisted_independently_of_speed_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json';controller=self.controller(path)
            self.assertEqual(controller.glass_transparency,70)
            for value in (0,43,100):
                controller.change_glass_transparency(value);controller.change_fast_mode(True)
                self.assertEqual(self.controller(path).glass_transparency,value)
                controller.change_fast_mode(False);self.assertEqual(controller.glass_transparency,value)
            for value in (True,1.5,'50',-1,101,None):
                with self.assertRaises(ValueError):controller.change_glass_transparency(value)

    def controller(self,path):
        controller=Controller(session=DemoSession(),preferences=path)
        self.addCleanup(controller.close);return controller

    def test_preference_survives_speed_mode_restart_and_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json';placement={'bounds':[1,2,864,640,False],'page':2}
            path.write_text(json.dumps({'qt_main':placement}),'utf-8')
            controller=self.controller(path);self.assertTrue(controller.glass_effect)
            controller.change_glass_effect(False);controller.change_fast_mode(True)
            restarted=self.controller(path);self.assertFalse(restarted.glass_effect);self.assertTrue(restarted.fast_mode)
            controller.change_glass_effect(True);controller.change_fast_mode(False)
            restarted=self.controller(path);self.assertTrue(restarted.glass_effect);self.assertFalse(restarted.fast_mode)
            self.assertEqual(restarted.preference_data['qt_main'],placement)
            for value in ('true',1,None):
                with self.assertRaises(ValueError):restarted.change_glass_effect(value)
            self.assertTrue(restarted.glass_effect)

    def test_system_policy_change_does_not_overwrite_user_glass_choice(self):
        controller=self.controller(None)
        with patch('encolite.appearance.read_system_transparency',return_value=False):controller.refresh_system_appearance()
        self.assertFalse(controller.system_transparency);self.assertTrue(controller.glass_effect)
        with patch('encolite.appearance.read_system_transparency',return_value=True):controller.refresh_system_appearance()
        self.assertTrue(controller.system_transparency);self.assertTrue(controller.glass_effect)

if __name__=='__main__':unittest.main()
