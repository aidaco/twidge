from rich.table import Table

from twidge.widgets.base import FocusManager, TableDispatcher
from twidge.widgets.editors import EditString


class Form:
    dispatch = TableDispatcher()

    def __init__(self, content: list[str]):
        self.labels = content
        self.fm = FocusManager(
            *(EditString(multiline=False, overflow="wrap") for k in content)
        )

    def result(self):
        return {l: w.result() for l, w in zip(self.labels, self.fm.widgets)}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for l, w in zip(self.labels, self.fm.widgets):
            t.add_row(f"[bold yellow]{l}[/]", w)
        return t

    @dispatch.on("tab")
    def focus_advance(self):
        self.fm.forward()

    @dispatch.on("shift+tab")
    def focus_back(self):
        self.fm.back()

    @dispatch.default
    def passthrough(self, event):
        self.fm.dispatch(event)
