import re
import sys
import typing

import pandas as pd
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.styled import Styled
from rich.table import Table

from twidge.core import chbreak, chreader, keystr

BUBBLE = object()


class TableDispatcher:
    def __init__(
        self,
        table: dict[typing.Any, typing.Callable[[typing.Any], typing.Any]]
        | None = None,
        default: typing.Callable[[typing.Any], typing.Any] = lambda e: BUBBLE,
        inst=None,
    ):
        self.table = table if table is not None else {}
        self._default = default
        self.inst = inst

    def dispatch(self, event):
        if res := self.table.get(event, lambda self: BUBBLE)(self.inst) is BUBBLE:
            res = self._default(self.inst, event)
            # all relevant data should be made accessible with inst, event
        return res

    def __call__(self, event):
        return self.dispatch(event)

    def on(self, *events) -> typing.Callable[[typing.Callable], typing.Callable]:
        def decorate(fn: typing.Callable) -> typing.Callable:
            for e in events:
                self.table[e] = fn
            return fn

        return decorate

    def default(self, fn: typing.Callable) -> typing.Callable:
        self._default = fn
        return fn

    def update(self, mapping, default=None):
        self.table.update(mapping)
        if default is not None:
            self._default = default
        return self

    def __get__(self, obj, obj_type=None):
        return type(self)(table=self.table, default=self._default, inst=obj)

    def autoignore(self):
        return self.update({}, default=_auto_ignore)

    def autofocus(self):
        return self.update(
            {
                "focus": _auto_onfocus,
                "blur": _auto_onblur,
            }
        )

    def autoexit(self, *keys: str):
        return self.update({key: _auto_onexit for key in keys})

    def autoclick(self):
        return self.update({"space": _auto_onclick, "enter": _auto_onclick})

    def autofilter(self):
        return self.update(
            {
                "ctrl+d": _auto_filterreset,
                "backspace": _auto_filterbackspace,
            },
            default=_auto_filterinsert,
        )


def _auto_ignore(self, key):
    pass


def _auto_onexit(self):
    self.runner.exit()


def _auto_onclick(self):
    self.click()


def _auto_onfocus(self):
    self.focus = True


def _auto_onblur(self):
    self.focus = False


def _auto_filterreset(self):
    self.query = ""
    self.last = self.full


def _auto_filterbackspace(self):
    self.query = self.query[:-1]
    self.last = self.full
    self.last = self.filter()


def _auto_filterinsert(self, key):
    if key == "space":
        key = " "
    if len(key) == 1:
        self.query += str(key)
        self.last = self.filter()


class Runner:
    class Exit(Exception):
        ...

    def __init__(self, inst=None):
        self.inst = inst

    def __get__(self, obj, obj_type=None):
        return type(self)(inst=obj)

    def exit(self):
        raise self.Exit()

    def run(
        self,
        stdin: int = sys.stdin.fileno(),
        reader: typing.Callable[[int], typing.Callable[[], bytes | None]] = chreader,
        console: None | Console = None,
    ):
        self.console = console or Console()
        try:
            with Live(
                self.inst,
                console=self.console,
                transient=True,
                auto_refresh=False,
            ) as live:
                with chbreak(stdin=stdin, reader=reader) as readch:
                    while ch := readch():
                        self.inst.dispatch(keystr(ch))
                        live.refresh()
        except self.Exit:
            ...

        return getattr(self.inst, "result", lambda: None)()

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


class Wrapper:
    def __init__(self, content):
        self.content = content

    def __rich__(self):
        return self.content

    def dispatch(self, key):
        if hasattr(self.content, "dispatch"):
            self.content.dispatch(key)

    def result(self):
        if hasattr(self.content, "result"):
            return self.content.result()
        else:
            return self.content


class Echo:
    def __init__(self):
        self.keys = []

    def dispatch(self, key):
        self.keys.append(key)

    def __rich__(self):
        chars = (f"'{ch}'" for ch in self.keys)
        return "[cyan]" + " ".join(chars) + "[/]"


class Toggle:
    dispatch = TableDispatcher().autoclick().autoignore()

    def __init__(self, value: bool, on_true, on_false):
        self.value = value
        self.on_true = on_true
        self.on_false = on_false

    def __rich__(self):
        return self.on_true if self.value else self.on_false

    def click(self):
        self.value = not self.value

    def result(self):
        return self.value


class Button:
    dispatch = TableDispatcher().autoclick().autoignore()

    def __init__(self, content, target: typing.Callable):
        self.content = content
        self.click = target

    def __rich__(self):
        return Panel.fit(self.content)


class Close(Wrapper):
    run = Runner()

    def __init__(self, key: str, content):
        self.key = key
        super().__init__(content)

    def dispatch(self, key):
        if key == self.key:
            self.run.exit()
        else:
            super().dispatch(key)


