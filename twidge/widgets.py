import functools
import re
import sys
import typing

import pandas as pd
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.segment import Segments
from rich.style import Style
from rich.table import Table

from twidge.core import chbreak, chreader, keystr


def on(*events):
    def decorate(fn: typing.Callable) -> typing.Callable:
        setattr(
            fn, "__dispatch_on__", getattr(fn, "__dispatch_on__", []) + list(events)
        )
        return fn

    return decorate


def default(fn: typing.Callable):
    setattr(fn, "__dispatch_on__", getattr(fn, "__dispatch_on__", []) + ["default"])
    return fn


class AutoDispatch:
    @functools.cached_property
    def __dispatch_table__(self):
        return {
            tag: meth
            for attr in dir(self)
            if attr != "__dispatch_table__"
            and callable((meth := getattr(self, attr, None)))
            and (tags := getattr(meth, "__dispatch_on__", None)) is not None
            for tag in tags
        }

    def dispatch(self, event):
        table = self.__dispatch_table__

        def default():
            table.get("default", lambda e: None)(event)

        table.get(event, default)()


class Exit(Exception):
    ...


class TUI(AutoDispatch):
    def __rich__(self):
        return ""

    def run(
        self,
        stdin: int = sys.stdin.fileno(),
        reader: typing.Callable[[int], typing.Callable[[], bytes | None]] = chreader,
        console: None | Console = None,
    ):
        self.console = console or Console()
        try:
            with Live(
                self, console=self.console, transient=True, auto_refresh=False
            ) as live:
                with chbreak(stdin=stdin, reader=reader) as readch:
                    while ch := readch():
                        self.dispatch(keystr(ch))
                        live.refresh()
        except Exit:
            ...

        return getattr(self, "result", lambda: None)()


class AutoFocus(AutoDispatch):
    """Subclasses are a assigned a managed self.focus: bool attribute."""

    @on("focus")
    def onfocus(self):
        self.focus = True

    @on("blur")
    def onblur(self):
        self.focus = False


class Echo(TUI):
    def __init__(self):
        self.keys = []

    def dispatch(self, key):
        self.keys.append(key)

    def __rich__(self):
        chars = (f"'{ch}'" for ch in self.keys)
        return "[cyan]" + " ".join(chars) + "[/]"


class Escape(TUI):
    def __init__(self, widget, key: str = "ctrl+c"):
        self.key = key
        self.widget = widget

    def __rich__(self):
        return self.widget

    def result(self):
        return self.widget.result()

    def dispatch(self, key):
        if key == self.key:
            raise Exit("Bye")
        else:
            if hasattr(self.widget, "dispatch"):
                self.widget.dispatch(key)


class Abort(TUI):
    def __init__(self, widget, seq: list[str] = ["escape", "escape", "escape"]):
        self.seq = seq
        self.keys = [""] * len(seq)
        self.widget = widget

    def __rich__(self):
        return self.widget

    def result(self):
        return self.widget.result()

    def dispatch(self, key):
        self.keys = self.keys[1:] + [key]
        if self.keys == self.seq:
            raise SystemExit()
        else:
            if hasattr(self.widget, "dispatch"):
                self.widget.dispatch(key)


class Framed(TUI):
    def __init__(self, content):
        self.content = content

    def __rich__(self):
        return Panel.fit(self.content)

    @default
    def passthrough(self, key):
        if hasattr(self.content, "dispatch"):
            self.content.dispatch(key)

    def result(self):
        if hasattr(self.content, "result"):
            return self.content.result()
        else:
            return self.content


class Labelled(TUI):
    def __init__(self, label, widget):
        self.widget = widget
        self.label = label

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        t.add_row(f"[bold yellow]{self.label}[/]", self.widget)
        return t

    def dispatch(self, key):
        if hasattr(self.widget, "dispatch"):
            self.widget.dispatch(key)

    def result(self):
        return self.widget.result()


class Toggle(TUI, AutoFocus):
    def __init__(self, value: bool, on_true, on_false):
        self.value = value
        self.on_true = on_true
        self.on_false = on_false
        self.focus = True

    def __rich_console__(self, console, options):
        if self.focus:
            return self.on_true if self.value else self.on_false
        else:
            return Segments.apply_style(console.render_lines(self.value), Style.null())

    @default
    def switch(self, key):
        self.value = not self.value

    def result(self):
        return self.value


class Button(TUI):
    def __init__(self, content, target: typing.Callable):
        self.content = content
        self.target = target
        self.focus = True

    def __rich__(self):
        return Panel.fit(self.content, style="green" if self.focus else "")

    @on("focus")
    def onfocus(self):
        self.focus = True

    @on("blur")
    def onblur(self):
        self.focus = False

    @on("enter")
    def click(self):
        self.target()

    @default
    def drop(self, key):
        ...


