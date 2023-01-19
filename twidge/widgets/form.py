from rich.table import Table
from rich.text import Text

from twidge.core import DispatchBuilder, RunBuilder
from twidge.widgets.base import FocusManager
from twidge.widgets.editors import EditString


class Form:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, labels: list[str]):
        self.labels = labels
        self.fm = FocusManager(
            *(EditString(multiline=False, overflow="wrap") for _ in labels)
        )

    @property
    def result(self):
        return {l: w.result for l, w in zip(self.labels, self.fm.widgets)}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for l, w in zip(self.labels, self.fm.widgets):
            t.add_row(Text(l, style="bright_green"), w)
        return t

    @dispatch.on("tab")
    def focus_advance(self):
        self.fm.forward()

    @dispatch.on("shift+tab")
    def focus_back(self):
        self.fm.back()

    @dispatch.default
    def passthrough(self, event):
        self.fm.focused.dispatch(event)