class Escape(Wrapper):
    run = Runner()

    def __init__(self, seq: list[str], content):
        self.seq = seq
        self.keys = [""] * len(seq)
        super().__init__(content)

    def dispatch(self, event):
        self.keys = self.keys[1:] + [event]
        if self.keys == self.seq:
            raise SystemExit()
        else:
            super().dispatch(event)


class FocusHighlight(Wrapper):
    def __rich__(self):
        focus = getattr(self, "focus", False)
        return Styled(self.content, style="yellow" if focus else "")

    def dispatch(self, event):
        if event == "focus":
            self.focus = True
        elif event == "blur":
            self.focus = False
        else:
            super().dispatch(event)


class Framed(Wrapper):
    def __rich__(self):
        focus = getattr(self, "focus", False)
        return Panel.fit(self.content, border_style="green" if focus else "")

    def dispatch(self, event):
        if event == "focus":
            self.focus = True
        elif event == "blur":
            self.focus = False
        else:
            super().dispatch(event)


class Labelled(Wrapper):
    def __init__(self, label: str, content):
        self.label = label
        super().__init__(content)

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        t.add_row(f"[bold yellow]{self.label}[/]", self.content)
        return t


class FocusManager:
    def __init__(self, *widgets, focus: int = 0):
        self.widgets = list(widgets)
        self.focus = focus
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")
        for w in self.widgets[self.focus + 1 :]:
            getattr(w, "dispatch", lambda e: None)("blur")

    def forward(self):
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("blur")
        if self.focus == len(self.widgets) - 1:
            self.focus = 0
        else:
            self.focus += 1
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")

    def back(self):
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("blur")
        if self.focus == 0:
            self.focus = len(self.widgets) - 1
        else:
            self.focus -= 1
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")

    def dispatch(self, key):
        if hasattr(self.widgets[self.focus], "dispatch"):
            self.widgets[self.focus].dispatch(key)


class FocusGroup:
    dispatch = TableDispatcher()

    def __init__(self, *widgets):
        self.fm = FocusManager(*widgets)

    def __rich__(self):
        return Group(*self.fm.widgets)

    def result(self):
        return [w.result() for w in self.fm.widgets]

    @dispatch.on("tab")
    def focus_advance(self):
        self.fm.forward()

    @dispatch.on("shift+tab")
    def focus_back(self):
        self.fm.back()

    @dispatch.default
    def passthrough(self, event):
        self.fm.dispatch(event)


class ListSearcher:
    dispatch = TableDispatcher().autofilter()

    def __init__(self, options: list[str]):
        self.full = list(options)
        self.last = self.full

    def filter(self):
        return [e for e in self.last if re.search(self.query, e, re.IGNORECASE)]

    def result(self):
        return self.last

    def __rich__(self):
        if len(self.last) == 0:
            content = "No matches."
        else:
            content = Group(*self.last, fit=True)
        return Group(f"[bold cyan]{self.query}[/]", content)


class DataFrameSearcher:
    dispatch = TableDispatcher().autofilter()

    def __init__(self, df: pd.DataFrame, sep="\t", case=False):
        self.full = df
        self.last = df
        self.case = case
        self.sep = sep
        self.query = ""

    def __rich__(self):
        if len(self.subset) == 0:
            content = "No matches."
        else:
            content = Table(
                *self.subset,
                expand=True,
                pad_edge=False,
                padding=0,
            )
            self.subset.head(10).apply(lambda r: content.add_row(*r), axis=1)
        return Panel(content, title=self.query, title_align="left", style="bold cyan")

    def filter(self) -> pd.DataFrame:
        ft = self.last.agg(self.sep.join, axis=1)
        return self.last[ft.str.contains(self.query, case=self.case)]


class ListIndexer:
    """Retrieve items from a list by indices."""

    RE_NUMSEQ = re.compile(r"\W*(\d+)\W*")
    dispatch = TableDispatcher().autofilter()

    def __init__(self, options: list[str]):
        self.full = list(options)
        self.last = self.full

    def result(self):
        return self.last

    def __rich__(self):
        table = Table.grid(padding=(0, 1, 0, 0))
        table.add_column()
        table.add_column()
        for i, o in enumerate(self.full):
            if o in self.last:
                table.add_row(f"[cyan]{i+1}[/]", f"[on green]{o}[/]")
            else:
                table.add_row(f"[cyan]{i+1}[/]", f"{o}")
        return Group(f"[bold yellow]{self.query}[/]", table)

    def filter(self):
        try:
            return [
                self.full[int(m.group(1)) - 1]
                for m in self.RE_NUMSEQ.finditer(self.query)
            ]
        except (ValueError, IndexError):
            return []


class ListSelector:
    dispatch = TableDispatcher()

    def __init__(self, *options: str):
        self.options = list(options)
        self.selected = [False] * len(self.options)
        self.fm = FocusManager(*self.options)

    def __rich__(self):
        return Group(
            *(
                Styled(
                    opt,
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

    def result(self):
        return [opt for opt, sel in zip(self.options, self.selected) if sel]
