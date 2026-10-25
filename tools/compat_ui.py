"""Backport the current UI to Slint 1.17 in an isolated package directory."""
from pathlib import Path


def backport(root: Path, version='1.17.1b2'):
    for ui in (root / 'ui').glob('*.slint'):
        source = ui.read_text('utf-8').replace('content-width:', 'viewport-width:')
        if int(version.split('.')[1]) < 17 and ui.name == 'app.slint':
            source = source.replace('in-out property <bool> window-maximized <=> root.maximized;',
                'in-out property <bool> window-maximized: false;')
            source = source.replace('in-out property <bool> window-minimized <=> root.minimized;',
                'in-out property <bool> window-minimized: false;')
            source = source.replace('root.maximized', 'root.window-maximized').replace('root.minimized', 'root.window-minimized')
            source = source.replace('changed maximized => { root.geometry-changed(); }',
                'callback window-state-requested();\n    changed window-maximized => { root.window-state-requested(); root.geometry-changed(); }')
            source = source.replace('changed minimized => { root.geometry-changed(); }',
                'changed window-minimized => { root.window-state-requested(); root.geometry-changed(); }')
        if 'WindowMoveArea {' in source:
            source = source.replace('callback geometry-changed();',
                'callback drag-window();\n    callback geometry-changed();')
            source = source.replace('WindowMoveArea {',
                'TouchArea { pointer-event(event) => { '
                'if event.kind == PointerEventKind.down && event.button == PointerEventButton.left '
                '{ root.drag-window(); } }')
        ui.write_text(source, 'utf-8')
    shell = root / 'encolite/windows_shell.py'
    shell.write_text(shell.read_text('utf-8') + '''

def drag_window(title):
    hwnd = window_handle(title)
    if hwnd:
        point = W.POINT()
        if GetCursorPos(C.byref(point)):
            api(user, 'ReleaseCapture', W.BOOL)()
            position = C.c_int32((point.x & 0xffff) | ((point.y & 0xffff) << 16)).value
            PostMessage(hwnd, 0xA1, 2, position)  # WM_NCLBUTTONDOWN, HTCAPTION
''', 'utf-8')
    desktop = root / 'encolite/desktop.py'
    source = desktop.read_text('utf-8')
    for view, title in (('main', 'MAIN_TITLE'), ('quick', 'QUICK_TITLE')):
        source = source.replace(f'self.{view}.geometry_changed =',
            f'self.{view}.drag_window = lambda:self.native_shell.drag_window(self.{title}) '
            f'if self.native_shell else None\n            self.{view}.geometry_changed =')
    if int(version.split('.')[1]) < 17:
        source = source.replace('self.main.geometry_changed =',
            'self.main.window_state_requested = self._request_main_state\n            self.main.geometry_changed =')
        source = source.replace('self.main_hwnd=hwnd',
            'self.main_hwnd=hwnd\n            self.native_shell.watch_window_state(hwnd, '
            'lambda:self.native.invoke_from_event_loop(self._sync_main_state))')
        source += '''

    def _request_main_state(self):
        if getattr(self, '_syncing_main_state', False) or not self.native_shell or not self.main:
            return
        hwnd = self.main_hwnd
        if not hwnd:
            return
        if self.main.window_minimized:
            if not self.native_shell.IsIconic(hwnd):self.native_shell.ShowWindow(hwnd, 6)
        elif self.native_shell.IsIconic(hwnd):
            self.native_shell.ShowWindow(hwnd, 9)
        elif bool(self.main.window_maximized) != bool(self.native_shell.IsZoomed(hwnd)):
            self.native_shell.ShowWindow(hwnd, 3 if self.main.window_maximized else 9)

    def _sync_main_state(self):
        if self.exiting or not self.main or not self.main_hwnd:
            return
        self._syncing_main_state = True
        try:
            self.main.window_minimized = bool(self.native_shell.IsIconic(self.main_hwnd))
            if not self.main.window_minimized:
                self.main.window_maximized = bool(self.native_shell.IsZoomed(self.main_hwnd))
        finally:
            self._syncing_main_state = False
        self.round_window(self.MAIN_TITLE)
'''
        shell_source = shell.read_text('utf-8')
        shell_source = shell_source.replace('@SUBCLASSPROC\ndef _borderless_proc',
            '_window_state_watchers = {}\n\ndef watch_window_state(hwnd, callback):\n'
            '    _window_state_watchers[hwnd] = callback\n\n@SUBCLASSPROC\ndef _borderless_proc')
        shell_source = shell_source.replace('if message==0x82:  # WM_NCDESTROY',
            'if message==5 and hwnd in _window_state_watchers:  # WM_SIZE\n'
            '        _window_state_watchers[hwnd]()\n'
            '    if message==0x82:  # WM_NCDESTROY\n'
            '        _window_state_watchers.pop(hwnd, None)')
        shell.write_text(shell_source, 'utf-8')
    desktop.write_text(source, 'utf-8')
