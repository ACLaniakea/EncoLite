"""Windows 11 owns the backdrop and its outer contour as one native surface."""
import ctypes as C
import sys


class DwmApi:
    def __init__(self):
        self.supported=False
        if sys.platform!='win32' or sys.getwindowsversion().build<22621:return
        try:
            dll=C.WinDLL('dwmapi');self.user=C.WinDLL('user32',use_last_error=True)
            self._attribute=dll.DwmSetWindowAttribute
            self._attribute.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_uint];self._attribute.restype=C.c_long
            self._frame=dll.DwmExtendFrameIntoClientArea
            self._frame.argtypes=[C.c_void_p,C.c_void_p];self._frame.restype=C.c_long
            self._get=dll.DwmGetWindowAttribute
            self._get.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_uint];self._get.restype=C.c_long
            enabled=C.c_int();fn=dll.DwmIsCompositionEnabled
            fn.argtypes=[C.POINTER(C.c_int)];fn.restype=C.c_long
            self.supported=fn(C.byref(enabled))==0 and bool(enabled.value)
        except (OSError,AttributeError):pass

    def attribute(self,hwnd,name,value):
        value=C.c_uint(value)
        return self._attribute(hwnd,name,C.byref(value),C.sizeof(value))==0

    def read_attribute(self,hwnd,name):
        value=C.c_int()
        return value.value if self._get(hwnd,name,C.byref(value),C.sizeof(value))==0 else None

    def frame(self,hwnd,extended):
        margins=(C.c_int*4)(*([-1]*4 if extended else [0]*4))
        return self._frame(hwnd,C.byref(margins))==0

    def prepare_frame(self,hwnd):
        from . import windows_shell as s
        # Keep the native nonclient surface, but let WM_NCCALCSIZE extend our
        # content across the caption. Layering/regions prevent DWM rounding.
        style=s.GetWindowLong(hwnd,-16);exstyle=s.GetWindowLong(hwnd,-20)
        region=self.user.SetWindowRgn;region.argtypes=[C.c_void_p,C.c_void_p,C.c_int];region.restype=C.c_int
        region(hwnd,None,1)
        s.SetWindowLong(hwnd,-20,exstyle&~0x80000)
        s.SetWindowLong(hwnd,-16,style|0x00c40000)
        ready=self.attribute(hwnd,2,2) and self.attribute(hwnd,33,2)
        self.attribute(hwnd,34,0xffffffff)
        if not ready:
            s.SetWindowLong(hwnd,-16,style);s.SetWindowLong(hwnd,-20,exstyle)
            self.attribute(hwnd,2,1);self.attribute(hwnd,33,1)
        s.SetWindowPos(hwnd,None,0,0,0,0,0x37)
        return ready

    def full_client(self,hwnd,lparam):
        """The caller handles WM_NCCALCSIZE; maximized content uses the work area."""
        from . import windows_shell as s
        from ctypes import wintypes as W
        zoom=self.user.IsZoomed;zoom.argtypes=[C.c_void_p];zoom.restype=W.BOOL
        if lparam and zoom(hwnd):
            info=s.MonitorInfo();info.size=C.sizeof(info)
            if s.GetMonitorInfo(s.MonitorFromWindow(hwnd,2),C.byref(info)):
                rect=C.cast(lparam,C.POINTER(W.RECT)).contents
                rect.left,rect.top,rect.right,rect.bottom=info.work.left,info.work.top,info.work.right,info.work.bottom

    def caption_hidden(self,hwnd):
        from . import windows_shell as s
        from ctypes import wintypes as W
        rect=W.RECT();point=W.POINT()
        fn=self.user.ClientToScreen;fn.argtypes=[C.c_void_p,C.POINTER(W.POINT)];fn.restype=W.BOOL
        if not (s.GetWindowRect(hwnd,C.byref(rect)) and fn(hwnd,C.byref(point))):return False
        zoom=self.user.IsZoomed;zoom.argtypes=[C.c_void_p];zoom.restype=W.BOOL
        if zoom(hwnd):
            info=s.MonitorInfo();info.size=C.sizeof(info)
            if s.GetMonitorInfo(s.MonitorFromWindow(hwnd,2),C.byref(info)):return abs(point.y-info.work.top)<=1
        return abs(point.y-rect.top)<=1


class WindowMaterial:
    def __init__(self,native=None):
        self.native=native if native is not None else DwmApi()
        self.supported=self.native.supported;self.states={};self.frames={};self.updates=0

    def apply(self,hwnd,enabled,dark=False,*,force=False):
        if not self.supported:return False
        key=(bool(enabled),bool(dark));previous=self.states.get(hwnd)
        if not force and previous and previous[:2]==key:return previous[2]
        if force or not self.frames.get(hwnd):self.frames[hwnd]=self.native.prepare_frame(hwnd)
        self.updates+=1
        active=False
        if self.frames[hwnd]:self.native.attribute(hwnd,20,int(bool(dark)))
        if self.frames[hwnd] and enabled:
            active=self.native.frame(hwnd,True) and self.native.attribute(hwnd,38,3)
        if not active:
            self.native.attribute(hwnd,38,1)
            self.native.frame(hwnd,False)
        self.states[hwnd]=(*key,active)
        return active

    def forget(self,hwnd):
        self.states.pop(hwnd,None);self.frames.pop(hwnd,None)
