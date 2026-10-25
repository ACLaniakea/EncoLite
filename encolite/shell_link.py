"""Minimal native Shell Link COM calls; no scripting host or extra dependency."""
from contextlib import contextmanager
import ctypes as C
import uuid

class GUID(C.Structure):
    _fields_=[('a',C.c_uint32),('b',C.c_uint16),('c',C.c_uint16),('d',C.c_ubyte*8)]
    def __init__(self,value):super().__init__();C.memmove(C.byref(self),uuid.UUID(value).bytes_le,16)

def checked(result):
    if result<0:raise OSError('Windows 快捷方式操作失败 · 0x%08x'%(result&0xffffffff))

def call(pointer,index,types,*args):
    table=C.cast(pointer,C.POINTER(C.POINTER(C.c_void_p))).contents
    result=C.WINFUNCTYPE(C.c_long,C.c_void_p,*types)(table[index])(pointer,*args)
    checked(result)

@contextmanager
def link():
    ole=C.WinDLL('ole32');ole.CoInitializeEx.argtypes=[C.c_void_p,C.c_uint];ole.CoInitializeEx.restype=C.c_long
    status=ole.CoInitializeEx(None,2)
    if status not in (0,1,-2147417850):checked(status)
    pointer=C.c_void_p();persist=C.c_void_p()
    try:
        ole.CoCreateInstance.argtypes=[C.POINTER(GUID),C.c_void_p,C.c_uint,C.POINTER(GUID),C.POINTER(C.c_void_p)]
        ole.CoCreateInstance.restype=C.c_long
        checked(ole.CoCreateInstance(C.byref(GUID('00021401-0000-0000-c000-000000000046')),None,1,
            C.byref(GUID('000214f9-0000-0000-c000-000000000046')),C.byref(pointer)))
        call(pointer,0,[C.POINTER(GUID),C.POINTER(C.c_void_p)],C.byref(GUID('0000010b-0000-0000-c000-000000000046')),C.byref(persist))
        yield pointer,persist
    finally:
        for item in (persist,pointer):
            if item.value:call(item,2,[])
        if status in (0,1):ole.CoUninitialize()

def read(path):
    with link() as (pointer,persist):
        call(persist,5,[C.c_wchar_p,C.c_uint],str(path),0)
        target=C.create_unicode_buffer(32768);arguments=C.create_unicode_buffer(32768)
        call(pointer,3,[C.c_wchar_p,C.c_int,C.c_void_p,C.c_uint],target,len(target),None,4)
        call(pointer,10,[C.c_wchar_p,C.c_int],arguments,len(arguments))
        return target.value,arguments.value

def write(path,target,arguments,root):
    with link() as (pointer,persist):
        call(pointer,20,[C.c_wchar_p],str(target))
        call(pointer,11,[C.c_wchar_p],arguments)
        call(pointer,9,[C.c_wchar_p],str(root))
        call(pointer,7,[C.c_wchar_p],'Enco Lite')
        call(pointer,17,[C.c_wchar_p,C.c_int],str(root/'ui/assets/app-icon.ico'),0)
        call(persist,6,[C.c_wchar_p,C.c_int],str(path),1)
