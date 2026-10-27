"""Qt Quick windows driven by the existing bounded JSON protocol."""
from pathlib import Path
import json
import os
import sys
import threading
import traceback

from PySide6.QtCore import (QObject, Property, Signal, Slot, Qt, QTimer, QUrl, QEvent,
                           QAbstractListModel, QModelIndex, QMetaObject, QAbstractNativeEventFilter)
from PySide6.QtGui import QGuiApplication, QFont, QIcon
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuick import QQuickWindow
from .preferences import window_state, fit_bounds
from .hotkeys import binding, label
from .window_material import WindowMaterial

TITLES = {'main': 'Enco Lite · 耳机助手', 'quick': 'Enco Lite · 快捷控制', 'notice': 'Enco Lite · 连接提示'}


def plain(value):
    if hasattr(value, 'toVariant'): value = value.toVariant()
    if isinstance(value, dict): return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [plain(item) for item in value]
    if isinstance(value, float) and value.is_integer(): return int(value)
    return value


class Bands(QAbstractListModel):
    def __init__(self):
        super().__init__(); self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def roleNames(self):
        return {Qt.UserRole + 1: b'label', Qt.UserRole + 2: b'gain'}

    def data(self, index, role):
        if index.isValid() and 0 <= index.row() < len(self.rows):
            return self.rows[index.row()].get({Qt.UserRole + 1: 'label', Qt.UserRole + 2: 'gain'}.get(role, ''))

    def update(self, rows):
        rows = [dict(row) for row in rows]
        if [r.get('label') for r in rows] != [r.get('label') for r in self.rows]:
            self.beginResetModel(); self.rows = rows; self.endResetModel()
        else:
            for i, row in enumerate(rows):
                if row != self.rows[i]:
                    self.rows[i] = row
                    self.dataChanged.emit(self.index(i), self.index(i), [Qt.UserRole + 2])


