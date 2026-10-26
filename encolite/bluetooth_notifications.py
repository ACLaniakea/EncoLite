"""Bluetooth ACL notifications delivered to the existing native tray window.

No polling thread or graphical runtime. ABI: Microsoft bthdef.h / dbt.h;
https://learn.microsoft.com/windows/win32/bluetooth/bluetooth-and-wm-devicechange-messages
"""
import ctypes as C
import uuid


HCI_EVENT = uuid.UUID('fc240062-1541-49be-b463-84c4dcd7bf7f').bytes_le


class BroadcastHandle(C.Structure):
    _fields_ = [('size', C.c_uint32), ('kind', C.c_uint32), ('reserved', C.c_uint32),
                ('handle', C.c_void_p), ('notification', C.c_void_p),
                ('guid', C.c_ubyte * 16), ('name_offset', C.c_int32), ('data', C.c_ubyte * 1)]


def decode_hci_event(data):
    """Copy/validate native data during WM_DEVICECHANGE, before deferring it."""
    offset = BroadcastHandle.data.offset
    if len(data) < offset + 10:
        return None
    record = BroadcastHandle.from_buffer_copy(data[:C.sizeof(BroadcastHandle)])
    if record.size != len(data) or record.kind != 6 or bytes(record.guid) != HCI_EVENT:
        return None
    # BTH_HCI_EVENT_INFO: BTH_ADDR, UCHAR connectionType, UCHAR connected.
    if data[offset + 8] != 1:  # Ignore SCO voice and LE events.
        return None
    return int.from_bytes(data[offset:offset + 8], 'little'), bool(data[offset + 9])


class BluetoothNotifications:
    def __init__(self, hwnd):
        from ctypes import wintypes as W
        from .bluetooth_windows import api, bt
        self.hwnd = hwnd
        self.handles = {}
        self.first = api(bt, 'BluetoothFindFirstRadio', W.HANDLE, C.c_void_p, C.POINTER(W.HANDLE))
        self.next = api(bt, 'BluetoothFindNextRadio', W.BOOL, W.HANDLE, C.POINTER(W.HANDLE))
        self.end = api(bt, 'BluetoothFindRadioClose', W.BOOL, W.HANDLE)
        self.close_handle = api(C.WinDLL('kernel32'), 'CloseHandle', W.BOOL, W.HANDLE)
        user = C.WinDLL('user32', use_last_error=True)
        self.register = api(user, 'RegisterDeviceNotificationW', W.HANDLE, W.HWND, C.c_void_p, W.DWORD)
        self.unregister = api(user, 'UnregisterDeviceNotification', W.BOOL, W.HANDLE)
        self.refresh()

    def refresh(self):
        """Re-register after adapter removal/addition; fallback discovery still runs."""
        from ctypes import wintypes as W
        self.close()
        params = C.c_uint32(4)
        radio = W.HANDLE()
        search = self.first(C.byref(params), C.byref(radio))
        if not search:
            return
        try:
            while True:
                handle = radio.value
                record = BroadcastHandle(size=C.sizeof(BroadcastHandle), kind=6, handle=handle)
                notification = self.register(self.hwnd, C.byref(record), 0)
                if notification:
                    self.handles[handle] = notification
                else:
                    self.close_handle(handle)
                radio = W.HANDLE()
                if not self.next(search, C.byref(radio)):
                    break
        finally:
            self.end(search)

    def event(self, wparam, lparam):
        if wparam != 0x8006 or not lparam:  # DBT_CUSTOMEVENT
            return None
        size = C.c_uint32.from_address(lparam).value
        if not BroadcastHandle.data.offset + 10 <= size <= 4096:
            return None
        data = C.string_at(lparam, size)
        record = BroadcastHandle.from_buffer_copy(data[:C.sizeof(BroadcastHandle)])
        if self.handles.get(record.handle) != record.notification:
            return None
        return decode_hci_event(data)

    def close(self):
        for handle, notification in self.handles.items():
            self.unregister(notification)
            self.close_handle(handle)
        self.handles.clear()
