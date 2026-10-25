import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from encolite.appearance import accent_color,accent_palette,contrast,saved_accent
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite.json_view import JsonView
from encolite.presentation import JsonPresentation

class AccentTests(unittest.TestCase):
    def controller(self,path=None):
        with patch('encolite.appearance.read_system_accent',return_value='#0078d4'):
            c=Controller(session=DemoSession(),preferences=path,presentation=JsonPresentation())
        self.addCleanup(c.close);return c

    def test_invalid_color_does_not_change_or_persist_state(self):
        c=self.controller();old=(c.accent_mode,c.accent_color)
        for value in ('red','#123','#ffffff00','#12ZZ56','transparent',None,123,[]):
            with self.assertRaises(ValueError):c.change_accent_color(value)
            self.assertEqual((c.accent_mode,c.accent_color),old)
        self.assertEqual(accent_color('#ABCDEF'),'#abcdef')
        self.assertEqual(saved_accent({'accent_mode':'bad','accent_color':'red'}),('custom','#168b51'))

    def test_custom_color_survives_restart_and_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'prefs.json';placement={'bounds':[10,20,864,640,False],'page':2}
            p.write_text(json.dumps({'qt_main':placement,'theme_mode':'system'}),'utf-8')
            c=self.controller(p);c.change_accent_color('#7160D9')
            c.change_accent_mode('system')
            restarted=self.controller(p)
            self.assertEqual((restarted.accent_mode,restarted.accent_color),('system','#7160d9'))
            self.assertEqual(json.loads(p.read_text())['qt_main'],placement)
            restarted.change_accent_mode('custom');self.assertEqual(restarted.accent_color,'#7160d9')

    def test_system_event_updates_palette_without_writing_or_overriding_custom(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'prefs.json';c=self.controller(p);view=JsonView();c.attach(view)
            with patch('encolite.appearance.read_system_accent',return_value='#0078d4'):c.change_accent_mode('system')
            saved=p.read_bytes()
            with patch('encolite.appearance.read_system_accent',return_value='#be4278'):
                c.refresh_system_appearance()
            self.assertEqual(view.palette,accent_palette('#be4278',c.dark));self.assertEqual(p.read_bytes(),saved)
            c.change_accent_color('#008184');palette=view.palette
            with patch('encolite.appearance.read_system_accent',return_value='#c04b33'):c.refresh_system_appearance()
            self.assertEqual(view.palette,palette)

    def test_arbitrary_colors_keep_readable_text_and_selected_states(self):
        for color in ('#000000','#ffffff','#ffff00','#00ffff','#ff0000','#0078d4','#7160d9','#168b51','#687080'):
            for dark in (False,True):
                p=accent_palette(color,dark)
                with self.subTest(color=color,dark=dark):
                    for surface in ('bg','card','selection'):
                        self.assertGreaterEqual(contrast(p['accent'],p[surface]),4.5)
                    self.assertGreaterEqual(contrast(p['accent_text'],p['accent']),4.5)
                    self.assertGreaterEqual(contrast(p['text'],p['card']),7)
