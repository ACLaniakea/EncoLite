"""Win32 message-loop scheduling, with no graphical runtime loaded."""
import heapq
import itertools
import queue
import time
import traceback


class NativeTimer:
    def __init__(self, loop):
        self.loop=loop
        self.running=False
        self.generation=0

    def start(self, seconds, callback, *, repeat=False):
        self.stop()
        self.running=True
        self.loop.schedule(self,max(.001,seconds),callback,repeat)

    def stop(self):
        self.running=False
        self.generation+=1
        self.loop.arm()


class NativeLoop:
    def __init__(self):
        self.hwnd=None
        self.tasks=queue.Queue()
        self.timers=[]
        self.serial=itertools.count()
        self.closed=False

    def timer(self):
        return NativeTimer(self)

    def post(self, callback):
        if self.closed:return
        self.tasks.put(callback)
        if self.hwnd:
            from .windows_shell import PostMessage
            PostMessage(self.hwnd,0x8003,0,0)

    def schedule(self, timer, seconds, callback, repeat):
        heapq.heappush(self.timers,(time.monotonic()+seconds,next(self.serial),timer,
                                   timer.generation,seconds,callback,repeat))
        self.arm()

    def arm(self):
        if not self.hwnd or self.closed:return
        from .windows_shell import KillTimer,SetTimer
        KillTimer(self.hwnd,2)
        while self.timers and (not self.timers[0][2].running or self.timers[0][2].generation!=self.timers[0][3]):
            heapq.heappop(self.timers)
        if self.timers:
            SetTimer(self.hwnd,2,max(1,round((self.timers[0][0]-time.monotonic())*1000)),None)

    def drain(self):
        try:
            for _ in range(512):
                try:callback=self.tasks.get_nowait()
                except queue.Empty:break
                callback()
            while self.timers and self.timers[0][0]<=time.monotonic():
                _,_,timer,generation,seconds,callback,repeat=heapq.heappop(self.timers)
                if not timer.running or timer.generation!=generation:continue
                if not repeat:timer.running=False
                callback()
                if repeat and timer.running and timer.generation==generation:
                    self.schedule(timer,seconds,callback,repeat)
        except Exception:
            traceback.print_exc()
        finally:
            self.arm()

    def run(self):
        import ctypes as C
        from ctypes import wintypes as W
        from .windows_shell import api,user
        get=api(user,'GetMessageW',W.BOOL,C.POINTER(W.MSG),W.HWND,W.UINT,W.UINT)
        translate=api(user,'TranslateMessage',W.BOOL,C.POINTER(W.MSG))
        dispatch=api(user,'DispatchMessageW',C.c_ssize_t,C.POINTER(W.MSG))
        message=W.MSG()
        self.drain()
        while True:
            result=get(C.byref(message),None,0,0)
            if result==0:break
            if result==-1:raise C.WinError(C.get_last_error())
            translate(C.byref(message));dispatch(C.byref(message))

    def quit(self):
        from .windows_shell import api,user
        self.closed=True
        api(user,'PostQuitMessage',None,__import__('ctypes').c_int)(0)
