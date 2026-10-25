"""Production entry: native tray owner and a disposable Qt Quick UI process."""
from pathlib import Path
import argparse
import ctypes
import os
import sys
import traceback
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True


def main():
    parser=argparse.ArgumentParser(description='Enco Lite')
    parser.add_argument('--quick',action='store_true')
    parser.add_argument('--tray-only',action='store_true')
    parser.add_argument('--quit',action='store_true')
    parser.add_argument('--restart',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--remove-autostart',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--startup-folder',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--fixture',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--fixture-data',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--test-report',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--test-timeout',type=float,default=0,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.fixture and args.fixture_data:os.environ['ENCOLITE_DATA_DIR']=str(args.fixture_data.resolve())
    if sys.platform!='win32':
        raise RuntimeError('当前蓝牙后端和托盘集成支持 Windows')
    if args.remove_autostart:
        from encolite.autostart import WindowsStartup
        startup=WindowsStartup(ROOT,folder=args.startup_folder)
        startup.set_enabled(False)
        return
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('EncoLite.Desktop')
    from encolite import windows_shell as shell
    if args.quit:
        hwnd=shell.FindWindow('EncoLiteTray','Enco Lite tray')
        if hwnd:shell.PostMessage(hwnd,0x8002,3,0)
        return
    if args.restart:
        hwnd=shell.FindWindow('EncoLiteTray','Enco Lite tray')
        if hwnd:shell.PostMessage(hwnd,0x8002,3,0)
        deadline=time.monotonic()+15
        while True:
            if not shell.FindWindow('EncoLiteTray','Enco Lite tray'):
                mutex=shell.application_mutex()
                if mutex is not None:break
            if time.monotonic()>=deadline:raise RuntimeError('已有 Enco Lite 尚未退出，请从托盘退出后再打开新版本')
            time.sleep(.1)
    else:
        if shell.activate_existing(args.quick,args.tray_only):return
        mutex=shell.application_mutex()
        if mutex is None:
            shell.activate_existing(args.quick,args.tray_only)
            return
    from encolite.native_desktop import NativeDesktop
    app=NativeDesktop(ROOT,args)
    try:app.run()
    finally:app.close()


def run():
    try:main()
    except Exception:
        from encolite.preferences import data_directory
        log=data_directory()/'startup-error.log'
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text(traceback.format_exc(),'utf-8')
        if sys.stderr:traceback.print_exc()
        if not any(arg in sys.argv for arg in ('--fixture','--test-report','--remove-autostart')):
            ctypes.windll.user32.MessageBoxW(None,f'启动失败，详细信息已保存：\n{log}','Enco Lite',0x10)
        raise


if __name__=='__main__':run()
