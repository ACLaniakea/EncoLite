"""Opt-in diagnostic bitmap export of this process's own window only."""
import ctypes as C
from ctypes import wintypes as W
import struct
from . import windows_shell as s


def capture(hwnd,path):
    owner=W.DWORD();s.GetWindowThreadProcessId(hwnd,C.byref(owner))
    import os
    if owner.value!=os.getpid():raise ValueError('Only this process can export its window')
    rect=W.RECT();s.GetWindowRect(hwnd,C.byref(rect));width=rect.right-rect.left;height=rect.bottom-rect.top
    gdi=C.WinDLL('gdi32');getdc=s.api(s.user,'GetDC',W.HDC,W.HWND);release=s.api(s.user,'ReleaseDC',C.c_int,W.HWND,W.HDC)
    dc=getdc(hwnd);memory=s.api(gdi,'CreateCompatibleDC',W.HDC,W.HDC)(dc)
    bits=C.c_void_p();header=struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,width*height*4,0,0,0,0)
    info=C.create_string_buffer(header)
    bitmap=s.api(gdi,'CreateDIBSection',W.HANDLE,W.HDC,C.c_void_p,W.UINT,C.POINTER(C.c_void_p),W.HANDLE,W.DWORD)(dc,info,0,C.byref(bits),None,0)
    select=s.api(gdi,'SelectObject',W.HANDLE,W.HDC,W.HANDLE);old=select(memory,bitmap)
    try:
        if not s.api(s.user,'PrintWindow',W.BOOL,W.HWND,W.HDC,W.UINT)(hwnd,memory,0):raise OSError('PrintWindow failed')
        pixels=C.string_at(bits,width*height*4)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(struct.pack('<2sIHHI',b'BM',54+len(pixels),0,0,54)+header+pixels)
    finally:
        select(memory,old);s.api(gdi,'DeleteObject',W.BOOL,W.HANDLE)(bitmap)
        s.api(gdi,'DeleteDC',W.BOOL,W.HDC)(memory);release(hwnd,dc)
