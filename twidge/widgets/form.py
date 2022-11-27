from rich.table import Table

from twidge.core import Dispatch, Run
from twidge.widgets.base import FocusManager
from twidge.widgets.editors import EditString


class Form:
    run = Run()
    dispatch = Dispatch()

    def __init__(self, content: list[str]):
        self.labels = content
        self.fm = FocusManager(
            *(EditString(multiline=False, overflow="wrap") for k in content)
        )

    @property
    def result(self):
        return [w.result for w in self.fm.widgets]

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for l, w in zip(self.labels, self.fm.widgets):
            t.add_row(f"[bold cyan]{l}[/]", w)
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
