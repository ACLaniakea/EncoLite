"""Roll back only our isolated test install if its uninstaller was blocked."""
from pathlib import Path
import os,shutil,winreg
ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'.install-test/Enco Lite'
key_path=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A0A57009-2B4F-490E-AB44-80C02964E3DD}_is1'
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
        location=Path(winreg.QueryValueEx(key,'InstallLocation')[0])
    assert location.resolve()==target.resolve(),'Refusing to touch a non-test installation'
    winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER,key_path,winreg.KEY_WOW64_64KEY,0)
    group=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Enco Lite'
    for name in ('Enco Lite.lnk','快捷控制.lnk','卸载 Enco Lite.lnk'):
        (group/name).unlink(missing_ok=True)
    if group.exists() and not any(group.iterdir()):group.rmdir()
except FileNotFoundError:pass
if target.parent.exists():shutil.rmtree(target.parent)
print('Removed only isolated test files, shortcuts and uninstall registration',flush=True)