class FocusFramed(Framed, AutoFocus):
    """Adds a focus-responsive frame to a widget that would otherwise not respond."""

    def __init__(self, content):
        self.focus = True
        super().__init__(content)

    def __rich__(self):
        return Panel.fit(self.content, border_style="green" if self.focus else "")


class FocusGroup(TUI):
    def __init__(self, *widgets):
        self.widgets = list(widgets)
        self.focus = 0
        getattr(self.widgets[0], "dispatch", lambda e: None)("focus")
        for w in self.widgets[1:]:
            getattr(w, "dispatch", lambda e: None)("blur")

    def __rich__(self):
        return Group(*self.widgets)

    @on("tab")
    def focus_next(self):
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("blur")
        if self.focus == len(self.widgets) - 1:
            self.focus = 0
        else:
            self.focus += 1
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")

    @on("shift+tab")
    def focus_previous(self):
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("blur")
        if self.focus == 0:
            self.focus = len(self.widgets) - 1
        else:
            self.focus -= 1
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")

    @default
    def dispatch_to_focus(self, key):
        if hasattr(self.widgets[self.focus], "dispatch"):
            self.widgets[self.focus].dispatch(key)

    def result(self):
        return [w.result() for w in self.widgets]


class Menu(FocusGroup):
    def __init__(self, *options: str):
        self.options = list(options)
        super().__init__(*(FocusFramed(o) for o in options))

    @on("enter", "space")
    def click(self):
        raise Exit

    def result(self):
        if hasattr(self.options[self.focus], "result"):
            return self.options[self.focus].result()
        else:
            return self.options[self.focus]


class SearchList(TUI):
    def __init__(self, options: list[str]):
        self.options = options
        self.reset()

    def filter(self):
        return [e for e in self.subset if re.search(self.query, e, re.IGNORECASE)]

    def result(self):
        return self.subset

    def __rich__(self):
        if len(self.subset) == 0:
            content = "No matches."
        else:
            content = Group(*self.subset, fit=True)
        return Group(f"[bold cyan]{self.query}[/]", content)

    def refresh(self):
        self.subset = self.filter()

    def reset(self):
        """Resets to like-new."""
        self.query = ""
        self.subset = self.options
        self.refresh()

    def recalculate(self):
        """Keep query, reset options and rerun search."""
        self.subset = self.options
        self.refresh()

    @on("ctrl+d")
    def clear(self):
        self.reset()

    @on("backspace")
    def backspace(self):
        self.query = self.query[:-1]
        self.recalculate()

    @default
    def update(self, key):
        if len(k := key) == 1:
            self.query += str(k)
            self.refresh()


class SearchDataFrame(TUI):
    def __init__(self, df: pd.DataFrame, sep="\t", case=False):
        self.data = df
        self.subset = df
        self.case = case
        self.sep = sep
        self.full_text = df.agg(sep.join, axis=1)
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

    def search(self) -> pd.DataFrame:
        return self.subset[self.full_text.str.contains(self.query, case=self.case)]

    def refresh(self):
        if len(self.query) == 0:
            self.subset = self.data
            self.full_text = self.subset.agg(self.sep.join, axis=1)
        elif len(self.query) < 2:
            pass
        else:
            self.subset = self.search()
            self.full_text = self.subset.agg(self.sep.join, axis=1)

    @on("ctrl+d")
    def clear(self):
        self.query = ""
        self.refresh()

    @on("backspace")
    def backspace(self):
        self.query = self.query[:-1]
        self.refresh()

    @default
    def update(self, key):
        if len(k := key) == 1:
            self.query += str(k)
            self.refresh()


class SelectList(SearchList):
    RE_NUMSEQ = re.compile(r"\W*(\d+)\W*")

    def __rich__(self):
        table = Table.grid(padding=(0, 1, 0, 0))
        table.add_column()
        table.add_column()
        for i, o in enumerate(self.options):
            if o in self.subset:
                table.add_row(f"[cyan]{i+1}[/]", f"[on green]{o}[/]")
            else:
                table.add_row(f"[cyan]{i+1}[/]", f"{o}")
        return Group(f"[bold yellow]{self.query}[/]", table)

    def reset(self):
        self.query = ""
        self.subset = []

    @on("space")
    def space(self):
        self.update(" ")

    def filter(self):
        try:
            return [
                self.options[int(m.group(1)) - 1]
                for m in self.RE_NUMSEQ.finditer(self.query)
            ]
        except (ValueError, IndexError):
            return []
