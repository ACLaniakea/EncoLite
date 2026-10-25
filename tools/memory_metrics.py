"""Read this application's process memory without loading optional extensions."""
import ctypes as C
from ctypes import wintypes as W


def process_memory(pid):
    class Counters(C.Structure):
        _fields_=[('cb',W.DWORD),('faults',W.DWORD),
            *[(name,C.c_size_t) for name in ('peak_working_set','working_set','peak_paged',
                'paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private_bytes')]]
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.K32GetProcessMemoryInfo.argtypes=[W.HANDLE,C.POINTER(Counters),W.DWORD]
    kernel.CloseHandle.argtypes=[W.HANDLE]
    handle=kernel.OpenProcess(0x410,False,pid)
    if not handle:raise C.WinError(C.get_last_error())
    try:
        info=Counters(cb=C.sizeof(Counters))
        if not kernel.K32GetProcessMemoryInfo(handle,C.byref(info),info.cb):raise C.WinError(C.get_last_error())
        return {'pid':pid,'working_set':info.working_set,'private_bytes':info.private_bytes}
    finally:kernel.CloseHandle(handle)


def process_tree_memory(pid):
    class Entry(C.Structure):
        _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',C.c_size_t),
            ('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),
            ('flags',W.DWORD),('name',W.WCHAR*260)]
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];kernel.CreateToolhelp32Snapshot.restype=W.HANDLE
    kernel.Process32FirstW.argtypes=[W.HANDLE,C.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[W.HANDLE,C.POINTER(Entry)];kernel.CloseHandle.argtypes=[W.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0);entry=Entry(size=C.sizeof(Entry));rows=[]
    if snapshot==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    try:
        success=kernel.Process32FirstW(snapshot,C.byref(entry))
        while success:
            rows.append((entry.pid,entry.parent,entry.name));success=kernel.Process32NextW(snapshot,C.byref(entry))
    finally:kernel.CloseHandle(snapshot)
    selected={pid};last=set()
    while last!=selected:
        last=selected.copy();selected.update(child for child,parent,_ in rows if parent in selected)
    values=[]
    for child,_,name in rows:
        if child in selected:
            try:values.append({**process_memory(child),'name':name})
            except OSError:pass
    return {'processes':values,'working_set_sum':sum(p['working_set'] for p in values),
        'private_bytes_sum':sum(p['private_bytes'] for p in values)}
