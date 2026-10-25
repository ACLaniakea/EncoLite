"""The tray and Bluetooth session survive; graphical windows do not stay resident."""
from pathlib import Path
import json
import os
import subprocess
import sys
import threading
import time

from .controller import Controller
from .json_view import JsonView
from .native_loop import NativeLoop
from .notifications import ConnectionNoticePolicy
from .presentation import JsonPresentation
from .preferences import data_directory,window_state


class NativeDesktop:
    ACTIONS={name for name in '''change_noise change_preset change_feature change_connection
        refresh scan select_device next_preset change_theme change_theme_mode change_fast_mode change_connection_popup
        select_custom edit_custom_name edit_gain write_custom change_spatial change_game
        find_device operate_multi select_model reset change_accent_mode change_accent_color change_fast_launch change_quick_topmost change_quick_auto_hide change_quick_idle_seconds'''.split()}

    def __init__(self, root, args, *, startup=None):
        from . import windows_shell as shell
        self.root,self.args,self.shell=root,args,shell
        self.loop=NativeLoop()
        self.gui=None
        self.gui_closing=False
        self.pending_view=None
        self.active_view=None
        self.exiting=False
        self.hotkey_result=None
        self.notice_policy=ConnectionNoticePolicy()
        self.view=JsonView()
        from .autostart import WindowsStartup
        self.startup=startup if startup is not None else WindowsStartup(root) if not args.fixture else None
        self.refresh_autostart()
        self.report={'checks':[],'errors':[],'gui_starts':0,'ui_closed':0}
        self.started=time.monotonic()
        session=None
        if args.fixture:
            from .session import DemoSession
            session=DemoSession()
        self.controller=Controller(preferences=data_directory()/'preferences.json',session=session,
            dispatch=self.loop.post,presentation=JsonPresentation(),scheduler=self.loop)
        self.tray=shell.Tray(root/'ui/assets/app-icon.ico',self.toggle_quick,
            lambda:self.show('main'),self.quit,self.controller.change_noise,self.loop.post,
            test_mode=getattr(args,'isolated_tray',False),
            noise_options=self.noise_options,on_show_quick=lambda:self.show('quick'),on_dispatch=self.loop.drain,
            on_settings_changed=self.system_settings_changed,on_hotkey=self.hotkey_message)
        self.loop.hwnd=self.tray.hwnd
        from .hotkeys import Hotkeys,WindowsRegistration
        self.hotkeys=Hotkeys(WindowsRegistration(self.tray.hwnd),self.controller.preference_data.get('hotkeys'),
            self.save_hotkeys,self.activate_shortcut)
        self.capture_timer=self.loop.timer()
        self.controller.on_changed=self.publish
        self.controller.attach(self.view)

    def noise_options(self):
        from .oppo_features import NOISE_TITLES
        session=self.controller.session
        if not session.connected or self.controller.busy:return []
        modes=session.noise_modes if self.controller.live else ('smart','transparency','off')
        return [(key,label) for key,label in NOISE_TITLES.items() if key in modes]

    def payload(self):
        session=self.controller.session
        return {'type':'state','state':self.view.snapshot(),
            'preferences':self.controller.preference_data,
            'hotkeys':{**self.hotkeys.snapshot(),'result':self.hotkey_result},
            'ready':bool(getattr(session,'ready',session.connected) and session.connected),
            'fixture':self.args.fixture}

    def refresh_autostart(self):
        self.view.autostart_enabled=False
        self.view.autostart_available=self.startup is not None
        self.view.autostart_error=''
        if self.startup is not None:
            try:self.view.autostart_enabled=self.startup.enabled()
            except OSError:
                self.view.autostart_available=False
                self.view.autostart_error='无法读取 Windows 启动项'

    def system_settings_changed(self):
        self.refresh_autostart()
        self.controller.refresh_system_appearance()
        self.publish()

    def change_autostart(self,enabled):
        if self.startup is None:raise OSError('当前运行环境不支持开机自启动')
        try:self.startup.set_enabled(enabled)
        finally:self.refresh_autostart()
        self.controller.set_status('已开启开机自启动' if enabled else '已关闭开机自启动')
        self.controller.sync()

    def publish(self):
        if self.exiting:return
        session=self.controller.session
        batteries=' / '.join(f'{label} {b.percent}%' for key,label in (('left','L'),('right','R'),('case','C'))
            if (b:=session.battery.get(key)) and session.connected)
        self.tray.update_tip((getattr(session,'device_name','耳机')+'\n'+(batteries or '已断开'))[:127])
        self.send(self.payload())
        ready=bool(getattr(session,'ready',session.connected) and session.connected)
        token=(getattr(session,'_generation',0),getattr(session,'device_name',''))
        notice=self.notice_policy.observe(ready,token,busy=self.controller.busy,
            enabled=self.controller.connection_popup and not self.args.fixture)
        if notice and self.active_view!='quick':self.show('notice')

    def gui_command(self):
        host=self.root/'python/pythonw.exe'
        if not host.exists():host=self.root/'.tools/python-3.13.17-embed-amd64/pythonw.exe'
        if not host.exists():raise FileNotFoundError('缺少官方 Python 运行环境')
        return [str(host),str(self.root/'qt_entry.py')]

    def send(self, data):
        process=self.gui
        if not process or process.poll() is not None:return False
        return process._encolite_channel.send(data)

    def show(self, kind):
        if self.exiting:return
        if kind not in ('main','quick','notice'):return
        if kind=='main':self.refresh_autostart()
        if self.gui_closing:
            self.pending_view=kind
            return
        if self.gui is None or self.gui.poll() is not None:
            error_path=data_directory()/'interface-error.log'
            error_path.parent.mkdir(parents=True,exist_ok=True)
            self._gui_log=error_path.open('w',encoding='utf-8')
            env={**os.environ,'ENCOLITE_ROOT':str(self.root),'DOTNET_CLI_TELEMETRY_OPTOUT':'1'}
            self.gui=subprocess.Popen(self.gui_command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=self._gui_log,text=True,encoding='utf-8',bufsize=1,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW)
            process=self.gui
            from .gui_channel import GuiChannel
            process._encolite_channel=GuiChannel(process)
            self.report['gui_starts']+=1
            threading.Thread(target=self.read_gui,args=(process,self._gui_log),name='EncoLite-UI',daemon=True).start()
        self.active_view=kind if kind!='notice' else self.active_view
        self.view.visible=True
        self.send(self.payload())
        if kind!='notice':
            self.shell.AllowSetForegroundWindow(self.gui.pid)
        self.send({'type':'show','view':kind})
        self.controller.refresh_background(force=True)

    def read_gui(self, process, log):
        try:
            for line in process.stdout:
                try:data=json.loads(line)
                except (ValueError,TypeError):continue
                self.loop.post(lambda data=data:self.receive(data))
        finally:
            process.wait()
            process._encolite_channel.stop()
            log.close()
            self.loop.post(lambda:self.gui_exited(process))

    def gui_exited(self, process):
        if process is not self.gui:return
        self.gui=None
        self.gui_closing=False
        self.active_view=None
        self.view.visible=False
        self.end_hotkey_capture()
        self.report['ui_closed']+=1
        if self.exiting:
            if hasattr(self,'shutdown_timer'):self.shutdown_timer.stop()
            self.loop.quit()
            return
        if process.returncode:
            self.report['errors'].append(f'UI exit {process.returncode}')
            if not self.exiting:
                self.controller.set_status('界面启动失败，请查看 interface-error.log')
        pending,self.pending_view=self.pending_view,None
        if pending and not self.exiting:self.show(pending)

    def receive(self, message):
        if not isinstance(message,dict):return
        if self.exiting and not (message.get('type')=='action' and message.get('name')=='save_window'):return
        kind=message.get('type')
        if kind=='closing':
            self.gui_closing=True
            return
        if kind=='idle':
            self.active_view=None;self.view.visible=False;self.end_hotkey_capture()
            return
        if kind=='view':
            self.active_view=message.get('view')
            if self.active_view!='main':self.end_hotkey_capture()
            self.view.visible=bool(message.get('visible',True))
            return
        if kind=='diagnostic' and (self.args.fixture or self.args.test_report):
            self.report.setdefault('ui',[]).append(message.get('data'))
            return
        if kind!='action':return
        name=message.get('name')
        values=message.get('args',[])
        if not isinstance(values,list) or len(values)>3:return
        try:
            if name=='set_hotkey' and len(values)==3:
                shortcut,value,request=values
                if not isinstance(request,str) or len(request)>64:return
                try:
                    self.hotkeys.set_binding(shortcut,value)
                    self.hotkey_result={'request':request,'ok':True,'action':shortcut}
                    self.controller.set_status('快捷键已保存')
                except (TypeError,ValueError,OSError) as error:
                    self.hotkey_result={'request':request,'ok':False,'action':shortcut,'error':str(error)}
                    self.controller.set_status('操作未完成 · '+str(error))
                self.controller.sync()
            elif name=='change_autostart' and len(values)==1:self.change_autostart(values[0])
            elif name=='set_hotkeys_enabled' and len(values)==1:self.hotkeys.set_enabled(values[0])
            elif name=='begin_hotkey_capture' and not values:
                self.hotkeys.suspend();self.capture_timer.start(45,self.end_hotkey_capture)
            elif name=='end_hotkey_capture' and not values:self.end_hotkey_capture()
            elif name in self.ACTIONS:
                getattr(self.controller,name)(*values)
            elif name=='show' and len(values)==1:self.show(values[0])
            elif name=='quit':self.quit()
            elif name=='save_window' and len(values)==3:
                window,bounds,page=values
                if window not in ('main','quick'):return
                placement,valid_page=window_state({'bounds':bounds,'page':page})
                if placement:
                    prefix='qt_' if message.get('frontend')=='qt' else 'web_'
                    self.controller.save_preferences(**{prefix+window:{'bounds':list(placement),'page':valid_page}})
            self.publish()
        except (TypeError,ValueError,KeyError,OSError) as error:
            self.controller.set_status('操作未完成 · '+str(error))
            self.controller.sync()

    def end_hotkey_capture(self):
        self.capture_timer.stop()
        if self.hotkeys.suspended:
            self.hotkeys.resume()
            self.publish()

    def save_hotkeys(self,config):
        from .preferences import write_preferences
        updated={**self.controller.preference_data,'hotkeys':config}
        write_preferences(self.controller.preferences,updated)
        self.controller.preference_data=updated

    def hotkey_message(self,identifier,packed):
        if not self.exiting:self.hotkeys.handle(identifier,packed)

    def activate_shortcut(self,name):
        from .hotkeys import execute_shortcut
        execute_shortcut(self.controller,name,self.show)
        self.publish()

    def toggle_quick(self):
        if self.gui and self.active_view=='quick':self.send({'type':'toggle_quick'})
        else:self.show('quick')

    def run(self):
        if not self.args.tray_only:self.show('quick' if self.args.quick else 'main')
        self.controller.start()
        if self.args.test_timeout:
            self._test_timer=self.loop.timer()
            self._test_timer.start(self.args.test_timeout,self.quit)
        self.loop.run()

    def quit(self):
        if self.exiting:return
        self.exiting=True
        if self.gui and self.gui.poll() is None:
            # Keep draining the pipe until Qt has saved its bounds and exited.
            self.send({'type':'quit'})
            self.shutdown_timer=self.loop.timer()
            self.shutdown_timer.start(2.5,self.loop.quit)
        else:self.loop.quit()

    def close(self):
        self.exiting=True
        self.capture_timer.stop()
        self.hotkeys.close()
        self.controller.close()
        if self.gui:
            self.send({'type':'quit'})
            try:self.gui.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.gui.terminate();self.gui.wait(timeout=5)
        self.tray.close()
        if self.args.test_report:
            self.report.update(elapsed=time.monotonic()-self.started,
                slint_loaded=any(key=='slint' or key.startswith('slint.') for key in sys.modules),
                qt_loaded=any(key=='PySide6' or key.startswith('PySide6.') for key in sys.modules),
                connected=self.controller.session.connected)
            self.args.test_report.parent.mkdir(parents=True,exist_ok=True)
            self.args.test_report.write_text(json.dumps(self.report,ensure_ascii=False,indent=2),'utf-8')
