"""Small Win32 WebView2 COM adapter, using only the official signed loader.

The vtable slots and callback IIDs come from Microsoft.Web.WebView2 1.0.4258.31.
No host objects, remote pages, Python extensions or HTTP server are exposed.
"""
import ctypes as C
from ctypes import wintypes as W
import base64, json, os, sys, traceback, uuid
from . import windows_shell as shell

HRESULT=C.c_long
ole=C.OleDLL('ole32')
ole.CoInitializeEx.argtypes=[C.c_void_p,W.DWORD]
ole.CoTaskMemFree.argtypes=[C.c_void_p]
IUnknown=uuid.UUID('00000000-0000-0000-C000-000000000046').bytes_le


def call(pointer,index,*arguments,types=(),result=HRESULT):
    table=C.cast(pointer,C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result,C.c_void_p,*types)(table[index])(pointer,*arguments)


def checked(status):
    if status<0:raise OSError(f'WebView2 HRESULT 0x{status&0xffffffff:08X}')
    return status


class Handler:
    def __init__(self,iid,callback,types):
        self.iid=uuid.UUID(iid).bytes_le;self.refs=1
        @C.WINFUNCTYPE(HRESULT,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p))
        def query(this,requested,output):
            if C.string_at(requested,16) in (IUnknown,self.iid):output[0]=this;self.refs+=1;return 0
            output[0]=None;return -2147467262
        @C.WINFUNCTYPE(W.ULONG,C.c_void_p)
        def add(this):self.refs+=1;return self.refs
        @C.WINFUNCTYPE(W.ULONG,C.c_void_p)
        def release(this):self.refs=max(0,self.refs-1);return self.refs
        @C.WINFUNCTYPE(HRESULT,C.c_void_p,*types)
        def invoke(this,*args):
            try:callback(*args)
            except Exception:traceback.print_exc();return -2147467259
            return 0
        self.callbacks=(query,add,release,invoke)
        self.table=(C.c_void_p*4)(*[C.cast(f,C.c_void_p).value for f in self.callbacks])
        self.instance=(C.c_void_p*1)(C.addressof(self.table));self.pointer=C.cast(self.instance,C.c_void_p)


class Environment:
    def __init__(self,loader,data,ready,failed):
        checked(ole.CoInitializeEx(None,2))
        self.loader=C.WinDLL(str(loader));self.pointer=None;self.waiting=[];self.handlers=[];self.failed=failed
        self.version='';self.ready=ready
        version=C.c_void_p()
        fn=shell.api(self.loader,'GetAvailableCoreWebView2BrowserVersionString',HRESULT,W.LPCWSTR,C.POINTER(C.c_void_p))
        checked(fn(None,C.byref(version)))
        try:self.version=C.wstring_at(version)
        finally:ole.CoTaskMemFree(version)
        def completed(status,pointer):
            if status<0 or not pointer:failed(f'WebView2 environment 0x{status&0xffffffff:08X}');return
            self.pointer=pointer;call(pointer,1,result=W.ULONG);ready()
        handler=Handler('4E8A3389-C9D8-4BD2-B6B5-124FEE6CC14D',completed,(HRESULT,C.c_void_p));self.handlers.append(handler)
        create=shell.api(self.loader,'CreateCoreWebView2EnvironmentWithOptions',HRESULT,W.LPCWSTR,W.LPCWSTR,C.c_void_p,C.c_void_p)
        checked(create(None,str(data),None,handler.pointer))

    def close(self):
        if self.pointer:call(self.pointer,2,result=W.ULONG);self.pointer=None


