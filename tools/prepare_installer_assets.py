"""Export the existing 256 px app artwork for native MSI bitmap controls."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]


def prepare(root=ROOT):
    from prepare_python import VERSION
    host=root/f'.tools/python-{VERSION}-embed-amd64/python.exe'
    packages=root/'.tools/qt-probe/packages'
    assert host.exists() and (packages/'PySide6/QtGui.pyd').exists(), 'Prepare Python and Qt first'
    code='import sys,runpy;sys.dont_write_bytecode=True;sys.path.insert(0,'+repr(str(packages))+');sys.argv=["prepare_installer_assets","--render"];runpy.run_path('+repr(str(root/'tools/prepare_installer_assets.py'))+',run_name="__main__")'
    subprocess.run([str(host),'-c',code],cwd=root,check=True,timeout=30)
    return root/'build/installer-assets'


def render():
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor,QImage,QPainter
    out=ROOT/'build/installer-assets';out.mkdir(parents=True,exist_ok=True)
    source=QImage(str(ROOT/'ui/assets/app-icon.png'))
    assert (source.width(),source.height())==(256,256)
    # Keep every source pixel; only composite alpha against the white header.
    icon=QImage(256,256,QImage.Format.Format_RGB32);icon.fill(QColor('#ffffff'))
    painter=QPainter(icon);painter.drawImage(0,0,source);painter.end()
    assert icon.convertToFormat(QImage.Format.Format_RGB888).save(str(out/'icon.bmp'),'BMP')
    banner=QImage(740,112,QImage.Format.Format_RGB32);banner.fill(QColor('#ffffff'))
    painter=QPainter(banner);painter.fillRect(QRect(24,32,4,40),QColor('#19654f'));painter.end()
    assert banner.convertToFormat(QImage.Format.Format_RGB888).save(str(out/'header.bmp'),'BMP')
    metadata={'source_pixels':[256,256],'icon_pixels':[256,256],'header_pixels':[740,112],
              'source_sha256':hashlib.sha256((ROOT/'ui/assets/app-icon.png').read_bytes()).hexdigest(),
              'assets':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'icon.bmp',out/'header.bmp')}}
    (out/'assets.json').write_text(json.dumps(metadata,indent=2),'utf-8')


if __name__=='__main__':
    if '--render' in sys.argv:render()
    else:prepare()