class Bridge(QObject):
    changed = Signal()
    def __init__(self, desktop):
        super().__init__(); self.desktop = desktop; self.payload = {}; self.pending = {}; self.bands = Bands()
        self._state = {'connected': False, 'busy': False, 'model_name': '未连接耳机', 'noise': '',
                       'glass_effect':False,'status': '正在读取耳机…', 'eq_minimum': -6, 'eq_maximum': 6,
                       'switches': [], 'noise_options': [], 'presets': [], 'bands': [], 'multi_devices': [],
                       'custom_names': [], 'device_names': [], 'model_names': [], 'spatial_options': [], 'game_options': []}
        self._hotkeys = {'items': [], 'enabled': True, 'capturing': False}
        self._preferences = {}; self._picture = ''; self.request = 0;self._glass_preview=None

    @Property('QVariantMap', notify=changed)
    def state(self): return self._state

    @Property('QVariantMap', notify=changed)
    def hotkeys(self): return self._hotkeys

    @Property('QVariantMap', notify=changed)
    def preferences(self): return self._preferences

    @Property(str, notify=changed)
    def picture(self): return self._picture

    @Property(bool, notify=changed)
    def motion(self): return not self._state.get('fast_mode', False) and self._state.get('system_motion', True)

    @Property(bool, constant=True)
    def glassAvailable(self): return self.desktop.material.supported

    @Property(bool, constant=True)
    def systemFrameAvailable(self): return self.desktop.material.supported

    @Property(int,notify=changed)
    def glassTransparency(self):
        return self._glass_preview if self._glass_preview is not None else self._state.get('glass_transparency',70)

    @Slot(int)
    def previewGlassTransparency(self,value):
        self._glass_preview=max(0,min(100,value));self.changed.emit()

    @Property(bool, notify=changed)
    def glassAllowed(self):
        return (self.glassAvailable and self._state.get('glass_effect') is True
                and not self._state.get('fast_mode',False) and self._state.get('system_transparency',True) is not False)

    @Property(QObject, constant=True)
    def bandModel(self): return self.bands

    def update(self, payload):
        self.payload = payload
        state = {**self._state, **payload.get('state', {})}
        if state.get('glass_transparency')==self._glass_preview:self._glass_preview=None
        switches = [dict(row) for row in state.get('switches') or []]
        for key, pending in list(self.pending.items()):
            row = next((row for row in switches if row['key'] == key), None)
            if state.get('busy'): pending['busy'] = True
            if not row or row['checked'] == pending['value'] or state.get('status_error') or (pending['busy'] and not state.get('busy')):
                self.pending.pop(key, None)
            else:
                row['checked'] = pending['value']; row['enabled'] = False
        state['switches'] = switches
        self._state = state
        self._hotkeys = payload.get('hotkeys') or self._hotkeys
        self._preferences = payload.get('preferences') or {}
        picture = state.get('product_picture')
        path = Path(picture) if picture else self.desktop.root / 'ui/assets/device-neutral.svg'
        self._picture = QUrl.fromLocalFile(str(path)).toString() if path.is_file() else ''
        self.bands.update(state.get('bands') or [])
        self.changed.emit()

    @Slot(str, 'QVariantList')
    def action(self, name, args):
        args = plain(args)
        if name == 'change_feature' and len(args) == 2:
            key, value = args
            token = object(); self.pending[key] = {'value': bool(value), 'busy': False, 'token': token}
            def expire():
                if self.pending.get(key, {}).get('token') is token:
                    self.pending.pop(key, None); self.update(self.payload)
            QTimer.singleShot(15000, expire)
        self.desktop.send('action', name=name, args=args)

    @Slot(str)
    def show(self, kind): self.action('show', [kind])

    @Slot(str)
    def closeWindow(self, kind): self.desktop.close_view(kind)

    @Slot(str)
    def minimize(self, kind):
        if kind in self.desktop.windows: self.desktop.windows[kind].showMinimized()

    @Slot(str)
    def maximize(self, kind):
        window = self.desktop.windows.get(kind)
        if window:
            window.showNormal() if window.windowState() == Qt.WindowMaximized else window.showMaximized()

    @Slot(bool)
    def hoverNotice(self, inside): self.desktop.notice_hover(inside)

    @Slot(int, int, result='QVariantMap')
    def captureKey(self, key, modifiers):
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta): return {'ignore': True}
        if key in (Qt.Key_Backspace, Qt.Key_Delete) and not modifiers: return {'binding': None, 'label': '未设置'}
        special = {Qt.Key_Space: 32, Qt.Key_PageUp: 33, Qt.Key_PageDown: 34, Qt.Key_End: 35,
                   Qt.Key_Home: 36, Qt.Key_Left: 37, Qt.Key_Up: 38, Qt.Key_Right: 39, Qt.Key_Down: 40,
                   Qt.Key_Insert: 45, Qt.Key_Delete: 46}
        vk = 112 + key - int(Qt.Key_F1) if int(Qt.Key_F1) <= key <= int(Qt.Key_F24) else special.get(key, key)
        mods = (2 if modifiers & Qt.ControlModifier.value else 0) | (1 if modifiers & Qt.AltModifier.value else 0) | (4 if modifiers & Qt.ShiftModifier.value else 0)
        try:
            if modifiers & Qt.MetaModifier.value: raise ValueError('请使用 Ctrl 或 Alt 组合，不使用 Win 键')
            value = binding({'modifiers': mods, 'key': int(vk)})
            return {'binding': value, 'label': label(value)}
        except ValueError as error: return {'error': str(error)}

    @Slot(str, 'QVariant', result=str)
    def saveHotkey(self, action, value):
        self.request += 1; request = 'qt-' + str(self.request)
        self.action('set_hotkey', [action, value, request]); return request


class MaterialEvents(QAbstractNativeEventFilter):
    def __init__(self,desktop):super().__init__();self.desktop=desktop
    def nativeEventFilter(self,event_type,message):
        if sys.platform=='win32':
            import ctypes as C
            from ctypes import wintypes as W
            msg=C.cast(int(message),C.POINTER(W.MSG)).contents
            if msg.message==0x83 and msg.hWnd in self.desktop.material_handles.values():
                self.desktop.material.native.full_client(msg.hWnd,msg.lParam)
                return True,0
            if msg.hWnd in self.desktop.material_handles.values():
                if msg.message in (0x85,0xae,0xaf):  # Suppress legacy nonclient caption/frame painting.
                    return True,0
                if msg.message==0x86:  # WM_NCACTIVATE: preserve activation without painting a caption.
                    return True,1
        return False,0


