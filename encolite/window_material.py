"""Windows 11 owns the backdrop and its outer contour as one native surface."""
import ctypes as C
import sys


class AccentPolicy(C.Structure):
    _fields_=[('state',C.c_int),('flags',C.c_uint),('color',C.c_uint),('animation',C.c_int)]


class CompositionData(C.Structure):
    _fields_=[('attribute',C.c_int),('data',C.c_void_p),('size',C.c_size_t)]


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
            self._accent=self.user.SetWindowCompositionAttribute
            self._accent.argtypes=[C.c_void_p,C.POINTER(CompositionData)];self._accent.restype=C.c_int
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

    def accent(self,hwnd,enabled,dark):
        color=0x66181818 if dark else 0x44f5f5f5
        policy=AccentPolicy(4 if enabled else 0,0,color,0)
        data=CompositionData(19,C.addressof(policy),C.sizeof(policy))
        return bool(self._accent(hwnd,C.byref(data)))

    def prepare_frame(self,hwnd):
        from . import windows_shell as s
        # Keep native sizing/contour styles; Qt owns the full client and caption
        # painting. Layering/regions would prevent DWM rounding.
        style=s.GetWindowLong(hwnd,-16);exstyle=s.GetWindowLong(hwnd,-20)
        # Avoid adding a classic class shadow on top of the compact DWM contour.
        get_class=self.user.GetClassLongPtrW;get_class.argtypes=[C.c_void_p,C.c_int];get_class.restype=C.c_size_t
        set_class=self.user.SetClassLongPtrW;set_class.argtypes=[C.c_void_p,C.c_int,C.c_ssize_t];set_class.restype=C.c_size_t
        class_style=get_class(hwnd,-26)
        if class_style&0x20000:set_class(hwnd,-26,class_style&~0x20000)
        region=self.user.SetWindowRgn;region.argtypes=[C.c_void_p,C.c_void_p,C.c_int];region.restype=C.c_int
        region(hwnd,None,1)
        s.SetWindowLong(hwnd,-20,exstyle&~0x80000)
        s.SetWindowLong(hwnd,-16,style|0x00c40000)
        ready=self.attribute(hwnd,2,1) and self.attribute(hwnd,33,3)
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

    def refresh_frame(self,hwnd):
        from . import windows_shell as s
        s.SetWindowPos(hwnd,None,0,0,0,0,0x37)


class WindowMaterial:
    def __init__(self,native=None):
        self.native=native if native is not None else DwmApi()
        self.supported=self.native.supported;self.states={};self.frames={};self.decorations={};self.updates=0

    def apply(self,hwnd,enabled,dark=False,*,force=False):
        if not self.supported:return False
        key=(bool(enabled),bool(dark));previous=self.states.get(hwnd)
        if not force and previous and previous[:2]==key:return previous[-1]
        if force or not self.frames.get(hwnd):self.frames[hwnd]=self.native.prepare_frame(hwnd)
        self.updates+=1
        active=False
        if self.frames[hwnd] and (force or previous is None or previous[1]!=bool(dark)):
            self.native.attribute(hwnd,20,int(bool(dark)))
        if force or previous is None:
            self.native.attribute(hwnd,38,1)
            self.native.frame(hwnd,False)
        if self.frames[hwnd]:active=bool(enabled and self.native.accent(hwnd,True,dark))
        if not active:self.native.accent(hwnd,False,dark)
        self.states[hwnd]=(*key,active)
        return active

    def forget(self,hwnd):
        self.states.pop(hwnd,None);self.frames.pop(hwnd,None);self.decorations.pop(hwnd,None)

    def decorate(self,hwnd,visible,*,force=False):
        if not self.frames.get(hwnd):return
        if not force and self.decorations.get(hwnd)==visible:return
        # Keep legacy caption painting disabled even after the fade. On Win11,
        # re-enabling NC rendering can paint a second title behind translucent Qt.
        self.native.attribute(hwnd,2,1)
        self.native.attribute(hwnd,34,0xffffffff if visible else 0xfffffffe)
        # Small native corners also use Windows' compact popup shadow. During
        # the client-surface fade, QML supplies the contour without a DWM halo.
        self.native.attribute(hwnd,33,3 if visible else 1)
        self.native.refresh_frame(hwnd)
        self.decorations[hwnd]=visible
