"""Current-user Windows Startup shortcut, with no resident helper."""
from pathlib import Path
import os
import subprocess
import sys


def startup_folder():
    return Path(os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))/'Microsoft/Windows/Start Menu/Programs/Startup'


class WindowsStartup:
    def __init__(self,root,*,folder=None,store=None):
        self.root=Path(root).resolve()
        self.path=Path(folder) / 'Enco Lite.lnk' if folder is not None else startup_folder()/'Enco Lite.lnk'
        self.store=store

    def host(self):
        path=self.root/'python/pythonw.exe'
        return path if path.is_file() else self.root/'.tools/python-3.13.17-embed-amd64/pythonw.exe'

    def command(self,*,validate=False):
        host=self.host();entry=self.root/'desktop_entry.py'
        if validate and (not host.is_file() or not entry.is_file()):
            raise FileNotFoundError('缺少启动文件，请重新安装或解压 Enco Lite')
        value=subprocess.list2cmdline([str(host),str(entry),'--tray-only'])
        if validate and len(value.encode('utf-16-le'))//2>260:
            raise ValueError('当前目录过长，请将 Enco Lite 移到更短的路径后再开启自启动')
        return value

    def _store(self):
        if self.store is not None:return self.store
        if sys.platform!='win32':raise OSError('当前系统不支持 Windows 开机自启动')
        from . import shell_link
        return shell_link

    def read(self):
        if not self.path.is_file():return None
        target,args=self._store().read(self.path)
        return subprocess.list2cmdline([target])+' '+args

    def enabled(self):
        value=self.read()
        return isinstance(value,str) and value.strip().casefold()==self.command().casefold()

    def set_enabled(self,enabled):
        if type(enabled) is not bool:raise ValueError('自启动开关无效')
        if enabled:
            self.command(validate=True);self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix('.tmp')
            try:
                self._store().write(temporary,self.host(),subprocess.list2cmdline([str(self.root/'desktop_entry.py'),'--tray-only']),self.root)
                temporary.replace(self.path)
            finally:temporary.unlink(missing_ok=True)
        elif self.enabled():self.path.unlink(missing_ok=True)
        if self.enabled()!=enabled:raise OSError('Windows 未能保存自启动设置，请重试')