class Desktop(QObject):
    incoming = Signal(dict)
    eof = Signal()
    def __init__(self, root, *, read_pipe=True):
        # Use elapsed time for multi-window animation, rather than assuming a
        # continuously advancing vsync clock while tools are shown/hidden.
        os.environ.setdefault('QSG_USE_SIMPLE_ANIMATION_DRIVER','1')
        QQuickWindow.setDefaultAlphaBuffer(True)
        self.app = QGuiApplication.instance() or QGuiApplication(sys.argv)
        super().__init__()
        self.root = Path(root); self.read_pipe = read_pipe; self.windows = {}; self.closing = {}; self.requested = None
        self.stopping = False; self.ready = set(); self.normal_bounds = {}; self.messages = []; self.idle = False
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName('Enco Lite'); self.app.setOrganizationName('EncoLite')
        self.app.setWindowIcon(QIcon(str(root / 'ui/assets/app-icon.ico')))
        font = QFont('Microsoft YaHei UI'); font.setPixelSize(13); self.app.setFont(font)
        QQuickStyle.setStyle('Basic')
        self.material=WindowMaterial();self.material_handles={}
        self.material_events=MaterialEvents(self);self.material_filter_installed=False
        self.bridge = Bridge(self)
        self.bridge.changed.connect(self.update_materials)
        self.engine = QQmlApplicationEngine(); self.engine.rootContext().setContextProperty('backend', self.bridge)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(root / 'ui/qt/App.qml')))
        if self.component.isError(): raise RuntimeError('\n'.join(error.toString() for error in self.component.errors()))
        self.incoming.connect(self.receive); self.eof.connect(self.quit)
        self.notice_timer = QTimer(self); self.notice_timer.setSingleShot(True)
        self.notice_hovered = False
        self.notice_timer.timeout.connect(lambda: self.close_view('notice', reason='timeout'))
        self.quick_idle_timer = QTimer(self); self.quick_idle_timer.setSingleShot(True)
        self.quick_idle_timer.setTimerType(Qt.PreciseTimer)
        self.quick_idle_timer.timeout.connect(self.quick_idle_expired)
        self.quick_idle_config = (False, 30); self.quick_touch_down = False

    def eventFilter(self, watched, event):
        if self.material.supported and event.type() in (QEvent.PlatformSurface,QEvent.WindowStateChange):
            QTimer.singleShot(0,lambda:self.update_materials(force=True))
        if self.quick_idle_config[0] and watched is self.windows.get('quick'):
            kind = event.type()
            if kind == QEvent.TouchBegin: self.quick_touch_down = True
            elif kind in (QEvent.TouchEnd, QEvent.TouchCancel): self.quick_touch_down = False
            if kind in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                        QEvent.MouseButtonDblClick, QEvent.Wheel, QEvent.KeyPress, QEvent.KeyRelease,
                        QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd, QEvent.TouchCancel):
                if self.closing.get('quick', {}).get('reason') == 'idle': self.show('quick')
                else: self.reset_quick_idle()
        return False

    def update_materials(self,force=False):
        wanted=bool(self.windows) and self.material.supported
        if wanted!=self.material_filter_installed:
            if wanted:self.app.installNativeEventFilter(self.material_events)
            else:self.app.removeNativeEventFilter(self.material_events)
            self.material_filter_installed=wanted
        for kind,window in list(self.windows.items()):
            hwnd=int(window.winId());old=self.material_handles.get(kind)
            if old and old!=hwnd:self.material.forget(old)
            self.material_handles[kind]=hwnd
            requested=self.bridge.glassAllowed and bool(window.property('surfaceReady'))
            changing=bool(window.property('nativeGlass'))!=requested
            if changing:window.setProperty('materialChanging',True)
            active=self.material.apply(hwnd,requested,self.bridge.state.get('dark',False),force=force)
            window.setProperty('systemFrame',self.material.frames.get(hwnd,False))
            window.setProperty('nativeGlass',active)
            self.material.decorate(hwnd,bool(window.property('surfaceReady')),force=force)
            if changing:
                QTimer.singleShot(0,lambda w=window,k=kind:w.setProperty('materialChanging',False) if self.windows.get(k) is w else None)

    def update_quick_idle(self):
        seconds = self.bridge.state.get('quick_idle_seconds', 30)
        if type(seconds) is not int or not 5 <= seconds <= 3600: seconds = 30
        config = (self.bridge.state.get('quick_auto_hide', False) is True, seconds)
        if config != self.quick_idle_config:
            self.quick_idle_config = config; self.reset_quick_idle()

    def reset_quick_idle(self):
        self.quick_idle_timer.stop()
        window = self.windows.get('quick'); enabled, seconds = self.quick_idle_config
        if (enabled and window and 'quick' in self.ready and 'quick' not in self.closing
                and not self.stopping and not window.property('quickMenuOpen')):
            self.quick_idle_timer.start(seconds * 1000)

    def quick_idle_expired(self):
        if not self.quick_idle_config[0] or self.stopping or 'quick' not in self.windows or 'quick' in self.closing: return
        if (self.bridge.state.get('busy') or self.quick_touch_down
                or QGuiApplication.mouseButtons() != Qt.NoButton
                or self.windows['quick'].property('quickMenuOpen')):
            self.reset_quick_idle(); return
        self.close_view('quick', reason='idle')

    def send(self, kind, **values):
        message = {'type': kind, **values}; self.messages.append(message)
        if len(self.messages) > 100: self.messages.pop(0)
        if self.read_pipe:
            try: print(json.dumps(message, ensure_ascii=False, separators=(',', ':')), flush=True)
            except (BrokenPipeError, OSError): self.quit()

    def read(self):
        try:
            for line in sys.stdin:
                try: data = json.loads(line)
                except ValueError: continue
                if isinstance(data, dict): self.incoming.emit(data)
        finally: self.eof.emit()

    @Slot(dict)
    def receive(self, message):
        try:
            kind = message.get('type')
            if kind == 'state':
                self.bridge.update(message)
                self.update_quick_idle()
                if self.idle and not self.bridge.state.get('fast_launch', False):
                    self.send('closing'); self.quit()
            elif kind == 'show': self.show(message.get('view', 'main'))
            elif kind == 'toggle_quick':
                self.close_view('quick') if 'quick' in self.windows and 'quick' not in self.closing else self.show('quick')
            elif kind == 'quit': self.quit()
            elif os.environ.get('ENCOLITE_DIAGNOSTICS') == '1':
                if kind == 'inspect': self.inspect(message.get('id', 'qt-inspect'))
                elif kind == 'verify_action': self.bridge.action(message.get('name', ''), message.get('args', []))
        except Exception:
            traceback.print_exc(); self.send('diagnostic', data={'result': 'FAIL', 'error': traceback.format_exc()})

    def inspect(self, identifier):
        self.show('main')
        pages = [0, 1, 5, 4, 6, 2]
        def step(index):
            window = self.windows.get('main')
            if window is None: return
            if index == len(pages):
                window.setProperty('page', 0)
                state = self.bridge.state
                report = {'id': identifier, 'result': 'PASS', 'pages': len(pages),
                          'navigation_items': len(plain(window.property('pages'))), 'sound_subpages': [1, 5],
                          'framework': 'Qt Quick', 'model': state.get('model_name'),
                          'picture': state.get('product_picture'), 'presets': len(state.get('presets') or []),
                          'switches': len(state.get('switches') or []), 'bands': self.bridge.bands.rowCount(),
                          'devices': len(state.get('multi_devices') or []), 'connected': bool(state.get('connected'))}
                if sys.platform == 'win32':
                    from . import windows_shell as s
                    hwnd=int(window.winId())
                    report['caption_absent'] = (self.material.native.caption_hidden(hwnd) if window.property('systemFrame')
                                                else not bool(s.GetWindowLong(hwnd,-16)&0x00C00000))
                self.send('diagnostic', data=report); return
            window.setProperty('page', pages[index])
            def capture():
                directory = os.environ.get('ENCOLITE_CAPTURE_DIR')
                if directory:
                    folder = Path(directory); folder.mkdir(parents=True, exist_ok=True)
                    window.grabWindow().save(str(folder / ('page-' + str(pages[index]) + '.png')))
                step(index + 1)
            QTimer.singleShot(160, capture)
        QTimer.singleShot(300, lambda: step(0))

    def restore(self, window, kind):
        prefs = self.bridge.preferences; saved = prefs.get('qt_' + kind)
        legacy = not bool(saved)
        saved = saved or prefs.get('web_' + kind) or prefs.get(kind + '_window') or {}
        bounds, page = window_state(saved)
        screen = self.app.primaryScreen(); area = screen.availableGeometry()
        width, height = (864, 640) if kind == 'main' else (352, 374) if kind == 'quick' else (360, 192)
        if bounds:
            x, y, width, height, maximized = bounds
            if legacy:
                scale = screen.devicePixelRatio(); x, y, width, height = (round(value / scale) for value in (x, y, width, height))
            screen = next((s for s in self.app.screens() if s.availableGeometry().contains(x, y)), screen)
            area = screen.availableGeometry()
            width = max(740 if kind == 'main' else 352, width); height = max(560 if kind == 'main' else 374, height)
            x, y, width, height, _ = fit_bounds((x, y, width, height, False), (area.left(), area.top(), area.right() + 1, area.bottom() + 1))
        else:
            maximized = False
            x = area.x() + (area.width() - width) // 2; y = area.y() + (area.height() - height) // 2
            if kind != 'main': x = area.right() - width - 13; y = area.bottom() - height - 13
        window.setGeometry(x, y, width, height); window.setProperty('page', page)
        self.normal_bounds[kind] = [x, y, width, height]
        window.setProperty('restoreMaximized', maximized)

    def show(self, kind):
        if kind not in TITLES or self.stopping: return
        self.idle = False
        if kind != 'notice': self.requested = kind
        if kind in self.windows:
            # A pending connection notification must not undo the user's close.
            if kind == 'notice' and self.closing.get(kind, {}).get('reason') not in (None, 'timeout'): return
            self.closing.pop(kind, None); window = self.windows[kind]
            QMetaObject.invokeMethod(window, 'present')
            self.activate(window, kind); return
        window = self.component.createWithInitialProperties({'kind': kind,'systemFrame':self.material.supported})
        if window is None: raise RuntimeError('\n'.join(error.toString() for error in self.component.errors()))
        self.windows[kind] = window
        window.surfaceReadyChanged.connect(self.update_materials)
        window.closingUiChanged.connect(self.update_materials)
        window.installEventFilter(self)
        window.flagsChanged.connect(lambda *_:QTimer.singleShot(0,lambda:self.update_materials(force=True)))
        if kind == 'quick':
            self.quick_touch_down = False
            window.quickMenuOpenChanged.connect(self.reset_quick_idle)
        self.restore(window, kind)
        self.update_materials()
        def remember(*_):
            if self.windows.get(kind) is window and window.windowState() == Qt.WindowNoState:
                rect = window.geometry(); self.normal_bounds[kind] = [rect.x(), rect.y(), rect.width(), rect.height()]
        for signal in (window.xChanged, window.yChanged, window.widthChanged, window.heightChanged):
            signal.connect(lambda *_, callback=remember: QTimer.singleShot(0, callback))
        window.finishedClosing.connect(lambda: self.finish_close(kind, window))
        window._first_frame = lambda: self.first_frame(kind, window)
        # frameSwapped may originate on Qt's render thread. Window properties,
        # native material and QML animation must start on the GUI thread.
        window.frameSwapped.connect(window._first_frame,Qt.QueuedConnection)
        window.setProperty('displayOpacity',.01 if self.bridge.motion else 1)
        if window.property('restoreMaximized'): window.showMaximized()
        else: window.show()
        QTimer.singleShot(1000, lambda: self.first_frame(kind, window) if self.windows.get(kind) is window else None)

    def first_frame(self, kind, window):
        if self.windows.get(kind) is not window or kind in self.ready: return
        self.ready.add(kind)
        self.update_materials(force=True)
        window.frameSwapped.disconnect(window._first_frame)
        # Closing may precede the first frame (including its delayed fallback).
        # present() would stop the close animation and leave closing set forever.
        if kind in self.closing: return
        if kind != 'notice' and self.requested != kind:
            self.close_view(kind, exiting=False, animate=False); return
        QMetaObject.invokeMethod(window, 'present')
        # A suspended compositor can deliver a frame without advancing the
        # animation clock. Never leave the content nearly invisible.
        QTimer.singleShot(650,lambda:QMetaObject.invokeMethod(window,'finishStalledEntrance')
                          if self.windows.get(kind) is window and kind not in self.closing else None)
        self.activate(window, kind)
        if kind != 'notice':
            for old in list(self.windows):
                if old != kind: self.close_view(old, exiting=False)
        # A passive connection notice must not replace the control window's
        # route: the tray uses it to decide whether a click closes quick UI.
        active = self.requested if self.requested in self.windows else kind
        self.send('view', view=active, visible=True)

    def activate(self, window, kind):
        if window.windowState() == Qt.WindowMinimized: window.showNormal()
        window.show()
        if sys.platform == 'win32':
            from . import windows_shell as s
            hwnd = int(window.winId())
            if kind != 'notice': s.activate_window(hwnd)
        elif kind != 'notice': window.raise_(); window.requestActivate()
        if kind == 'notice':
            self.notice_timer.stop()
            if not self.notice_hovered: self.notice_timer.start(5000)
        elif kind == 'quick': self.reset_quick_idle()

    def notice_hover(self, inside):
        self.notice_hovered = bool(inside)
        self.notice_timer.stop()
        if inside and self.closing.get('notice', {}).get('reason') == 'timeout': self.show('notice')
        elif not inside and 'notice' in self.windows and 'notice' not in self.closing: self.notice_timer.start(3000)

    def close_view(self, kind, exiting=True, animate=True, reason='close'):
        window = self.windows.get(kind)
        if not window or kind in self.closing: return
        info = self.closing[kind] = {'exiting': exiting, 'reason': reason}
        if kind == 'notice': self.notice_timer.stop()
        elif kind == 'quick': self.quick_idle_timer.stop()
        if animate and self.bridge.motion and not self.stopping:
            QMetaObject.invokeMethod(window, 'dismiss')
            # Hidden/occluded windows may stop rendering animation frames. A
            # canceled close cannot let this timer destroy a reopened window.
            QTimer.singleShot(350, lambda: self.finish_close(kind, window)
                              if self.windows.get(kind) is window and self.closing.get(kind) is info else None)
        else: self.finish_close(kind, window)

    def finish_close(self, kind, window):
        if self.windows.get(kind) is not window or kind not in self.closing: return
        info = self.closing.pop(kind)
        if kind == 'quick':
            self.quick_idle_timer.stop(); self.quick_touch_down = False
        if kind == 'notice':
            self.notice_timer.stop(); self.notice_hovered = False
        if kind != 'notice':
            maximized = window.windowState() == Qt.WindowMaximized
            rect = window.geometry()
            bounds = (self.normal_bounds.get(kind, [rect.x(),rect.y(),rect.width(),rect.height()]) if maximized else [rect.x(),rect.y(),rect.width(),rect.height()]) + [maximized]
            self.send('action', name='save_window', args=[kind, bounds, window.property('page')], frontend='qt')
        if kind == 'main': self.bridge.action('end_hotkey_capture', [])
        window.hide()  # Keep native client-area handling installed until hidden.
        self.windows.pop(kind); self.ready.discard(kind)
        hwnd=self.material_handles.pop(kind,None)
        if hwnd:self.material.forget(hwnd)
        self.update_materials()
        window.deleteLater()
        if not self.windows and info['exiting'] and not self.stopping:
            if self.bridge.state.get('fast_launch', False):
                self.idle = True; self.requested = None; self.send('idle')
            else:
                self.send('closing'); self.quit()
        elif self.windows:
            active = self.requested if self.requested in self.windows else next(iter(self.windows))
            self.send('view', view=active, visible=True)

    def quit(self):
        if self.stopping: return
        self.stopping = True; self.notice_timer.stop(); self.quick_idle_timer.stop()
        for kind in list(self.windows):
            if kind in self.closing: self.finish_close(kind, self.windows[kind])
            else: self.close_view(kind, exiting=False, animate=False)
        # Window close requests intentionally go to the tray; exit the event
        # loop explicitly after disposing windows instead of requesting Close.
        self.app.exit(0)

    def run(self):
        sys.stdin.reconfigure(encoding='utf-8'); sys.stdout.reconfigure(encoding='utf-8')
        if self.read_pipe: threading.Thread(target=self.read, name='EncoLite-state', daemon=True).start()
        try: return self.app.exec()
        finally: self.quit()
