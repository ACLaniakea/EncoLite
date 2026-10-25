"""Per-window native Acrylic. Effects exist only while a GUI window is open."""
import ctypes as C
import sys


class AccentPolicy(C.Structure):
    _fields_=[('state',C.c_int),('flags',C.c_uint),('color',C.c_uint),('animation',C.c_int)]


class CompositionData(C.Structure):
    _fields_=[('attribute',C.c_int),('data',C.c_void_p),('size',C.c_size_t)]


class DwmApi:
    def __init__(self):
        self.supported=False
        if sys.platform!='win32' or sys.getwindowsversion().build<17763:return
        try:
            dll=C.WinDLL('dwmapi');user=C.WinDLL('user32',use_last_error=True);gdi=C.WinDLL('gdi32')
            self._attribute=dll.DwmSetWindowAttribute
            self._attribute.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_uint];self._attribute.restype=C.c_long
            self._frame=dll.DwmExtendFrameIntoClientArea
            self._frame.argtypes=[C.c_void_p,C.c_void_p];self._frame.restype=C.c_long
            self._set=user.SetWindowCompositionAttribute;self._get=user.GetWindowCompositionAttribute
            for fn in (self._set,self._get):fn.argtypes=[C.c_void_p,C.POINTER(CompositionData)];fn.restype=C.c_int
            self._region=gdi.CreateRoundRectRgn;self._region.argtypes=[C.c_int]*6;self._region.restype=C.c_void_p
            self._set_region=user.SetWindowRgn;self._set_region.argtypes=[C.c_void_p,C.c_void_p,C.c_int];self._set_region.restype=C.c_int
            self._delete=gdi.DeleteObject;self._delete.argtypes=[C.c_void_p];self._delete.restype=C.c_int
            enabled=C.c_int();fn=dll.DwmIsCompositionEnabled
            fn.argtypes=[C.POINTER(C.c_int)];fn.restype=C.c_long
            self.supported=fn(C.byref(enabled))==0 and bool(enabled.value)
        except (OSError,AttributeError):pass

    def attribute(self,hwnd,name,value):
        value=C.c_uint(value)
        return self._attribute(hwnd,name,C.byref(value),C.sizeof(value))==0

    def frame(self,hwnd,extended):
        margins=(C.c_int*4)(*([-1]*4 if extended else [0]*4))
        return self._frame(hwnd,C.byref(margins))==0

    def accent(self,hwnd,enabled,dark):
        policy=AccentPolicy(4 if enabled else 0,0,0x99181818 if dark else 0x99f5f5f5,0)
        data=CompositionData(19,C.addressof(policy),C.sizeof(policy))
        return bool(self._set(hwnd,C.byref(data)))

    def accent_state(self,hwnd):
        policy=AccentPolicy();data=CompositionData(19,C.addressof(policy),C.sizeof(policy))
        return policy.state if self._get(hwnd,C.byref(data)) else None

    def shape(self,hwnd,shape):
        if shape is None:return bool(self._set_region(hwnd,None,1))
        width,height,radius=shape
        # GDI regions have integer, exclusive edges. Keep the Qt antialiased
        # outline inside the region on both sides at fractional/scaled DPI.
        region=self._region(-2,-2,width+3,height+3,radius*2+4,radius*2+4)
        if not region:return False
        if self._set_region(hwnd,region,1):return True  # Ownership passes to USER32.
        self._delete(region);return False


class WindowMaterial:
    def __init__(self,native=None):
        self.native=native if native is not None else DwmApi()
        self.supported=self.native.supported;self.states={};self.shapes={};self.updates=0

    def apply(self,hwnd,enabled,dark=False,*,force=False):
        if not self.supported:return False
        key=(bool(enabled),bool(dark));previous=self.states.get(hwnd)
        if not enabled and previous is None:return False
        if not force and previous and previous[:2]==key:return previous[2]
        self.updates+=1
        active=False
        if enabled:
            self.native.attribute(hwnd,20,int(bool(dark)))
            # Qt's frameless alpha windows are layered. The taskbar-style
            # accent brush works with that surface; system backdrop 38 does not.
            self.native.attribute(hwnd,38,1)
            self.native.frame(hwnd,False)
            active=self.native.accent(hwnd,True,dark)
        if not active:
            self.native.accent(hwnd,False,dark)
            self.native.attribute(hwnd,38,1)
            self.native.frame(hwnd,False)
        self.native.attribute(hwnd,33,1)
        self.native.attribute(hwnd,34,0xfffffffe)
        self.states[hwnd]=(*key,active)
        return active

    def shape(self,hwnd,shape):
        if not self.supported:return
        if self.shapes.get(hwnd)==shape:return
        if self.native.shape(hwnd,shape):
            if shape is None:self.shapes.pop(hwnd,None)
            else:self.shapes[hwnd]=shape

    def forget(self,hwnd):
        self.states.pop(hwnd,None);self.shapes.pop(hwnd,None)
