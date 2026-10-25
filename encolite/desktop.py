"""Lazy windows share one controller and one earphone session."""
from pathlib import Path
import sys
import os
from datetime import timedelta
from .notifications import ConnectionNoticePolicy


class Desktop:
    MAIN_TITLE = "Enco Lite · OPPO 耳机助手"
    QUICK_TITLE = "Enco Lite · 快捷控制"
    NOTICE_TITLE = "Enco Lite · 连接提示"

    def __init__(self, root: Path, controller, *, tray_enabled=True, test_mode=False):
        import slint
        from slint._native import native
        self.slint, self.native = slint, native
        self.root, self.controller = root, controller
        self.main = None
        self.quick = None
        self.quick_hwnd = None
        self.main_hwnd = None
        self.anchor = None
        self.tray = None
        self.exiting = False
        self.native_shell = None
        self.notice=None
        self._notice_policy=ConnectionNoticePolicy()
        self._notifications_enabled=not test_mode
        self._notice_timer=slint.Timer()
        self._main_activation_pending=False
        self._main_activation_attempts=0
        self._main_restoring=False
        self._chrome_timers={}
        self._pending_popups={}
        self._popup_attempts={}
        from .preferences import window_state
        self._main_placement,self._main_page=window_state(controller.preference_data.get("main_window"))
        self._normal_placement=self._main_placement
        self._quick_placement,_=window_state(controller.preference_data.get("quick_window"))
        self._last_dark=controller.dark
        if sys.platform == 'win32' and not os.environ.get('SLINT_BACKEND','').startswith('headless'):
            from . import windows_shell
            self.native_shell=windows_shell
        controller.on_changed=self.state_changed
        if self.native_shell and tray_enabled:
            from . import windows_shell
            self.native_shell = windows_shell
            # Slint Python 1.18 has no public persistent-loop flag. Keep one
            # tiny logical window alive; its OS window is hidden and has no
            # taskbar button. All real views can then be released while in tray.
            self.anchor = slint.load_file(root/"ui/anchor.slint").RuntimeAnchor()
            self.anchor.show()
            windows_shell.style_window("Enco Lite · runtime", tool=True, hidden=True)
            try:
                self.tray = windows_shell.Tray(root/"ui/assets/app-icon.ico",
                    self.toggle_quick, self.show_main, self.quit,
                    controller.change_noise, native.invoke_from_event_loop, test_mode=test_mode, noise_options=self.noise_options, on_show_quick=self.show_quick)
            except Exception:
                self.anchor.hide()
                self.anchor = None
                raise
            self.update_tip()

    def noise_options(self):
        from .oppo_features import NOISE_TITLES
        s=self.controller.session
        modes=s.noise_modes if self.controller.live else ("smart","transparency","off")
        return [(key,title) for key,title in NOISE_TITLES.items() if key in modes] if s.connected and not self.controller.busy else []

    def update_tip(self):
        if self.tray:
            session = self.controller.session
            parts = []
            if session.connected:
                for key, label in (("left","L"),("right","R"),("case","C")):
                    battery = session.battery.get(key)
                    if battery:
                        parts.append(f"{label} {battery.percent}%")
            name = getattr(session, "device_name", "OPPO Enco X3")
            self.tray.update_tip(name + "\n" + (" / ".join(parts) or "已断开"))

    def state_changed(self):
        self.update_tip()
        if self._last_dark!=self.controller.dark:
            self._last_dark=self.controller.dark
            for title,window in ((self.MAIN_TITLE,self.main),(self.QUICK_TITLE,self.quick),(self.NOTICE_TITLE,self.notice)):
                if window:
                    self.round_window(title)
        session=self.controller.session
        ready=getattr(session,'ready',session.connected) and session.connected
        token=(getattr(session,'_generation',0),getattr(session,'device_name','OPPO Enco X3'))
        show=self._notice_policy.observe(ready,token,busy=self.controller.busy,
            enabled=self._notifications_enabled and self.controller.connection_popup)
        if self.notice is not None and (not ready or not self.controller.connection_popup):
            self.close_notice()
        if show and self.native_shell and self.quick is None:
            self.show_notice()
        if self.notice:
            self.notice.dark=self.controller.dark
            self.notice.battery_text=self._battery_text()

    def _battery_text(self):
        return ' · '.join(f'{label} {battery.percent}%' for key,label in
            (('left','左耳'),('right','右耳'),('case','充电盒'))
            if (battery:=self.controller.session.battery.get(key))) or '正在更新电量'

    def round_window(self,title):
        if not self.native_shell or self.exiting:
            return
        timer=self._chrome_timers.get(title)
        if timer is None:
            timer=self.slint.Timer()
            self._chrome_timers[title]=timer
        timer.start(self.slint.TimerMode.SingleShot,timedelta(milliseconds=24),
            lambda:self._apply_chrome(title))

    def _apply_chrome(self,title):
        if self.exiting:
            return
        maximized=bool(self.main and self.main.window_maximized) if title==self.MAIN_TITLE else False
        hwnd=self.native_shell.style_window(title,tool=title!=self.MAIN_TITLE,
            passive=title==self.NOTICE_TITLE,maximized=maximized)
        if title==self.MAIN_TITLE and hwnd:
            self.main_hwnd=hwnd
        if title==self.MAIN_TITLE:
            self._activate_main()
        if title in self._pending_popups:
            if not self._configure_popup(title):
                count=self._popup_attempts.get(title,0)+1
                self._popup_attempts[title]=count
                if count<6:
                    self.round_window(title)
        if title==self.MAIN_TITLE and self.main and not maximized and not self.main.window_minimized:
            self._normal_placement=self.native_shell.window_placement(title)

    def _restore_main(self,window,placement):
        if self.main is window and not self.exiting:
            self.native_shell.restore_placement(self.MAIN_TITLE,placement)
            self._main_restoring=False
            if placement[4]:
                # Moving/resizing queues a normal-state update in winit. Let it
                # settle before maximizing, otherwise that update wins the race.
                self.slint.Timer.single_shot(timedelta(milliseconds=40),
                    lambda:setattr(window,'window_maximized',True)
                    if self.main is window and not self.exiting else None)
            self.round_window(self.MAIN_TITLE)

    def _activate_main(self):
        if not self.main or not self._main_activation_pending or self._main_restoring:
            return
        if self.main_hwnd:
            if (not self.main.window_minimized and not self.native_shell.IsIconic(self.main_hwnd)
                    and self.native_shell.GetForegroundWindow()==self.main_hwnd):
                self._main_activation_pending=False
                self.close_quick()
                return
            self.native_shell.activate_window(self.main_hwnd)
        self._main_activation_attempts+=1
        if self._main_activation_attempts<8:
            self.round_window(self.MAIN_TITLE)
        else:
            self._main_activation_pending=False
            self.close_quick()

    def _stop_chrome(self,title):
        self._pending_popups.pop(title,None)
        self._popup_attempts.pop(title,None)
        timer=self._chrome_timers.pop(title,None)
        if timer:
            timer.stop()

    def _configure_popup(self,title):
        pending=self._pending_popups.get(title)
        if not pending:
            return True
        window,foreground,placement,activate=pending
        current=self.quick if title==self.QUICK_TITLE else self.notice
        if current is not window:
            self._pending_popups.pop(title,None)
            return True
        hwnd=self.native_shell.position_popup(title,activate=activate,reference=foreground)
        if not hwnd:
            return False
        if placement:
            self.native_shell.restore_placement(title,placement)
        if title==self.QUICK_TITLE:
            self.quick_hwnd=hwnd
        self._pending_popups.pop(title,None)
        self._popup_attempts.pop(title,None)
        return True

    def show_notice(self):
        if self.exiting or not self.native_shell:
            return
        self.close_notice()
        foreground=self.native_shell.GetForegroundWindow()
        window=self.slint.load_file(self.root/'ui/notice.slint',style='fluent').ConnectionNotice()
        session=self.controller.session
        window.dark=self.controller.dark
        window.model_name=getattr(session,'device_name','OPPO Enco X3')
        window.battery_text=self._battery_text()
        from .images import product_image
        from .preferences import image_directory
        identifier=(session.profile or {}).get('id',session.product_id) if self.controller.live else '067410'
        path=product_image(self.root,identifier,image_directory())
        try:window.product_picture=self.slint.Image.load_from_path(path)
        except Exception:window.product_picture=self.slint.Image.load_from_path(product_image(self.root,''))
        window.dismiss=self.close_notice
        window.open_controls=self.show_quick
        window.hover_changed=self._notice_hover
        self.notice=window
        self._pending_popups[self.NOTICE_TITLE]=(window,foreground,None,False)
        window.show()
        self._configure_popup(self.NOTICE_TITLE)
        self.round_window(self.NOTICE_TITLE)
        self._notice_timer.start(self.slint.TimerMode.SingleShot,timedelta(seconds=5),self.close_notice)

    def _notice_hover(self,hovered):
        if hovered:
            self._notice_timer.stop()
        elif self.notice:
            self._notice_timer.start(self.slint.TimerMode.SingleShot,timedelta(seconds=3),self.close_notice)

    def close_notice(self):
        self._notice_timer.stop()
        self._stop_chrome(self.NOTICE_TITLE)
        window,self.notice=self.notice,None
        if window:
            window.hide()

    def show_main(self):
        if self.exiting:
            return
        self.close_notice()
        created=self.main is None
        if created:
            self.main = self.slint.load_file(self.root/"ui/app.slint", style="fluent").AppWindow()
            self.controller.attach(self.main)
            self.main.geometry_changed = lambda:self.round_window(self.MAIN_TITLE)
            self.main.dismiss = self.hide_main if self.tray else self.quit
            self.main.show_quick = self.show_quick
            self.main.quit_requested = self.quit
            self.main.page=self._main_page
        self.main.window_minimized=False
        self.main.show()
        if self.native_shell:
            self._main_activation_pending=True
            self._main_activation_attempts=0
            self.main_hwnd = self.native_shell.style_window(self.MAIN_TITLE)
            if created and self._main_placement:
                self._main_restoring=True
                window=self.main
                placement=self._main_placement
                # Winit applies the initial native position on its first frame.
                # Restore afterwards, once, so the initial cascade cannot win.
                self.slint.Timer.single_shot(timedelta(milliseconds=50),
                    lambda:self._restore_main(window,placement))
            self._activate_main()
            self.round_window(self.MAIN_TITLE)
        else:
            self.close_quick()

    def hide_main(self):
        if self.main is None:
            return
        self._main_page=self.main.page
        if self.native_shell:
            placement=self.native_shell.window_placement(self.MAIN_TITLE)
            if self.main.window_maximized:
                placement=self._normal_placement or placement
                if placement:placement=(*placement[:4],True)
            elif placement:
                placement=(*placement[:4],False)
            self._main_placement=placement or self._main_placement
            self.controller.save_preferences(main_window={'bounds':list(self._main_placement) if self._main_placement else None,'page':self._main_page})
        self._stop_chrome(self.MAIN_TITLE)
        self._main_activation_pending=False
        self._main_restoring=False
        window,self.main = self.main,None
        self.main_hwnd = None
        self.controller.detach(window)
        window.hide()

    def show_quick(self):
        if self.exiting:
            return
        self.close_notice()
        created=self.quick is None
        if created:
            self.quick = self.slint.load_file(self.root/"ui/quick.slint", style="fluent").QuickWindow()
            self.controller.attach(self.quick)
            self.quick.geometry_changed = lambda:self.round_window(self.QUICK_TITLE)
            self.quick.dismiss = self.close_quick
            self.quick.show_main = self.show_main
        self.quick.show()
        # Keep at least one real window visible on platforms without tray support.
        if self.tray:
            self.hide_main()
        if self.native_shell:
            if created:
                self._pending_popups[self.QUICK_TITLE]=(self.quick,None,self._quick_placement,True)
                self._configure_popup(self.QUICK_TITLE)
            elif self.quick_hwnd:
                self.native_shell.activate_window(self.quick_hwnd)
            self.round_window(self.QUICK_TITLE)

    def toggle_quick(self):
        if self.quick is None:
            self.show_quick()
        else:
            self.close_quick()

    def close_quick(self):
        if self.quick is None:
            return
        if self.native_shell:
            self._quick_placement=self.native_shell.window_placement(self.QUICK_TITLE) or self._quick_placement
            if self._quick_placement:
                self.controller.save_preferences(quick_window={'bounds':list(self._quick_placement)})
        self._stop_chrome(self.QUICK_TITLE)
        window,self.quick = self.quick,None
        self.quick_hwnd = None
        self.controller.detach(window)
        window.hide()

    def quit(self):
        if self.exiting:
            return
        self.exiting=True
        self.native.quit_event_loop()

    def close(self):
        self.exiting=True
        self.controller.on_changed=None
        self.close_notice()
        for timer in self._chrome_timers.values():
            timer.stop()
        self._chrome_timers.clear()
        self.close_quick()
        self.hide_main()
        if self.tray:
            self.tray.close()
            self.tray=None
        if self.anchor:
            self.anchor.hide()
            self.anchor=None
