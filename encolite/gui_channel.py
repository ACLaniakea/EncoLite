"""Bounded outbound pipe; a slow window process cannot block tray controls."""
from collections import deque
import json
import threading


class GuiChannel:
    def __init__(self, process):
        self.process=process
        self.pending=deque()
        self.condition=threading.Condition()
        self.closed=False
        self.thread=threading.Thread(target=self._write,name='EncoLite-UI-Send',daemon=True)
        self.thread.start()

    def send(self, data):
        with self.condition:
            if self.closed:return False
            kind=data.get('type')
            if kind=='state' and self.pending and self.pending[-1].get('type')=='state':
                self.pending[-1]=data
            else:
                if len(self.pending)>=32:
                    # Coalesce stale state without dropping user commands.
                    for old in tuple(self.pending):
                        if old.get('type')=='state':self.pending.remove(old);break
                    else:return False
                self.pending.append(data)
            self.condition.notify()
            return True

    def stop(self):
        with self.condition:
            self.closed=True
            self.pending.clear()
            self.condition.notify()

    def _write(self):
        try:
            while True:
                with self.condition:
                    while not self.pending and not self.closed:self.condition.wait()
                    if self.closed:return
                    data=self.pending.popleft()
                self.process.stdin.write(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
                self.process.stdin.flush()
        except (BrokenPipeError,OSError,ValueError):
            pass
        finally:
            self.stop()
            try:self.process.stdin.close()
            except (OSError,ValueError):pass
