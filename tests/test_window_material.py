import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from encolite.window_material import WindowMaterial,rounded_region_rows
from encolite.controller import Controller
from encolite.session import DemoSession


class FakeDwm:
    supported=True
    def __init__(self):self.calls=[];self.reject=False
    def attribute(self,hwnd,name,value):
        self.calls.append(('attribute',hwnd,name,value))
        return True
    def frame(self,hwnd,extended):self.calls.append(('frame',hwnd,extended));return True
    def accent(self,hwnd,enabled,dark):self.calls.append(('accent',hwnd,enabled,dark));return not(enabled and self.reject)
    def shape(self,hwnd,shape):self.calls.append(('shape',hwnd,shape));return True


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
        self.assertIn(('attribute',17,33,1),api.calls)
        self.assertIn(('frame',17,False),api.calls)
        material.forget(17);self.assertFalse(material.states)

    def test_partial_native_failure_rolls_back_to_an_opaque_compatible_frame(self):
        api=FakeDwm();api.reject=True;material=WindowMaterial(api)
        self.assertFalse(material.apply(23,True))
        self.assertIn(('accent',23,False,False),api.calls)
        self.assertEqual(api.calls[-4:],[('attribute',23,38,1),('frame',23,False),('attribute',23,33,1),('attribute',23,34,0xfffffffe)])
        count=len(api.calls);self.assertFalse(material.apply(23,True));self.assertEqual(count,len(api.calls))
        api.reject=False;self.assertTrue(material.apply(23,True,force=True))

    def test_unsupported_platform_uses_no_native_calls(self):
        api=FakeDwm();api.supported=False;material=WindowMaterial(api)
        self.assertFalse(material.apply(1,True));self.assertFalse(api.calls)

    def test_opaque_windows_do_not_change_native_composition(self):
        api=FakeDwm();material=WindowMaterial(api)
        self.assertFalse(material.apply(1,False,force=True))
        self.assertFalse(api.calls)

    def test_rounded_mask_has_symmetric_corners_and_never_extends_outside_window(self):
        for ratio in (1,1.25,1.5,2):
            width,height,radius=round(352*ratio),round(374*ratio),round(12*ratio)
            rows=rounded_region_rows(width,height,radius)
            self.assertEqual(len(rows),radius*2+1)
            self.assertTrue(all(0<=l<r<=width and 0<=t<b<=height for l,t,r,b in rows))
            self.assertTrue(all(l==width-r for l,t,r,b in rows))
            self.assertGreater(rows[0][0],0)
            self.assertEqual(rows[0],(rows[-1][0],height-rows[-1][3],rows[-1][2],height-rows[-1][1]))

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
