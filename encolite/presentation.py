"""Presentation adapters keep the Bluetooth controller independent of a GUI."""
from pathlib import Path


class SlintPresentation:
    def __init__(self):
        self.types = None

    def model(self, values, typename=None):
        import slint
        if typename:
            if self.types is None:
                self.types = slint.load_file(Path(__file__).resolve().parents[1] / 'ui/types.slint')
            values = [getattr(self.types, typename)(**value) for value in values]
        return slint.ListModel(values)

    def image(self, path):
        import slint
        return slint.Image.load_from_path(path)


class JsonPresentation:
    def model(self, values, typename=None):
        return list(values)

    def image(self, path):
        return str(path)


class SlintTimer:
    def __init__(self):
        import slint
        self.timer = slint.Timer()

    @property
    def running(self):
        return self.timer.running

    def start(self, seconds, callback, *, repeat=False):
        import slint
        from datetime import timedelta
        self.timer.start(slint.TimerMode.Repeated if repeat else slint.TimerMode.SingleShot,
                         timedelta(seconds=seconds), callback)

    def stop(self):
        self.timer.stop()


class SlintScheduler:
    def timer(self):
        return SlintTimer()
