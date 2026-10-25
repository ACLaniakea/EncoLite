"""Exercise actual title-bar clicks and closing before the first rendered frame."""
from pathlib import Path
import json, sys, time, traceback
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / '.tools/qt-probe/packages')]
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
from PySide6.QtCore import QMetaObject, QPointF, QTimer, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from encolite.qt_desktop import Desktop
app = Desktop(ROOT, read_pipe=False)
# Production releases the GUI process after its final window closes. Keep this
# fixture's event loop alive between independent cases, without changing dismiss.
close_view = app.close_view
app.close_view = lambda kind, exiting=False, **kw: close_view(kind, exiting=False, **kw)
report = {'checks': [], 'errors': [], 'clicks': [], 'real_hardware': False}
state = {'connected': True, 'model_name': 'OPPO Enco X3', 'noise_options': [],
         'fast_mode': False, 'system_motion': True, 'dark': False}
def check(name):
    report['checks'].append(name); print('PASS', name, flush=True)
def later(ms, fn):
    def run():
        try: fn()
        except Exception:
            report['errors'].append(traceback.format_exc()); app.quit()
    QTimer.singleShot(ms, run)
def until(predicate, fn, label):
    deadline = time.monotonic() + 3
    def poll():
        if predicate(): fn()
        elif time.monotonic() > deadline: raise TimeoutError(label)
        else: later(10, poll)
    later(0, poll)
def title_close(win):
    pending = [win.contentItem()]
    while pending:
        item = pending.pop()
        if item.property('modelData') == 'close' and item.property('down') is not None:
            return item
        pending.extend(item.childItems())
    raise AssertionError('close button missing')
cases = [(kind, fast) for fast in (False, True) for kind in ('notice', 'quick', 'main')]
def cycle(index=0):
    if index == len(cases): return early_close()
    kind, fast = cases[index]; state['fast_mode'] = fast
    app.receive({'type': 'state', 'state': state, 'preferences': {}})
    app.show(kind)
    win = app.windows[kind]
    def click():
        button = title_close(win)
        p = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
        report['clicks'].append({'kind': kind, 'fast': fast, 'x': p.x(), 'y': p.y(),
                                'width': button.width(), 'height': button.height()})
        assert button.width() >= 30 and button.height() >= 25, report['clicks'][-1]
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p)
        until(lambda: kind not in app.windows, closed, 'title close ' + kind)
    def closed():
        check(f'{kind} title close click dismisses the window (fast={fast})')
        later(50, lambda: cycle(index + 1))
    until(lambda: win.opacity() == 1 and kind in app.ready, click, 'window presented')
def early_close(index=0):
    if index == 3: return interrupted()
    kind = ('notice', 'quick', 'main')[index]
    state['fast_mode'] = False
    app.receive({'type': 'state', 'state': state, 'preferences': {}})
    app.show(kind); win = app.windows[kind]
    # User close can arrive before frameSwapped, or its fallback timer.
    app.close_view(kind, exiting=False)
    app.first_frame(kind, win)
    def done():
        check(kind + ': first frame cannot cancel an explicit close during opening')
        later(30, lambda: early_close(index + 1))
    until(lambda: kind not in app.windows, done, 'close before first frame: ' + kind)
def interrupted():
    app.show('notice'); win = app.windows['notice']
    def close():
        app.close_view('notice')
        # Model an animation interrupted by a late presentation/compositor event.
        QMetaObject.invokeMethod(win, 'present')
        until(lambda: 'notice' not in app.windows, interrupted_done, 'interrupted animation fallback')
    until(lambda: win.opacity() == 1 and 'notice' in app.ready, close, 'present')
def interrupted_done():
    check('interrupted closing animation still releases the notification window')
    app.show('notice'); win = app.windows['notice']
    def close():
        app.close_view('notice'); app.notice_hover(True); app.show('notice'); app.notice_hover(False)
        assert 'notice' in app.closing and not app.notice_timer.isActive()
        until(lambda: 'notice' not in app.windows, notice_done, 'explicit close survives hover/show')
    until(lambda: win.opacity() == 1 and 'notice' in app.ready, close, 'present')
def notice_done():
    check('hover and pending notifications cannot reopen an explicitly closed notice')
    app.show('notice'); win = app.windows['notice']
    def timeout():
        app.close_view('notice', reason='timeout'); app.notice_hover(True)
        assert 'notice' not in app.closing and not app.notice_timer.isActive()
        later(450, lambda: timeout_done(win))
    until(lambda: win.opacity() == 1 and 'notice' in app.ready, timeout, 'present')
def timeout_done(win):
    assert app.windows.get('notice') is win and win.opacity() == 1
    check('hover can still cancel an automatic timeout without stale timers closing it')
    app.close_view('notice', animate=False); app.show('quick'); win = app.windows['quick']
    def reopen():
        app.close_view('quick'); app.show('quick')
        later(450, lambda: reopen_done(win))
    until(lambda: win.opacity() == 1 and 'quick' in app.ready, reopen, 'present')
def reopen_done(win):
    assert app.windows.get('quick') is win and win.opacity() == 1 and 'quick' not in app.closing
    check('explicitly reopening quick control cancels its old close deadline')
    app.close_view('quick', animate=False); app.quit()
app.receive({'type': 'state', 'state': state, 'preferences': {}})
later(0, cycle)
later(15000, lambda: (_ for _ in ()).throw(TimeoutError('close test timeout')))
try: app.run()
finally:
    report['result'] = 'FAIL' if report['errors'] or len(report['checks']) != 13 else 'PASS'
    out = ROOT / 'verification/qt-close'; out.mkdir(exist_ok=True, parents=True)
    (out/'report.json').write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps(report), flush=True)
    if report['result'] != 'PASS': raise SystemExit(1)
