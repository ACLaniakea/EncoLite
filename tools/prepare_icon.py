"""Render the vector application mark at native Windows icon sizes."""
from pathlib import Path
import struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]


def prepare(root=ROOT):
    from prepare_python import VERSION
    host=root/f'.tools/python-{VERSION}-embed-amd64/python.exe'
    packages=root/'.tools/qt-probe/packages'
    assert host.exists() and (packages/'PySide6/QtSvg.pyd').exists(), 'Prepare Python and Qt first'
    code='import sys,runpy;sys.dont_write_bytecode=True;sys.path.insert(0,'+repr(str(packages))+');sys.argv=["prepare_icon","--render"];runpy.run_path('+repr(str(root/'tools/prepare_icon.py'))+',run_name="__main__")'
    subprocess.run([str(host),'-c',code],cwd=root,check=True,timeout=30)


def render():
    from PySide6.QtCore import QBuffer,QByteArray,QIODevice
    from PySide6.QtGui import QImage,QPainter
    from PySide6.QtSvg import QSvgRenderer
    source=(ROOT/'ui/assets/app-icon.svg').read_bytes();parts=[]
    for size in (16,20,24,32,48,64,128,256):
        artwork=source.replace(b'stroke-width="18"',b'stroke-width="22"') if size<=24 else source
        renderer=QSvgRenderer(QByteArray(artwork));assert renderer.isValid()
        image=QImage(size,size,QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
        painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing);renderer.render(painter);painter.end()
        buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);assert image.save(buffer,'PNG');data=bytes(buffer.data())
        if size==256:(ROOT/'ui/assets/app-icon.png').write_bytes(data)
        parts.append((size,data))
    offset=6+16*len(parts);entries=[]
    for size,data in parts:
        entries.append(struct.pack('<BBBBHHII',size if size<256 else 0,size if size<256 else 0,0,0,1,32,len(data),offset));offset+=len(data)
    (ROOT/'ui/assets/app-icon.ico').write_bytes(struct.pack('<HHH',0,1,len(parts))+b''.join(entries)+b''.join(data for _,data in parts))


if __name__=='__main__':
    if '--render' in sys.argv:render()
    else:prepare()
