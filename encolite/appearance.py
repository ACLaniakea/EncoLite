"""Read-only system appearance; no polling, registry writes or policy changes."""
import sys,re
from functools import lru_cache

THEME_MODES=('system','light','dark')
ACCENT_MODES=('custom','system')
DEFAULT_ACCENT='#168b51'

def accent_color(value):
    if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
        raise ValueError('请输入六位颜色值，例如 #168B51')
    return value.lower()

def saved_accent(preferences):
    mode=preferences.get('accent_mode','custom')
    if mode not in ACCENT_MODES:mode='custom'
    try:color=accent_color(preferences.get('accent_color',DEFAULT_ACCENT))
    except ValueError:color=DEFAULT_ACCENT
    return mode,color

def read_system_accent():
    """Read the actual Windows UI accent, with DWM as an older-system fallback."""
    if sys.platform=='win32':
        import ctypes as C
        from ctypes import wintypes as W
        try:return _read_windows_ui_accent()
        except OSError:pass
        try:
            function=C.WinDLL('dwmapi').DwmGetColorizationColor
            function.argtypes=[C.POINTER(W.DWORD),C.POINTER(W.BOOL)];function.restype=C.c_long
            color=W.DWORD();opaque=W.BOOL()
            if function(C.byref(color),C.byref(opaque))==0:return f'#{color.value&0xffffff:06x}'
        except OSError:pass
    return DEFAULT_ACCENT

def _read_windows_ui_accent():
    """Call UISettings.GetColorValue(Accent) using the system WinRT ABI only.

    IID/vtable: Microsoft Windows SDK IUISettings3; Color is four bytes ARGB.
    Balance all COM/HSTRING references; no retained runtime, hooks or polling.
    """
    import ctypes as C
    import uuid
    from ctypes import wintypes as W
    dll=C.WinDLL('combase');pointer=C.c_void_p;hr=C.c_long
    def api(name,result,*args):
        f=getattr(dll,name);f.restype=result;f.argtypes=args;return f
    initialize=api('RoInitialize',hr,W.UINT)
    uninitialize=api('RoUninitialize',None)
    create=api('WindowsCreateString',hr,W.LPCWSTR,W.UINT,C.POINTER(pointer))
    delete=api('WindowsDeleteString',hr,pointer)
    activate=api('RoActivateInstance',hr,pointer,C.POINTER(pointer))
    def checked(result):
        if result<0:raise OSError(result,'无法读取 Windows 强调色')
    def method(obj,index,result,*args):
        table=C.cast(obj,C.POINTER(C.POINTER(pointer))).contents
        return C.WINFUNCTYPE(result,pointer,*args)(table[index])
    status=initialize(1)
    if status<0 and status!=-2147417850:checked(status)  # Existing STA is usable.
    text=pointer();instance=pointer();settings=pointer()
    try:
        name='Windows.UI.ViewManagement.UISettings'
        checked(create(name,len(name),C.byref(text)))
        checked(activate(text,C.byref(instance)))
        iid=(C.c_ubyte*16).from_buffer_copy(uuid.UUID('03021be4-5254-4781-8194-5168f7d06d7b').bytes_le)
        checked(method(instance,0,hr,pointer,C.POINTER(pointer))(instance,C.byref(iid),C.byref(settings)))
        class Color(C.Structure):_fields_=[(k,C.c_ubyte) for k in ('a','r','g','b')]
        color=Color()
        checked(method(settings,6,hr,C.c_int,C.POINTER(Color))(settings,5,C.byref(color)))
        return f'#{color.r:02x}{color.g:02x}{color.b:02x}'
    finally:
        if settings:method(settings,2,W.ULONG)(settings)
        if instance:method(instance,2,W.ULONG)(instance)
        if text:delete(text)
        if status>=0:uninitialize()

def _rgb(color):return tuple(int(color[i:i+2],16)/255 for i in (1,3,5))
def _hex(rgb):return '#'+''.join(f'{round(max(0,min(1,v))*255):02x}' for v in rgb)
def _mix(first,second,amount):return tuple(a*(1-amount)+b*amount for a,b in zip(first,second))
def _luminance(rgb):return sum(weight*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for weight,v in zip((.2126,.7152,.0722),rgb))
def contrast(first,second):
    a,b=sorted((_luminance(_rgb(first)),_luminance(_rgb(second))))
    return (b+.05)/(a+.05)

@lru_cache(maxsize=128)
def accent_palette(color,dark):
    """Lightly tinted surfaces, with readable accent text for any chosen RGB."""
    rgb=_rgb(accent_color(color))
    palette={key:_hex(_mix(_rgb(base),rgb,amount)) for key,base,amount in (
        ('bg','#181818' if dark else '#f7f7f7',.035),
        ('sidebar','#202020' if dark else '#f0f0f0',.05),
        ('card','#262626' if dark else '#ffffff',.035 if dark else 0),
        ('line','#424242' if dark else '#dddddd',.12),
        ('text','#f0f0f0' if dark else '#282828',.025),
        ('muted','#b3b3b3' if dark else '#686868',.025),
        ('selection','#303030' if dark else '#efefef',.16))}
    target=_rgb('#ffffff' if dark else '#000000')
    # Include the selected-row surface because the accent is used as its text.
    for step in range(101):
        candidate=_hex(_mix(rgb,target,step/100))
        if min(contrast(candidate,palette[key]) for key in ('bg','card','selection'))>=4.5:break
    palette['accent']=candidate
    palette['accent_text']=max(('#ffffff','#111111'),key=lambda value:contrast(value,candidate))
    return palette


def saved_theme_mode(preferences):
    mode=preferences.get('theme_mode')
    if mode in THEME_MODES:return mode
    legacy=preferences.get('dark')
    if type(legacy) is bool:return 'dark' if legacy else 'light'
    return 'system'


def read_system_appearance():
    dark=False;motion=True
    if sys.platform=='win32':
        import winreg
        import ctypes as C
        from ctypes import wintypes as W
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
                value,_=winreg.QueryValueEx(key,'AppsUseLightTheme');dark=value==0
        except OSError:pass
        try:
            function=C.WinDLL('user32').SystemParametersInfoW
            function.argtypes=[W.UINT,W.UINT,C.c_void_p,W.UINT];function.restype=W.BOOL
            enabled=W.BOOL(True)
            if function(0x1042,0,C.byref(enabled),0):motion=bool(enabled.value)
        except OSError:pass
    return dark,motion
