"""Isolated representative Qt Quick render probe; never connects to Bluetooth."""
from pathlib import Path
import json
import sys
import traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'verification/qt-probe'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT / '.tools/qt-probe/packages'), str(ROOT / 'tools')]
try:
    from PySide6.QtCore import QTimer, QUrl, qVersion
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    app = QGuiApplication(sys.argv)
    QQuickStyle.setStyle('FluentWinUI3')
    engine = QQmlApplicationEngine()
    pictures = list((ROOT / 'ui').rglob('*'))
    image = next((p for p in pictures if p.suffix == '.png' and 'x3' in p.name.lower()), ROOT / 'ui/assets/device-neutral.svg')
    engine.rootContext().setContextProperty('productImage', QUrl.fromLocalFile(str(image)))
    engine.load(QUrl.fromLocalFile(str(ROOT / 'tools/qt_probe.qml')))
    assert engine.rootObjects(), 'QML did not create a window'
    window = engine.rootObjects()[0]
    frames = [0]
    window.frameSwapped.connect(lambda: frames.__setitem__(0, frames[0] + 1))

    def finish():
        from memory_metrics import process_memory
        import os
        report = {'result': 'PASS' if window.isVisible() and frames[0] else 'FAIL',
                  'qt_version': qVersion(), 'style': QQuickStyle.name(), 'frames_presented': frames[0],
                  'memory': process_memory(os.getpid()), 'real_device_tested': False,
                  'representative_controls_only': True}
        report['screenshot_saved'] = window.grabWindow().save(str(OUT / 'main.png'))
        (OUT / 'window.json').write_text(json.dumps(report, indent=2), 'utf-8')
        app.quit()

    QTimer.singleShot(40000, finish)
    raise SystemExit(app.exec())
except Exception:
    (OUT / 'failure.txt').write_text(traceback.format_exc(), 'utf-8')
    raise
