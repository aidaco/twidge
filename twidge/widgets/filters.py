import re
import typing

from rich.console import Group
from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from twidge.core import DispatchBuilder, RunBuilder
from twidge.widgets.wrappers import FocusManager


class Indexer:
    """Retrieve items from a list by indices."""

    RE_NUMSEQ = re.compile(r"\W*(\d+)\W*")
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, options: list, fmt: typing.Callable[[typing.Any], str] = str):
        self.query = ""
        self.full = list(options)
        self.last = self.filter()
        self.fmt = fmt

    def reset(self):
        self.last = []
        self.last = self.filter()

    @property
    def result(self):
        return self.last

    def __rich__(self):
        table = Table.grid(padding=(0, 1, 0, 0))
        table.add_column()
        table.add_column()
        for i, o in enumerate(self.full):
            if o in self.last:
                table.add_row(
                    Text(str(i + 1), style="cyan"), Text(self.fmt(o), style="on green")
                )
            else:
                table.add_row(Text(str(i + 1), style="cyan"), f"{o}")
        return Group(Text(self.query, style="bold yellow"), table)

    def filter(self):
        try:
            return [
                self.full[int(m.group(1)) - 1]
                for m in self.RE_NUMSEQ.finditer(self.query)
            ]
        except (ValueError, IndexError):
            return []

    @dispatch.on("ctrl+d")
    def clear(self):
        self.query = ""
        self.reset()

    @dispatch.on("backspace")
    def backspace(self):
        self.query = self.query[:-1]
        self.reset()

    @dispatch.on("space")
    def space(self):
        self.query += " "

    @dispatch.default
    def default(self, key):
        if len(key) == 1:
            self.query += str(key)
            self.last = self.filter()


class Searcher:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, options: list, fmt: typing.Callable[[typing.Any], str] = str):
        self.query = ""
        self.full = list(options)
        self.last = self.full
        self.fmt = fmt

    def reset(self):
        self.last = self.full
        self.last = self.filter()

    def filter(self):
        return [e for e in self.last if re.search(self.query, e, re.IGNORECASE)]

    @property
    def result(self):
        return self.last

    def __rich__(self):
        if len(self.last) == 0:
            content = "No matches."
        else:
            content = Group(*(self.fmt(e) for e in self.last), fit=True)
        return Group(Text(self.query, style="grey0 on grey100"), content)

    @dispatch.on("ctrl+d")
    def clear(self):
        self.query = ""
        self.reset()

    @dispatch.on("backspace")
    def backspace(self):
        self.query = self.query[:-1]
        self.reset()

    @dispatch.default
    def default(self, key):
        if key == "space":
            key = " "
        if len(key) == 1:
            self.query += str(key)
            self.last = self.filter()


class Selector:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, options: list, fmt: typing.Callable[[typing.Any], str] = str):
        self.options = list(options)
        self.selected = [False] * len(self.options)
        self.fm = FocusManager(*self.options)
        self.fmt = fmt

    def __rich__(self):
        return Group(
            *(
                Styled(
                    self.fmt(opt),
                    style=f'{"bold yellow" if self.fm.focus==i else ""}{" on blue" if sel else ""}',
                )
                for i, (opt, sel) in enumerate(zip(self.options, self.selected))
            )
        )

    @dispatch.on("enter", "space")
    def select(self):
        self.selected[self.fm.focus] = not self.selected[self.fm.focus]

    @dispatch.on("tab")
    def focus_advance(self):
        self.fm.forward()

    @dispatch.on("shift+tab")
    def focus_back(self):
        self.fm.back()

    @dispatch.default
    def passthrough(self, event):
        self.fm.dispatch(event)

    @property
    def result(self):
        return [opt for opt, sel in zip(self.options, self.selected) if sel]


__all__ = ["Indexer", "Searcher", "Selector"]
