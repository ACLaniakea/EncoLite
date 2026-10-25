"""Windows paired-device discovery and bounded RFCOMM sockets.

Uses documented Bluetooth/Winsock ABIs. No subprocess, registry writes, pairing
changes, channel sweep, or third-party Bluetooth service is required.
"""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import threading
import time
import uuid
from .model_catalog import is_earbud_candidate


def api(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, args
    return fn


bt = C.WinDLL("bthprops.cpl", use_last_error=True)
ws = C.WinDLL("ws2_32", use_last_error=True)


class SystemTime(C.Structure):
    _fields_=[(name,W.WORD) for name in ("year","month","weekday","day","hour","minute","second","milliseconds")]


class DeviceInfo(C.Structure):
    _fields_ = [("size",W.DWORD),("address",C.c_ulonglong),("device_class",W.ULONG),
                ("connected",W.BOOL),("remembered",W.BOOL),("authenticated",W.BOOL),
                ("last_seen",SystemTime),("last_used",SystemTime),("name",W.WCHAR*248)]


class SearchParams(C.Structure):
    _fields_ = [("size",W.DWORD),("authenticated",W.BOOL),("remembered",W.BOOL),
                ("unknown",W.BOOL),("connected",W.BOOL),("inquiry",W.BOOL),
                ("timeout",C.c_ubyte),("radio",W.HANDLE)]


first_device = api(bt,"BluetoothFindFirstDevice",W.HANDLE,C.POINTER(SearchParams),C.POINTER(DeviceInfo))
next_device = api(bt,"BluetoothFindNextDevice",W.BOOL,W.HANDLE,C.POINTER(DeviceInfo))
close_find = api(bt,"BluetoothFindDeviceClose",W.BOOL,W.HANDLE)


@dataclass(frozen=True)
class Device:
    address: int
    name: str
    connected: bool
    authenticated: bool


def discover():
    """Read Windows' paired classic-Bluetooth devices, without active inquiry."""
    assert C.sizeof(DeviceInfo) == 560 and C.sizeof(SearchParams) == 40
    params=SearchParams(size=C.sizeof(SearchParams),authenticated=True,remembered=True,connected=True)
    info=DeviceInfo(size=C.sizeof(DeviceInfo))
    handle=first_device(C.byref(params),C.byref(info))
    if not handle:
        error=C.get_last_error()
        if error in (0,259,1168):
            return []
        raise OSError(error,"无法读取蓝牙设备，请检查蓝牙适配器")
    devices={}
    try:
        while True:
            name=info.name.strip()
            if is_earbud_candidate(name,info.device_class) and (info.remembered or info.authenticated):
                devices[info.address]=Device(info.address,name,bool(info.connected),bool(info.authenticated))
            info=DeviceInfo(size=C.sizeof(DeviceInfo))
            if not next_device(handle,C.byref(info)):
                break
    finally:
        close_find(handle)
    return sorted(devices.values(),key=lambda d:(not d.connected,d.name))


class Guid(C.Structure):
    _fields_=[("data",C.c_ubyte*16)]

    @classmethod
    def parse(cls,value):
        return cls((C.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le))


class SockAddrBth(C.Structure):
    _pack_=1
    _fields_=[("family",C.c_ushort),("address",C.c_ulonglong),("service",Guid),("port",C.c_ulong)]


class FdSet(C.Structure):
    _fields_=[("count",C.c_uint),("sockets",C.c_size_t*64)]


class TimeVal(C.Structure):
    _fields_=[("seconds",C.c_long),("microseconds",C.c_long)]


startup=api(ws,"WSAStartup",C.c_int,C.c_ushort,C.c_void_p)
last_error=api(ws,"WSAGetLastError",C.c_int)
new_socket=api(ws,"socket",C.c_size_t,C.c_int,C.c_int,C.c_int)
connect_socket=api(ws,"connect",C.c_int,C.c_size_t,C.c_void_p,C.c_int)
ioctl=api(ws,"ioctlsocket",C.c_int,C.c_size_t,C.c_long,C.POINTER(C.c_ulong))
select=api(ws,"select",C.c_int,C.c_int,C.POINTER(FdSet),C.POINTER(FdSet),C.POINTER(FdSet),C.POINTER(TimeVal))
get_option=api(ws,"getsockopt",C.c_int,C.c_size_t,C.c_int,C.c_int,C.c_void_p,C.POINTER(C.c_int))
send=api(ws,"send",C.c_int,C.c_size_t,C.c_void_p,C.c_int,C.c_int)
recv=api(ws,"recv",C.c_int,C.c_size_t,C.c_void_p,C.c_int,C.c_int)
shutdown=api(ws,"shutdown",C.c_int,C.c_size_t,C.c_int)
close_socket=api(ws,"closesocket",C.c_int,C.c_size_t)
INVALID=C.c_size_t(-1).value
MELODY="0000079a-d102-11e1-9b23-00025b00a5a5"
_started=False
_startup_lock=threading.Lock()


class Rfcomm:
    def __init__(self):
        self.socket=INVALID
        self._lock=threading.Lock()

    def connect(self,device,*,service=MELODY,channel=0,timeout=2.5,cancel=None):
        global _started
        assert C.sizeof(SockAddrBth)==30 and SockAddrBth.port.offset==26
        with _startup_lock:
            if not _started:
                result=startup(0x202,C.create_string_buffer(512))
                if result:
                    raise OSError(result,"无法初始化蓝牙通信")
                _started=True
        sock=new_socket(32,1,3)
        if sock==INVALID:
            raise OSError(last_error(),"无法创建蓝牙控制通道")
        with self._lock:
            self.socket=sock
        try:
            nonblocking=C.c_ulong(1)
            if ioctl(sock,C.c_long(0x8004667e).value,C.byref(nonblocking)):
                raise OSError(last_error(),"无法设置连接超时")
            endpoint=SockAddrBth(32,device.address,Guid.parse(service),channel)
            result=connect_socket(sock,C.byref(endpoint),C.sizeof(endpoint))
            error=last_error() if result else 0
            if error not in (0,10035,10036,10037):
                raise OSError(error,"无法连接耳机控制服务")
            deadline=time.monotonic()+timeout
            while result:
                if cancel and cancel.is_set():
                    raise ConnectionAbortedError("连接已取消")
                left=deadline-time.monotonic()
                if left<=0:
                    raise TimeoutError("耳机控制服务连接超时")
                writable=FdSet(1,(C.c_size_t*64)(sock))
                failed=FdSet(1,(C.c_size_t*64)(sock))
                tv=TimeVal(0,int(min(left,.15)*1_000_000))
                ready=select(0,None,C.byref(writable),C.byref(failed),C.byref(tv))
                if ready<0:
                    raise OSError(last_error(),"蓝牙连接已中断")
                if ready:
                    option=C.c_int();size=C.c_int(C.sizeof(option))
                    if get_option(sock,0xffff,0x1007,C.byref(option),C.byref(size)) or option.value:
                        raise OSError(option.value or last_error(),"耳机拒绝控制连接")
                    break
            return self
        except BaseException:
            self.close()
            raise

    def write(self,data,timeout=2):
        deadline=time.monotonic()+timeout
        offset=0
        while offset<len(data):
            sock=self.socket
            if sock==INVALID:
                raise ConnectionError("耳机已断开")
            block=C.create_string_buffer(data[offset:])
            sent=send(sock,block,len(data)-offset,0)
            if sent>0:
                offset+=sent
            elif sent<0 and last_error()==10035:
                if time.monotonic()>deadline:
                    raise TimeoutError("发送命令超时")
                writable=FdSet(1,(C.c_size_t*64)(sock));tv=TimeVal(0,100_000)
                select(0,None,C.byref(writable),None,C.byref(tv))
            else:
                raise ConnectionError(f"蓝牙发送失败 ({last_error()})")

    def read(self,timeout=.5):
        sock=self.socket
        if sock==INVALID:
            raise ConnectionError("耳机已断开")
        readable=FdSet(1,(C.c_size_t*64)(sock));tv=TimeVal(int(timeout),int(timeout%1*1_000_000))
        result=select(0,C.byref(readable),None,None,C.byref(tv))
        if result==0:
            return b""
        if result<0:
            raise ConnectionError("蓝牙读取已中断")
        buffer=C.create_string_buffer(4096)
        received=recv(sock,buffer,len(buffer),0)
        if received<=0:
            if received<0 and last_error()==10035:
                return b""
            raise ConnectionError("耳机控制连接已关闭")
        return buffer.raw[:received]

    def close(self):
        with self._lock:
            sock,self.socket=self.socket,INVALID
        if sock!=INVALID:
            shutdown(sock,2)
            close_socket(sock)
