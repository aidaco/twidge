from typing import Callable
from rich.table import Table
from rich.text import Text

from twidge.core import DispatchBuilder, RunBuilder
from twidge.widgets.editors import EditString
from twidge.widgets.wrappers import FocusManager


class Form:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, labels: list, fmt: Callable = str, label_style='bright_green', field_style=''):
        self.labels = labels
        self.fmt = fmt
        self.fm = FocusManager(
            *(EditString(multiline=False, overflow="wrap", text_style=field_style, cursor_line_style=field_style) for _ in labels)
        )
        self.label_style = label_style
        self.field_style = field_style

    @property
    def result(self):
        return {l: w.result for l, w in zip(self.labels, self.fm.widgets)}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for l, w in zip(self.labels, self.fm.widgets):
            t.add_row(Text(self.fmt(l), style=self.label_style), w)

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


__all__ = ["Form"]