class Browser:
    def __init__(self,environment,hwnd,html,message,created):
        self.environment=environment;self.hwnd=hwnd;self.html=html;self.message=message;self.created=created
        self.allowed_sources={'about:blank','data:text/html;charset=utf-8;base64,'+base64.b64encode(html.encode('utf-8')).decode('ascii')}
        self.controller=None;self.core=None;self.handlers=[];self.closed=False
        handler=Handler('6C4819F3-C9B7-4260-8127-C9F5BDE7F68C',self.controller_created,(HRESULT,C.c_void_p));self.handlers.append(handler)
        checked(call(environment.pointer,3,hwnd,handler.pointer,types=(W.HWND,C.c_void_p)))

    def controller_created(self,status,pointer):
        if status<0 or not pointer:
            self.environment.failed(f'WebView2 controller 0x{status&0xffffffff:08X}');return
        if self.closed:return
        self.controller=pointer;call(pointer,1,result=W.ULONG)
        core=C.c_void_p();checked(call(pointer,25,C.byref(core),types=(C.POINTER(C.c_void_p),)));self.core=core.value
        settings=C.c_void_p();checked(call(self.core,3,C.byref(settings),types=(C.POINTER(C.c_void_p),)))
        try:
            for slot in (8,10,12,14,16,18):checked(call(settings.value,slot,False,types=(W.BOOL,)))
        finally:call(settings.value,2,result=W.ULONG)
        def web_message(sender,args):
            text=C.c_void_p();source=C.c_void_p()
            checked(call(args,3,C.byref(source),types=(C.POINTER(C.c_void_p),)))
            try:
                origin=C.wstring_at(source)
                if os.environ.get('ENCOLITE_DIAGNOSTICS')=='1':print('web message source',origin[:60],file=sys.stderr,flush=True)
                if origin not in self.allowed_sources:return
            finally:ole.CoTaskMemFree(source)
            checked(call(args,5,C.byref(text),types=(C.POINTER(C.c_void_p),)))
            try:self.message(json.loads(C.wstring_at(text)))
            finally:ole.CoTaskMemFree(text)
        handler=Handler('57213F19-00E6-49FA-8E07-898EA01ECBD2',web_message,(C.c_void_p,C.c_void_p));self.handlers.append(handler)
        token=C.c_longlong();checked(call(self.core,34,handler.pointer,C.byref(token),types=(C.c_void_p,C.POINTER(C.c_longlong))))
        def navigation(sender,args):
            text=C.c_void_p();checked(call(args,3,C.byref(text),types=(C.POINTER(C.c_void_p),)))
            try:
                uri=C.wstring_at(text);allowed=uri in self.allowed_sources
                if os.environ.get('ENCOLITE_DIAGNOSTICS')=='1':print('navigation',uri[:60],allowed,file=sys.stderr,flush=True)
            finally:ole.CoTaskMemFree(text)
            if not allowed:checked(call(args,8,True,types=(W.BOOL,)))
        handler=Handler('9ADBE429-F36D-432B-9DDC-F8881FBD76E3',navigation,(C.c_void_p,C.c_void_p));self.handlers.append(handler)
        checked(call(self.core,7,handler.pointer,C.byref(token),types=(C.c_void_p,C.POINTER(C.c_longlong))))
        self.resize();checked(call(pointer,4,True,types=(W.BOOL,)))
        checked(call(self.core,6,self.html,types=(W.LPCWSTR,)))
        self.created()

    def resize(self):
        if not self.controller:return
        rect=W.RECT();shell.GetClientRect(self.hwnd,C.byref(rect))
        checked(call(self.controller,6,rect,types=(W.RECT,)))

    def send(self,payload):
        if self.core and not self.closed:checked(call(self.core,32,json.dumps(payload,ensure_ascii=False),types=(W.LPCWSTR,)))

    def close(self):
        self.closed=True
        if self.controller:call(self.controller,24);call(self.controller,2,result=W.ULONG);self.controller=None
        if self.core:call(self.core,2,result=W.ULONG);self.core=None

    def capture(self,path,completed):
        stream=C.c_void_p()
        create=shell.api(C.WinDLL('shlwapi'),'SHCreateStreamOnFileEx',HRESULT,W.LPCWSTR,W.DWORD,W.DWORD,W.BOOL,C.c_void_p,C.POINTER(C.c_void_p))
        checked(create(str(path),0x1042,0x80,True,None,C.byref(stream)))
        def saved(status):
            call(stream.value,2,result=W.ULONG);checked(status);completed()
        handler=Handler('697E05E9-3D8F-45FA-96F4-8FFE1EDEDAF5',saved,(HRESULT,));self.handlers.append(handler)
        checked(call(self.core,30,0,stream,handler.pointer,types=(C.c_int,C.c_void_p,C.c_void_p)))
