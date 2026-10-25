"""UI-thread controller. All Bluetooth work runs on one bounded worker."""
from pathlib import Path
import json
import sys
import threading

from .protocol import FEATURES, PRESETS


from .advanced_controller import AdvancedController


class Controller(AdvancedController):
    def __init__(self, window=None, preferences=None, session=None, dispatch=None, *, presentation=None, scheduler=None):
        from .live_session import LiveSession
        from .presentation import SlintPresentation, SlintScheduler
        self.presentation=presentation if presentation is not None else SlintPresentation()
        self.scheduler=scheduler if scheduler is not None else SlintScheduler()
        self.windows=[]
        self.preferences=preferences
        self.dark=False
        self.connection_popup=True
        self.cancel_requested=False
        self._connect_cancel=None
        self.status="尚未连接耳机"
        self.anc_level="smart"
        self.on_changed=None
        self.busy=False
        self.connecting=False
        self.stopped=False
        self.want_connection=False
        self.devices=[]
        self.device_index=-1
        self.dispatch=dispatch or (lambda fn: fn())
        self.session=session if session is not None else LiveSession(self._changed_from_worker)
        self.live=bool(getattr(self.session,"is_live",False))
        self._notification_lock=threading.Lock()
        self._notification_pending=False
        self._preset_signature=None
        self._preset_model=None
        self._preset_factory=None
        self._device_signature=None
        self._device_model=None
        self._hero_image=None
        self._image_key=None
        self._retry_delay=2
        self._retry_timer=None
        self._refresh_timer=None
        self._refreshing=False
        self._executor=None
        if self.live:
            from concurrent.futures import ThreadPoolExecutor
            self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="EncoLite-Control")
        from .preferences import read_preferences
        self.preference_data=read_preferences(preferences)
        from .appearance import saved_theme_mode,read_system_appearance,saved_accent,read_system_accent,DEFAULT_ACCENT
        self.theme_mode=saved_theme_mode(self.preference_data)
        self.system_dark,self.system_motion=read_system_appearance()
        self.accent_mode,self.accent_color=saved_accent(self.preference_data)
        self.system_accent=read_system_accent() if self.accent_mode=='system' else DEFAULT_ACCENT
        self.dark=self.system_dark if self.theme_mode=='system' else self.theme_mode=='dark'
        value=self.preference_data.get('fast_mode',False)
        self.fast_mode=value if type(value) is bool else False
        value=self.preference_data.get('fast_launch',False)
        self.fast_launch=value if type(value) is bool else False
        value=self.preference_data.get('quick_topmost',True)
        self.quick_topmost=value if type(value) is bool else True
        value=self.preference_data.get('quick_auto_hide',False)
        self.quick_auto_hide=value if type(value) is bool else False
        value=self.preference_data.get('quick_idle_seconds',30)
        self.quick_idle_seconds=value if type(value) is int and 5<=value<=3600 else 30
        value=self.preference_data.get('connection_popup',True)
        self.connection_popup=value if isinstance(value,bool) else True
        self.init_advanced()
        if window is not None:
            self.attach(window)

    def attach(self,window):
        self.windows.append(window)
        for callback,handler in (("change_noise",self.change_noise),("change_preset",self.change_preset),
                ("change_feature",self.change_feature),("change_connection",self.change_connection),
                ("refresh_device",self.refresh),("change_theme",self.change_theme),
                ("reset_demo",self.reset),("scan_devices",self.scan),
                ("select_device",self.select_device),("next_preset",self.next_preset),("change_connection_popup",self.change_connection_popup),
                ("select_custom",self.select_custom),("edit_custom_name",self.edit_custom_name),
                ("edit_gain",self.edit_gain),("write_custom",self.write_custom),
                ("change_spatial",self.change_spatial),("change_game",self.change_game),
                ("find_device",self.find_device),("operate_multi",self.operate_multi),
                ("select_model",self.select_model)):
            if hasattr(window,callback):
                setattr(window,callback,handler)
        self.sync()
        self.refresh_background(force=True)

    def detach(self,window):
        self.windows.remove(window)
        if not self.windows:
            self._hero_image=None
            self._image_key=None

    def set_status(self,value):
        self.status=value
        for window in self.windows:
            window.status=value

    def _changed_from_worker(self):
        if self.stopped:
            return
        with self._notification_lock:
            if self._notification_pending:
                return
            self._notification_pending=True
        self.dispatch(self._drain_notifications)

    def _drain_notifications(self):
        with self._notification_lock:
            self._notification_pending=False
        if self.stopped:
            return
        if self.live and not self.session.connected and not self.busy:
            if self.session.error:
                self.set_status(self.session.error)
            self._schedule_reconnect()
        self.sync()
        if self.live and self.session.dirty:
            self.refresh_background()

    def _presets(self):
        return self.session.presets if self.live else [{"id":i,"name":n} for i,n in PRESETS]

    def sync(self):
        session=self.session
        if session.noise and session.noise not in ("off","transparency","vocal"):
            self.anc_level=session.noise
        if self.live and session.noise_modes and self.anc_level not in session.noise_modes:
            self.anc_level=next((m for m in session.noise_modes if m not in ("off","transparency","vocal")),"")
        presets=self._presets()
        if self.windows:
            signature=tuple((p["id"],p["name"]) for p in presets)
            if signature!=self._preset_signature:
                self._preset_signature=signature
                self._preset_model=self.presentation.model([dict(id=p["id"],name=p["name"],detail="自定义音效" if p.get("custom") else "原厂音效") for p in presets], 'PresetItem')
            names=tuple(d.name for d in self.devices)
            if names!=self._device_signature:
                self._device_signature=names
                self._device_model=self.presentation.model(names)
        for window in self.windows:
            self.sync_window(window)
        if self.on_changed:
            self.on_changed()

    def sync_window(self,w):
        s=self.session
        w.connected=s.connected
        w.noise=s.noise
        w.anc_level=self.anc_level
        w.dark=self.dark
        for key in ('theme_mode','system_dark','system_motion','fast_mode','fast_launch','quick_topmost','quick_auto_hide','quick_idle_seconds','accent_mode','accent_color','system_accent'):
            if hasattr(w,key):setattr(w,key,getattr(self,key))
        if hasattr(w,'palette'):
            from .appearance import accent_palette
            w.palette=accent_palette(self.system_accent if self.accent_mode=='system' else self.accent_color,self.dark)
        w.status=self.status
        if hasattr(w,"status_error"):
            w.status_error=self.status.startswith("操作未完成")
        w.busy=self.busy
        w.connecting=self.connecting
        if hasattr(w,"cancelling"):
            w.cancelling=self.cancel_requested
        if hasattr(w,"connection_popup"):
            w.connection_popup=self.connection_popup
        w.preset=s.preset
        w.wear=s.features.get(4,False)
        w.dual=s.features.get(0x11,False)
        w.model_name=s.device_name if self.live else "OPPO Enco X3"
        w.firmware=s.firmware if self.live else ""
        if hasattr(w,'product_picture'):
            from .images import product_image
            from .preferences import image_directory
            identifier=(s.profile or {}).get('id',s.product_id) if self.live and s.connected else '067410' if not self.live and s.connected else ''
            root=Path(__file__).resolve().parents[1]
            custom=image_directory()
            path=product_image(root,identifier,custom)
            if self._image_key!=str(path):
                try:
                    self._hero_image=self.presentation.image(path)
                except Exception:
                    self._hero_image=self.presentation.image(product_image(root,''))
                self._image_key=str(path)
            w.product_picture=self._hero_image
        modes=s.noise_modes if self.live else {"off","transparency","smart","light","moderate","deep"}
        for mode in ("off","transparency","smart","light","moderate","deep"):
            setattr(w,"can_"+mode,s.connected and not self.busy and mode in modes)
        w.can_anc=any(m not in ("off","transparency","vocal") for m in modes) and s.connected and not self.busy
        w.can_equalizer=(s.connected and bool(s.presets) and (s.eq_available or s.game_sound is not None) if self.live else s.connected) and not self.busy
        w.can_wear=(s.feature_available("wear") if self.live else s.connected) and not self.busy
        w.can_dual=(s.feature_available("dual") if self.live else s.connected) and not self.busy
        w.presets=self._preset_model
        presets=self._presets()
        w.preset_name=next((p["name"] for p in presets if p["id"]==s.preset),"—" if s.preset<0 else "自定义音效")
        if hasattr(w,"device_names"):
            w.device_names=self._device_model
            w.device_index=self.device_index
        for key in ("left","right","case"):
            battery=s.battery.get(key) if s.connected else None
            setattr(w,key+"_value",f"{battery.percent}%" if battery else "—")
            setattr(w,key+"_charging",bool(battery and battery.charging))
            setattr(w,key+"_level",battery.percent/100 if battery else 0)
        if hasattr(w,'battery_layout'):
            profile=(s.profile or {}) if self.live and s.connected else {}
            w.battery_layout='SingleBattery' if profile.get('battery_layout')=='SingleBattery' or profile.get('form_factor')=='N' else 'DualEarWithCase'
            w.single_battery_key=next((key for key in ('left','right','case') if s.battery.get(key)),'left')
        w.trace=s.trace[-1] if s.trace else ""
        self.sync_advanced(w)

    def perform(self,function,message,*,then=None,quiet=False):
        if self.stopped:
            return
        if not self.live:
            try:
                value=function()
                self.sync()
                self.set_status(message)
                if then:
                    then(value)
            except (OSError,ConnectionError,ValueError,KeyError) as error:
                self.sync()
                self.set_status("操作未完成 · "+str(error))
            return
        if self.busy:
            if not quiet:
                self.set_status("正在处理上一次操作，请稍候")
            return
        self.busy=True
        if not quiet:
            self.set_status("正在读取耳机…" if not self.connecting else "正在连接耳机…")
        self.sync()
        future=self._executor.submit(function)
        future.add_done_callback(lambda f:None if self.stopped else self.dispatch(lambda:self._finish(f,message,then,quiet)))

    def _finish(self,future,message,then,quiet):
        if self.stopped:
            return
        self.busy=False
        self.connecting=False
        cancelled=self.cancel_requested
        self.cancel_requested=False
        try:
            value=future.result()
            if cancelled and self.session.connected:
                self.perform(self.session.disconnect,'已取消连接')
                return
            if cancelled:
                message='已取消连接'
            self._retry_delay=2
            if not quiet:
                self.set_status(message)
            self.sync()
            if then:
                then(value)
        except Exception as error:
            self.set_status("已取消连接" if cancelled else "操作未完成 · "+str(error))
            self.sync()
            self._schedule_reconnect()
        if self.session.connected and getattr(self.session,'dirty',None):
            self.refresh_background()

    def change_noise(self,mode):
        if self.session.connected and self.session.noise==mode and not self.busy:
            return
        name={"smart":"智能降噪","light":"轻度降噪","moderate":"中度降噪",
              "deep":"深度降噪","off":"关闭降噪","transparency":"通透模式","vocal":"人声通透","adaptive":"自适应降噪"}.get(mode,mode)
        self.perform(lambda:self.session.set_noise(mode),name+"已生效")

    def change_preset(self,preset):
        if self.session.connected and self.session.preset==preset and not self.busy:
            return
        name=next((p["name"] for p in self._presets() if p["id"]==preset),"音效")
        self.perform(lambda:self.session.set_preset(preset),"已切换为「"+name+"」")

    def next_preset(self):
        ids=[p["id"] for p in self._presets()]
        if ids:
            current=ids.index(self.session.preset) if self.session.preset in ids else -1
            self.change_preset(ids[(current+1)%len(ids)])

    def change_feature(self,key,enabled):
        from .oppo_features import FEATURE_TITLES
        title=FEATURE_TITLES.get(key,key)
        self.perform(lambda:self.session.set_feature(key,enabled),title+("已开启" if enabled else "已关闭"))

    def start(self):
        if not self.live:
            return
        if sys.platform!="win32":
            self.set_status("真实蓝牙控制当前支持 Windows")
            return
        self._retry_timer=self.scheduler.timer()
        self._refresh_timer=self.scheduler.timer()
        self._refresh_timer.start(2,self._refresh_tick,repeat=True)
        self.scan(auto_connect=True)

    def scan(self,auto_connect=False):
        if not self.live:
            return
        def found(devices):
            previous=self.devices[self.device_index].address if 0<=self.device_index<len(self.devices) else None
            self.devices=devices
            self.device_index=next((i for i,d in enumerate(devices) if d.address==previous),0 if devices else -1)
            self.sync()
            if not devices:
                self.set_status("未找到已配对的 OPPO 或一加耳机，请先在 Windows 中配对")
            elif auto_connect and not self.session.connected:
                self.connect_selected()
        if sys.platform!="win32":
            self.set_status("真实蓝牙控制当前支持 Windows")
            return
        from .bluetooth_windows import discover
        self.perform(discover,"已更新耳机列表",then=found)

    def select_device(self,index):
        if self.live and not self.busy and 0<=index<len(self.devices):
            if index==self.device_index and self.session.connected:
                return
            self.device_index=index
            self.connect_selected()

    def connect_selected(self):
        if self.busy or self.stopped:
            return
        if not (0<=self.device_index<len(self.devices)):
            self.scan(auto_connect=True)
            return
        self.want_connection=True
        if self._retry_timer:
            self._retry_timer.stop()
        self.connecting=True
        self.cancel_requested=False
        self._connect_cancel=threading.Event()
        cancel=self._connect_cancel
        device=self.devices[self.device_index]
        self.perform(lambda:self.session.connect(device,cancel=cancel),"已连接 · "+device.name)

    def change_connection(self):
        if not self.live:
            self.session.transport.connected=not self.session.connected
            self.refresh() if self.session.connected else self.sync()
            return
        if self.busy and self.connecting:
            self.want_connection=False
            self.cancel_requested=True
            if self._retry_timer:
                self._retry_timer.stop()
            if self._connect_cancel:
                self._connect_cancel.set()
            self.session.cancel.set()
            if self.session.channel:
                self.session.channel.close()
            self.set_status("正在取消连接…")
            self.sync()
            return
        if self.busy:
            return
        if self.session.connected:
            self.want_connection=False
            if self._retry_timer:
                self._retry_timer.stop()
            self.perform(self.session.disconnect,"控制连接已断开")
        else:
            self.connect_selected()

    def _schedule_reconnect(self):
        if (self.stopped or not self.want_connection or self.session.connected or self.busy
                or not self._retry_timer or self._retry_timer.running):
            return
        self._retry_timer.start(self._retry_delay,self.connect_selected)
        self._retry_delay=min(self._retry_delay*2,60)

    def _refresh_tick(self):
        self.refresh_background()

    def refresh_background(self,force=False):
        # One read at a time, on the same worker as writes. Polling never marks
        # controls busy; a user's next operation can queue behind this short read.
        if (self.stopped or not self.live or self.busy or self._refreshing
                or not self.session.connected or not getattr(self.session,'ready',False)):
            return
        interactive=any(getattr(window,'visible',True) for window in self.windows)
        self._refreshing=True
        future=self._executor.submit(lambda:self.session.refresh_due(interactive,force=force))
        future.add_done_callback(lambda f:None if self.stopped else self.dispatch(lambda:self._finish_background(f)))

    def _finish_background(self,future):
        self._refreshing=False
        if self.stopped:
            return
        try:
            future.result()
        except Exception as error:
            if not self.busy:
                self.set_status('操作未完成 · '+str(error))
            self._schedule_reconnect()
        self.sync()
        if self.session.connected and self.session.dirty:
            self.refresh_background()

    def refresh(self):
        if self.live and not self.session.connected:
            self.scan(auto_connect=True)
        else:
            self.perform(self.session.refresh,"状态已刷新")

    def change_theme(self,dark):
        self.change_theme_mode('dark' if dark else 'light')

    def change_theme_mode(self,mode):
        from .appearance import THEME_MODES
        if mode not in THEME_MODES:raise ValueError('未知外观模式')
        self.theme_mode=mode
        self.dark=self.system_dark if mode=='system' else mode=='dark'
        self.save_preferences(theme_mode=mode,dark=self.dark)
        self.sync()

    def change_fast_mode(self,enabled):
        if type(enabled) is not bool:raise ValueError('极速模式需要开关值')
        self.fast_mode=enabled
        self.save_preferences(fast_mode=enabled)
        self.sync()

    def change_fast_launch(self,enabled):
        if type(enabled) is not bool:raise ValueError('快速唤出需要开关值')
        self.fast_launch=enabled
        self.save_preferences(fast_launch=enabled)
        self.sync()

    def change_quick_topmost(self,enabled):
        if type(enabled) is not bool:raise ValueError('快捷控制置顶需要开关值')
        self.quick_topmost=enabled
        self.save_preferences(quick_topmost=enabled)
        self.sync()

    def change_quick_auto_hide(self,enabled):
        if type(enabled) is not bool:raise ValueError('快捷控制自动收起需要开关值')
        self.quick_auto_hide=enabled
        self.save_preferences(quick_auto_hide=enabled)
        self.sync()

    def change_quick_idle_seconds(self,seconds):
        if type(seconds) is not int or not 5<=seconds<=3600:raise ValueError('自动收起时间应为 5–3600 秒')
        self.quick_idle_seconds=seconds
        self.save_preferences(quick_idle_seconds=seconds)
        self.sync()

    def change_accent_mode(self,mode):
        from .appearance import ACCENT_MODES,read_system_accent
        if mode not in ACCENT_MODES:raise ValueError('未知主题色来源')
        self.accent_mode=mode
        if mode=='system':self.system_accent=read_system_accent()
        self.save_preferences(accent_mode=mode)
        self.sync()

    def change_accent_color(self,color):
        from .appearance import accent_color
        self.accent_color=accent_color(color);self.accent_mode='custom'
        self.save_preferences(accent_mode='custom',accent_color=self.accent_color)
        self.sync()

    def refresh_system_appearance(self):
        from .appearance import read_system_appearance,read_system_accent
        dark,motion=read_system_appearance()
        accent=read_system_accent() if self.accent_mode=='system' else self.system_accent
        if (dark,motion,accent)==(self.system_dark,self.system_motion,self.system_accent):return
        self.system_dark,self.system_motion=dark,motion
        self.system_accent=accent
        if self.theme_mode=='system':self.dark=dark
        self.sync()

    def save_preferences(self,**changes):
        from .preferences import write_preferences
        self.preference_data.update(changes)
        try:
            write_preferences(self.preferences,self.preference_data)
        except OSError:
            self.set_status('设置已更改，本次未能保存偏好')

    def change_connection_popup(self,enabled):
        self.connection_popup=bool(enabled)
        self.save_preferences(connection_popup=self.connection_popup)
        self.sync()

    def reset(self):
        if self.live:
            self.change_theme(False)
            self.sync()
            self.set_status("已恢复默认外观")
        else:
            from .session import DemoSession
            self.session=DemoSession()
            self.anc_level="smart"
            self.sync()
            self.set_status("已恢复默认设置")

    def close(self):
        self.stopped=True
        for timer in (self._retry_timer,self._refresh_timer):
            if timer:
                timer.stop()
        if self.live:
            self.session.on_changed=None
            self.session.cancel.set()
            self.session.close()
        if self._executor:
            self._executor.shutdown(wait=False,cancel_futures=True)
