"""Read the Windows input desktop when foreground assertions cannot run."""
import ctypes as c,json
from ctypes import wintypes as w
u=c.WinDLL('user32',use_last_error=True);k=c.WinDLL('kernel32')
u.GetForegroundWindow.restype=w.HWND
u.OpenInputDesktop.argtypes=[w.DWORD,w.BOOL,w.DWORD];u.OpenInputDesktop.restype=w.HANDLE
u.GetThreadDesktop.argtypes=[w.DWORD];u.GetThreadDesktop.restype=w.HANDLE
u.GetUserObjectInformationW.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)]
u.CloseDesktop.argtypes=[w.HANDLE]
def name(handle):
    text=c.create_unicode_buffer(256);size=w.DWORD()
    if handle and u.GetUserObjectInformationW(handle,2,text,c.sizeof(text),c.byref(size)):return text.value
    return None
input_desktop=u.OpenInputDesktop(0,False,1)
error=c.get_last_error() if not input_desktop else None
thread_desktop=u.GetThreadDesktop(k.GetCurrentThreadId())
print(json.dumps({'foreground':u.GetForegroundWindow(),'input_desktop':name(input_desktop),'input_desktop_error':error,'thread_desktop':name(thread_desktop)}))
if input_desktop:u.CloseDesktop(input_desktop)
wts=c.WinDLL('wtsapi32');session=w.DWORD()
k.ProcessIdToSessionId(k.GetCurrentProcessId(),c.byref(session))
wts.WTSQuerySessionInformationW.argtypes=[w.HANDLE,w.DWORD,c.c_int,c.POINTER(c.c_void_p),c.POINTER(w.DWORD)]
wts.WTSFreeMemory.argtypes=[c.c_void_p]
for info,label in ((8,'connection_state'),(25,'session_info_ex')):
    data=c.c_void_p();size=w.DWORD()
    if wts.WTSQuerySessionInformationW(None,session.value,info,c.byref(data),c.byref(size)):
        try:
            raw=c.string_at(data,size.value)
            print(json.dumps({'session':session.value,'query':label,'size':size.value,'prefix_ints':[int.from_bytes(raw[i:i+4],'little') for i in range(0,min(size.value,28),4)]}))
        finally:wts.WTSFreeMemory(data)
