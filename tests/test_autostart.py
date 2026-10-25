import tempfile,unittest
from pathlib import Path
from encolite.autostart import WindowsStartup


class ShortcutStore:
    def __init__(self):self.denied=False;self.ignore_writes=False
    def read(self,path):
        if self.denied:raise PermissionError('denied')
        import json
        return tuple(json.loads(path.read_text()))
    def write(self,path,target,arguments,root):
        if self.denied:raise PermissionError('denied')
        if not self.ignore_writes:
            import json
            path.write_text(json.dumps([str(target),arguments]))


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'耳机 客户端';self.root.mkdir()
        (self.root/'python').mkdir();(self.root/'python/pythonw.exe').touch()
        (self.root/'desktop_entry.py').touch()
        self.store=ShortcutStore();self.folder=Path(self.temp.name)/'Startup';self.startup=WindowsStartup(self.root,folder=self.folder,store=self.store)

    def test_registration_is_read_from_system_and_removal_preserves_neighbors(self):
        self.folder.mkdir();other=self.folder/'Other.lnk';other.write_text('untouched')
        self.assertFalse(self.startup.enabled())
        self.startup.set_enabled(True)
        self.assertTrue(WindowsStartup(self.root,folder=self.folder,store=self.store).enabled())
        self.assertIn('--tray-only',self.startup.read())
        self.startup.set_enabled(False);self.startup.set_enabled(False)
        self.assertFalse(self.startup.path.exists());self.assertEqual(other.read_text(),'untouched')

    def test_old_copy_does_not_remove_the_other_copy_registration(self):
        other=WindowsStartup(self.root/'another copy',folder=self.folder,store=self.store)
        self.folder.mkdir();self.store.write(self.startup.path,other.host(),__import__('subprocess').list2cmdline([str(other.root/'desktop_entry.py'),'--tray-only']),other.root)
        self.startup.set_enabled(False)
        self.assertEqual(self.startup.read(),other.command())

    def test_invalid_inputs_never_write_a_startup_entry(self):
        for value in (1,0,None,'true',[],{}):
            with self.assertRaises(ValueError):self.startup.set_enabled(value)
        self.assertFalse(self.startup.path.exists())

    def test_missing_runtime_and_entry_are_rejected_before_registration(self):
        (self.root/'desktop_entry.py').unlink()
        with self.assertRaises(FileNotFoundError):self.startup.set_enabled(True)
        self.assertFalse(self.startup.path.exists())

    def test_oversized_command_is_rejected_before_registration(self):
        root=self.root/('long-path-'*12);(root/'python').mkdir(parents=True)
        (root/'python/pythonw.exe').touch();(root/'desktop_entry.py').touch()
        with self.assertRaises(ValueError):WindowsStartup(root,folder=self.folder,store=self.store).set_enabled(True)
        self.assertFalse(self.startup.path.exists())

    def test_permission_and_readback_failure_are_not_reported_as_enabled(self):
        self.startup.set_enabled(True);self.store.denied=True
        with self.assertRaises(PermissionError):self.startup.enabled()
        self.store.denied=False;self.startup.set_enabled(False);self.store.ignore_writes=True
        with self.assertRaises(OSError):self.startup.set_enabled(True)
        self.assertFalse(self.startup.enabled())

    def test_source_runtime_and_bundle_runtime_use_absolute_windowless_entry(self):
        command=self.startup.command(validate=True)
        self.assertIn(str(self.root/'python/pythonw.exe'),command)
        (self.root/'python/pythonw.exe').unlink()
        source=self.root/'.tools/python-3.13.17-embed-amd64/pythonw.exe'
        source.parent.mkdir(parents=True);source.touch()
        self.assertIn(str(source),self.startup.command(validate=True))
        self.assertNotIn('python.exe',self.startup.command())
