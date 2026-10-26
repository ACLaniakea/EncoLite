"""Native integration for this application's own windows and notification icon.

No polling thread, no extra GUI framework. Every pointer-sized Win32 function
has an explicit signature. UI callbacks are deferred to Slint's UI event queue.
"""
import ctypes as C
from ctypes import wintypes as W
import os
import time

user = C.WinDLL("user32", use_last_error=True)
shell = C.WinDLL("shell32", use_last_error=True)
kernel = C.WinDLL("kernel32", use_last_error=True)
controls = C.WinDLL("comctl32", use_last_error=True)
LRESULT = C.c_ssize_t
WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
ENUMPROC = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
SUBCLASSPROC = C.WINFUNCTYPE(LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM,C.c_size_t,C.c_size_t)


def api(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, args
    return fn


DefWindowProc = api(user,"DefWindowProcW",LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
SetWindowLong = api(user,"SetWindowLongPtrW",C.c_ssize_t,W.HWND,C.c_int,C.c_ssize_t)
GetWindowLong = api(user,"GetWindowLongPtrW",C.c_ssize_t,W.HWND,C.c_int)
GetModuleHandle = api(kernel,"GetModuleHandleW",W.HMODULE,W.LPCWSTR)
GetThreadId = api(kernel,"GetCurrentThreadId",W.DWORD)
EnumThreadWindows = api(user,"EnumThreadWindows",W.BOOL,W.DWORD,ENUMPROC,W.LPARAM)
GetWindowText = api(user,"GetWindowTextW",C.c_int,W.HWND,W.LPWSTR,C.c_int)
ShowWindow = api(user,"ShowWindow",W.BOOL,W.HWND,C.c_int)
SetForegroundWindow = api(user,"SetForegroundWindow",W.BOOL,W.HWND)
AllowSetForegroundWindow = api(user,"AllowSetForegroundWindow",W.BOOL,W.DWORD)
GetWindowThreadProcessId = api(user,"GetWindowThreadProcessId",W.DWORD,W.HWND,C.POINTER(W.DWORD))
SetWindowPos = api(user,"SetWindowPos",W.BOOL,W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT)
GetWindowRect = api(user,"GetWindowRect",W.BOOL,W.HWND,C.POINTER(W.RECT))
GetCursorPos = api(user,"GetCursorPos",W.BOOL,C.POINTER(W.POINT))
MonitorFromPoint = api(user,"MonitorFromPoint",W.HANDLE,W.POINT,W.DWORD)
DestroyWindow = api(user,"DestroyWindow",W.BOOL,W.HWND)
LoadImage = api(user,"LoadImageW",W.HANDLE,W.HINSTANCE,W.LPCWSTR,W.UINT,C.c_int,C.c_int,W.UINT)
DestroyIcon = api(user,"DestroyIcon",W.BOOL,W.HICON)
CreatePopupMenu = api(user,"CreatePopupMenu",W.HMENU)
AppendMenu = api(user,"AppendMenuW",W.BOOL,W.HMENU,W.UINT,C.c_size_t,W.LPCWSTR)
DestroyMenu = api(user,"DestroyMenu",W.BOOL,W.HMENU)
TrackPopupMenu = api(user,"TrackPopupMenu",W.UINT,W.HMENU,W.UINT,C.c_int,C.c_int,C.c_int,W.HWND,C.c_void_p)
PostMessage = api(user,"PostMessageW",W.BOOL,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
GetForegroundWindow = api(user,"GetForegroundWindow",W.HWND)
IsWindowVisible = api(user,"IsWindowVisible",W.BOOL,W.HWND)
IsIconic = api(user,"IsIconic",W.BOOL,W.HWND)
IsChild = api(user,"IsChild",W.BOOL,W.HWND,W.HWND)
MonitorFromWindow = api(user,"MonitorFromWindow",W.HANDLE,W.HWND,W.DWORD)
GetClientRect = api(user,"GetClientRect",W.BOOL,W.HWND,C.POINTER(W.RECT))
FindWindow = api(user,"FindWindowW",W.HWND,W.LPCWSTR,W.LPCWSTR)
CreateMutex = api(kernel,"CreateMutexW",W.HANDLE,C.c_void_p,W.BOOL,W.LPCWSTR)
SetWindowSubclass = api(controls,"SetWindowSubclass",W.BOOL,W.HWND,SUBCLASSPROC,C.c_size_t,C.c_size_t)
RemoveWindowSubclass = api(controls,"RemoveWindowSubclass",W.BOOL,W.HWND,SUBCLASSPROC,C.c_size_t)
DefSubclassProc = api(controls,"DefSubclassProc",LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
SetTimer = api(user,"SetTimer",C.c_size_t,W.HWND,C.c_size_t,W.UINT,C.c_void_p)
KillTimer = api(user,"KillTimer",W.BOOL,W.HWND,C.c_size_t)


@SUBCLASSPROC
def _borderless_proc(hwnd,message,wparam,lparam,subclass_id,reference):
    # Window style flags alone do not suppress classic nonclient painting when
    # Windows activates or restores a custom-region window. Preserve Slint's
    # nonclient size calculation and hit testing, suppress only native painting.
    if message==0x85:  # WM_NCPAINT
        return 0
    if message==0x86:  # WM_NCACTIVATE: update activation without painting a rim.
        return DefSubclassProc(hwnd,message,wparam,-1)
    if message==0x82:  # WM_NCDESTROY
        RemoveWindowSubclass(hwnd,_borderless_proc,subclass_id)
    return DefSubclassProc(hwnd,message,wparam,lparam)


def activate_existing(quick=False, tray_only=False):
    """Local app IPC: reuse this app's existing tray owner when launched again."""
    hwnd = FindWindow("EncoLiteTray", "Enco Lite tray")
    if hwnd and not tray_only:
        process_id=W.DWORD()
        GetWindowThreadProcessId(hwnd,C.byref(process_id))
        if process_id.value:
            AllowSetForegroundWindow(process_id.value)
    return bool(hwnd and PostMessage(hwnd, 0x8002, 0 if tray_only else 1 if quick else 2, 0))


def activate_window(hwnd):
    if IsIconic(hwnd):
        ShowWindow(hwnd,9)  # Restore only minimized windows, keep maximized ones.
    SetWindowPos(hwnd,None,0,0,0,0,0x53)  # HWND_TOP, show without moving/resizing.
    return bool(SetForegroundWindow(hwnd))


def application_mutex():
    handle=CreateMutex(None,False,'Local\\EncoLite.Desktop')
    if not handle:
        raise C.WinError(C.get_last_error())
    if C.get_last_error()==183:  # ERROR_ALREADY_EXISTS
        api(kernel,'CloseHandle',W.BOOL,W.HANDLE)(handle)
        return None
    return handle  # Owned until process exit; also used by Setup's AppMutex.


class WndClass(C.Structure):
    _fields_ = [("style",W.UINT),("proc",WNDPROC),("cls_extra",C.c_int),("wnd_extra",C.c_int),
                ("instance",W.HINSTANCE),("icon",W.HICON),("cursor",W.HANDLE),
                ("background",W.HBRUSH),("menu",W.LPCWSTR),("name",W.LPCWSTR)]


class NotifyIcon(C.Structure):
    _fields_ = [("size",W.DWORD),("hwnd",W.HWND),("id",W.UINT),("flags",W.UINT),
                ("message",W.UINT),("icon",W.HICON),("tip",W.WCHAR*128),
                ("state",W.DWORD),("state_mask",W.DWORD),("info",W.WCHAR*256),
                ("version",W.UINT),("info_title",W.WCHAR*64),("info_flags",W.DWORD),
                ("guid",C.c_ubyte*16),("balloon_icon",W.HICON)]


class MonitorInfo(C.Structure):
    _fields_ = [("size",W.DWORD),("monitor",W.RECT),("work",W.RECT),("flags",W.DWORD)]


RegisterClass = api(user,"RegisterClassW",W.ATOM,C.POINTER(WndClass))
UnregisterClass = api(user,"UnregisterClassW",W.BOOL,W.LPCWSTR,W.HINSTANCE)
CreateWindow = api(user,"CreateWindowExW",W.HWND,W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,
                   C.c_int,C.c_int,C.c_int,C.c_int,W.HWND,W.HMENU,W.HINSTANCE,C.c_void_p)
Notify = api(shell,"Shell_NotifyIconW",W.BOOL,W.DWORD,C.POINTER(NotifyIcon))
RegisterMessage = api(user,"RegisterWindowMessageW",W.UINT,W.LPCWSTR)
GetMonitorInfo = api(user,"GetMonitorInfoW",W.BOOL,W.HANDLE,C.POINTER(MonitorInfo))


def window_handle(title, *, visible_only=True):
    """Only search windows on our UI thread, never another application's window."""
    matches = []
    @ENUMPROC
    def collect(hwnd, _):
        text = C.create_unicode_buffer(256)
        GetWindowText(hwnd,text,len(text))
        if text.value == title:
            matches.append(hwnd)
        return True
    EnumThreadWindows(GetThreadId(),collect,0)
    visible=[hwnd for hwnd in matches if IsWindowVisible(hwnd)]
    # Slint can keep a hidden previous component alive while its replacement
    # has the same title. Never style, position or activate that stale HWND.
    return visible[0] if visible else matches[0] if matches and not visible_only else None


def style_window(title, *, tool=False, hidden=False, passive=False, maximized=None):
    hwnd=window_handle(title,visible_only=not hidden)
    if not hwnd:
        return None
    if not hidden:
        SetWindowSubclass(hwnd,_borderless_proc,1,0)
    # Preserve Slint's resize hit testing; remove actual native caption and
    # decorative extended edges, which can reappear after a frame recalculation.
    style=GetWindowLong(hwnd,-16)
    clean=style & ~0x00C00000
    extended=GetWindowLong(hwnd,-20)
    clean_extended=extended & ~(0x200 | 0x20000)
    if tool:
        clean_extended=(clean_extended | 0x80) & ~0x40000
    if passive:
        clean_extended |= 0x08000000  # WS_EX_NOACTIVATE
    if clean!=style:
        SetWindowLong(hwnd,-16,clean)
    if clean_extended!=extended:
        SetWindowLong(hwnd,-20,clean_extended)
    if clean!=style or clean_extended!=extended:
        SetWindowPos(hwnd,None,0,0,0,0,0x37)
    try:
        dwm=C.WinDLL('dwmapi')
        setter=api(dwm,'DwmSetWindowAttribute',C.c_long,W.HWND,W.DWORD,C.c_void_p,W.DWORD)
        # Rounded geometry belongs to the app. DWM must not add a second rim.
        preference=C.c_int(1)
        border=C.c_uint32(0xFFFFFFFE)
        setter(hwnd,33,C.byref(preference),C.sizeof(preference))
        setter(hwnd,34,C.byref(border),C.sizeof(border))
    except OSError:
        pass
    if not hidden:
        round_window(title,maximized=maximized)
    else:
        ShowWindow(hwnd,0)
    return hwnd


def position_popup(title, *, activate=True, reference=None):
    hwnd=style_window(title,tool=True,passive=not activate)
    if not hwnd:
        return None
    monitor=MonitorInfo(size=C.sizeof(MonitorInfo))
    if reference:
        monitor_handle=MonitorFromWindow(reference,2)
    else:
        point=W.POINT();GetCursorPos(C.byref(point))
        monitor_handle=MonitorFromPoint(point,2)
    if not GetMonitorInfo(monitor_handle,C.byref(monitor)):
        return hwnd
    rect=W.RECT();GetWindowRect(hwnd,C.byref(rect))
    gap=round(12*(GetDpiForWindow(hwnd) or 96)/96)
    x=max(monitor.work.left,monitor.work.right-(rect.right-rect.left)-gap)
    y=max(monitor.work.top,monitor.work.bottom-(rect.bottom-rect.top)-gap)
    SetWindowPos(hwnd,C.c_void_p(-1),x,y,0,0,0x11)
    if activate:
        activate_window(hwnd)
    elif reference and GetForegroundWindow()==hwnd:
        SetForegroundWindow(reference)
    return hwnd


class NativePlacement(C.Structure):
    _fields_=[('length',W.UINT),('flags',W.UINT),('show',W.UINT),
        ('minimum',W.POINT),('maximum',W.POINT),('normal',W.RECT)]

GetWindowPlacement=api(user,'GetWindowPlacement',W.BOOL,W.HWND,C.POINTER(NativePlacement))


def window_placement(title):
    hwnd=window_handle(title)
    if not hwnd:
        return None
    if IsIconic(hwnd) or IsZoomed(hwnd):
        placement=NativePlacement(length=C.sizeof(NativePlacement))
        if GetWindowPlacement(hwnd,C.byref(placement)):
            rect=placement.normal
            return (rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top,
                bool(IsZoomed(hwnd) or placement.show==3 or placement.flags&2))
    rect=W.RECT();GetWindowRect(hwnd,C.byref(rect))
    return (rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top,False)


def restore_placement(title,placement):
    hwnd=window_handle(title)
    if not hwnd or not placement:
        return
    from .preferences import fit_bounds
    x,y,width,height,maximized=placement
    monitor=MonitorInfo(size=C.sizeof(MonitorInfo))
    if GetMonitorInfo(MonitorFromPoint(W.POINT(x,y),2),C.byref(monitor)):
        x,y,width,height,maximized=fit_bounds(placement,(monitor.work.left,monitor.work.top,monitor.work.right,monitor.work.bottom))
    SetWindowPos(hwnd,None,x,y,width,height,0x14)


class TrayClickTimer:
    """One native single-shot timer; works with either a Win32 or Slint loop."""
    def __init__(self, owner):
        self.owner=owner
        self.callback=None

    @property
    def running(self):
        return self.callback is not None

    def start(self, mode, duration, callback):
        self.stop()
        self.callback=callback
        if not SetTimer(self.owner.hwnd,1,max(1,round(duration.total_seconds()*1000)),None):
            self.callback=None
            raise C.WinError(C.get_last_error())

    def stop(self):
        KillTimer(self.owner.hwnd,1)
        self.callback=None

    def fire(self):
        callback=self.callback
        self.stop()
        if callback:self.owner.defer(callback)


class Tray:
    def __init__(self, icon_path, on_quick, on_main, on_exit, on_noise, defer, test_mode=False, noise_options=None, on_show_quick=None, on_dispatch=None, on_settings_changed=None, on_hotkey=None, on_bluetooth=None):
        self.on_quick,self.on_main,self.on_exit,self.on_noise=on_quick,on_main,on_exit,on_noise
        self.defer=defer
        self.noise_options=noise_options
        self.on_show_quick=on_show_quick or on_quick
        self.on_dispatch=on_dispatch
        self.on_settings_changed=on_settings_changed
        self.on_hotkey=on_hotkey
        self.on_bluetooth=on_bluetooth
        self.bluetooth_notifications=None
        self._destroyed=False
        self._ignore_until=0
        self._menu_pending=False
        self._quick_pending=False
        self._tip=""
        self.instance=GetModuleHandle(None)
        self.class_name=f"EncoLiteTray-test-{os.getpid()}" if test_mode else "EncoLiteTray"
        self.taskbar_created=RegisterMessage("TaskbarCreated")
        self.proc=WNDPROC(self._wndproc)
        self.wndclass=WndClass(proc=self.proc,instance=self.instance,name=self.class_name)
        if not RegisterClass(C.byref(self.wndclass)):
            raise C.WinError(C.get_last_error())
        self.hwnd=CreateWindow(0,self.class_name,"Enco Lite tray",0,0,0,0,0,None,None,self.instance,None)
        if not self.hwnd:
            raise C.WinError(C.get_last_error())
        self.icon=LoadImage(None,str(icon_path),1,32,32,0x10)
        if not self.icon:
            self.close()
            raise C.WinError(C.get_last_error())
        self.data=NotifyIcon(size=C.sizeof(NotifyIcon),hwnd=self.hwnd,id=1,flags=0x87,
                             message=0x8001,icon=self.icon,tip="Enco Lite")
        self._add_icon()
        self.click_timer=TrayClickTimer(self)
        if on_bluetooth:
            from .bluetooth_notifications import BluetoothNotifications
            self.bluetooth_notifications=BluetoothNotifications(self.hwnd)

    def _add_icon(self):
        if not Notify(0,C.byref(self.data)):
            raise C.WinError(C.get_last_error())
        self.data.version=4
        self.version4=bool(Notify(4,C.byref(self.data)))

    def queue_quick(self):
        if self._quick_pending:return
        self._quick_pending=True
        def deliver():
            self._quick_pending=False
            if time.monotonic()>=self._ignore_until:self.on_quick()
        self.defer(deliver)

    def _wndproc(self, hwnd, message, wparam, lparam):
        try:
            if message == self.taskbar_created and hasattr(self,"data"):
                self._add_icon()
            elif message==0x219 and self.bluetooth_notifications:  # WM_DEVICECHANGE
                event=self.bluetooth_notifications.event(wparam,lparam)
                if event is not None:
                    self.defer(lambda event=event:self.on_bluetooth(*event))
                elif wparam==7:  # DBT_DEVNODES_CHANGED: radio may have been replaced.
                    self.defer(self.bluetooth_notifications.refresh)
            elif message==0x312 and self.on_hotkey:  # WM_HOTKEY, delivered without a keyboard hook.
                self.defer(lambda:self.on_hotkey(wparam,lparam))
                return 0
            elif message in (0x15,0x1A,0x31A,0x320) and self.on_settings_changed:
                self.defer(self.on_settings_changed)
                return 0
            elif message==0x113 and wparam==1:
                self.click_timer.fire()
                return 0
            elif (message==0x8003 or message==0x113 and wparam==2) and self.on_dispatch:
                self.on_dispatch()
                return 0
            elif message == 0x8002:
                if wparam in (1, 2, 3):
                    self.defer({1:self.on_show_quick,2:self.on_main,3:self.on_exit}[wparam])
                return 0
            elif message == 0x8001:
                event=lparam & 0xFFFF
                if event == 0x203:  # WM_LBUTTONDBLCLK
                    self.click_timer.stop()
                    self._ignore_until=time.monotonic()+.45
                    self.defer(self.on_main)
                elif (event in (0x400,0x401) or event==0x202 and not self.version4) and time.monotonic() >= self._ignore_until:
                    # Version 4 emits NIN_SELECT/NIN_KEYSELECT. Handling its
                    # legacy mouse-up too would toggle twice. Dispatch now;
                    # double-click still opens main and suppresses its tail.
                    self.queue_quick()
                elif event in (0x205,0x7B):
                    self.click_timer.stop()
                    if not self._menu_pending:
                        self._menu_pending=True
                        self.defer(self.menu)
                return 0
        except Exception:
            # Exceptions must never cross the native Windows callback boundary.
            import traceback
            traceback.print_exc()
        return DefWindowProc(hwnd,message,wparam,lparam)

    def update_tip(self,text):
        if text != self._tip:
            self._tip=text
            self.data.tip=text[:127]
            Notify(1,C.byref(self.data))

    def menu(self):
        self.click_timer.stop()
        menu=CreatePopupMenu()
        action=None
        try:
            options=self.noise_options() if self.noise_options else [('smart','智能降噪'),('transparency','通透模式'),('off','关闭降噪')]
            for ident,label in ((1,"快捷控制"),(2,"打开主窗口"),(0,None)):
                AppendMenu(menu,0x800 if label is None else 0,ident,label)
            noise_actions={}
            for ident,(mode,label) in enumerate(options,start=10):
                AppendMenu(menu,0,ident,label)
                noise_actions[ident]=lambda mode=mode:self.on_noise(mode)
            if options:
                AppendMenu(menu,0x800,0,None)
            AppendMenu(menu,0,3,"退出 Enco Lite")
            point=W.POINT()
            GetCursorPos(C.byref(point))
            SetForegroundWindow(self.hwnd)
            result=TrackPopupMenu(menu,0x100|0x2,point.x,point.y,0,self.hwnd,None)
            PostMessage(self.hwnd,0,0,0)
            actions={1:self.on_show_quick,2:self.on_main,3:self.on_exit,
                     **noise_actions}
            if result in actions:
                action=actions[result]
        finally:
            DestroyMenu(menu)
            self._menu_pending=False
            self._ignore_until=time.monotonic()+.45
            Notify(3,C.byref(self.data))  # NIM_SETFOCUS after the menu closes.
        # menu() already runs on the UI thread. Re-enqueuing inside Slint's
        # callback drain can leave this action waiting for the next tray event.
        if action:
            action()

    def close(self):
        if self._destroyed:
            return
        self._destroyed=True
        if self.bluetooth_notifications:
            self.bluetooth_notifications.close()
        if hasattr(self,"click_timer"):
            self.click_timer.stop()
        if hasattr(self,"data"):
            Notify(2,C.byref(self.data))
        if getattr(self,"icon",None):
            DestroyIcon(self.icon)
        if getattr(self,"hwnd",None):
            DestroyWindow(self.hwnd)
        UnregisterClass(self.class_name,self.instance)

# Explicit native region complements transparent, clipped Slint corners on
# software-rendered borderless windows. No HWND subclass or persistent timer.
gdi=C.WinDLL('gdi32',use_last_error=True)
CreateRoundRectRgn=api(gdi,'CreateRoundRectRgn',W.HANDLE,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int)
DeleteObject=api(gdi,'DeleteObject',W.BOOL,W.HANDLE)
SetWindowRgn=api(user,'SetWindowRgn',C.c_int,W.HWND,W.HANDLE,W.BOOL)
IsZoomed=api(user,'IsZoomed',W.BOOL,W.HWND)
GetDpiForWindow=api(user,'GetDpiForWindow',W.UINT,W.HWND)


def round_window(title,*,maximized=None):
    hwnd=window_handle(title)
    if not hwnd:
        return False
    rect=W.RECT()
    if not GetWindowRect(hwnd,C.byref(rect)):
        return False
    if maximized is True or (maximized is None and IsZoomed(hwnd)):
        SetWindowRgn(hwnd,None,True)
        return True
    diameter=max(2,round(24*(GetDpiForWindow(hwnd) or 96)/96))
    region=CreateRoundRectRgn(0,0,rect.right-rect.left+1,rect.bottom-rect.top+1,diameter,diameter)
    if not region:
        return False
    # On success the OS owns the region; deleting it here would invalidate it.
    if not SetWindowRgn(hwnd,region,True):
        DeleteObject(region)
        return False
    return True
