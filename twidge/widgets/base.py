import re
import sys
import typing
from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from twidge.core import BytesReader, DispatchBuilder, Event, RunBuilder

# --- Simple Widgets


class Echo:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, stop_key: str = "ctrl+c"):
        self.history = ""

    @dispatch.on("ctrl+c")
    def stop(self):
        self.run.stop()

    @dispatch.default
    def add(self, key: str):
        self.history += key

    def __rich__(self):
        return f"{self.history}"

    @property
    def result(self):
        return self.history


class EchoBytes:
    run = RunBuilder(reader=BytesReader)
    dispatch = DispatchBuilder()

    def __init__(self):
        self.history = b""

    @dispatch.on(b"\x7f")
    def stop(self):
        self.run.stop()

    @dispatch.default
    def default(self, key: str):
        self.history += key

    def __rich__(self):
        return f"{self.history}"

    @property
    def result(self):
        return self.history


@dataclass
class Toggle:
    value: bool = True
    true: RenderableType = "True"
    false: RenderableType = "False"
    run: typing.ClassVar = RunBuilder()
    dispatch: typing.ClassVar = DispatchBuilder()

    @dispatch.on("space")
    def toggle(self):
        self.value = not self.value

    @dispatch.default
    def ignore(self, key):
        pass

    def __rich__(self):
        return self.true if self.value else self.false

    @property
    def result(self):
        return self.value


@dataclass
class Button:
    content: RenderableType
    target: typing.Callable
    run: typing.ClassVar = RunBuilder()
    dispatch: typing.ClassVar = DispatchBuilder()

    @dispatch.on("enter")
    def trigger(self):
        return self.target()

    def __rich__(self):
        return self.content


T = typing.TypeVar("T")


class Searcher:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, options: list[T], fmt: typing.Callable[[T], str] = str):
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


class Indexer:
    """Retrieve items from a list by indices."""

    RE_NUMSEQ = re.compile(r"\W*(\d+)\W*")
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, options: list[T], fmt: typing.Callable[[T], str] = str):
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


class Selector:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, options: list[T], fmt: typing.Callable[[T], str] = str):
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


# ---

# --- Wrapper widgets


class Closeable:
    def close(self):
        self.run.stop()

    def crash(self):
        sys.exit(1)

    def __init__(self, content, close: str = "ctrl+w", crash: str = "ctrl+c"):
        self.close_event = close
        self.crash_event = crash
        self.content = content

    run = RunBuilder()

    def dispatch(self, event: Event):
        match event:
            case self.close_event:
                self.close()
            case self.crash_event:
                self.crash()
            case _:
                self.content.dispatch(event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        return self.content


class Framed:
    run = RunBuilder()

    def __init__(self, content):
        self.content = content

    def dispatch(self, event):
        return self.content.dispatch(event)

    def __rich__(self):
        return Panel.fit(self.content)

    @property
    def result(self):
        return self.content.result


class Labelled:
    def __init__(self, label, content):
        self.label = label
        self.content = content

    def dispatch(self, event):
        return self.content.dispatch(event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        t.add_row(Text(self.label, style="bold cyan"), self.content)
        return t


# --- Focusing


class FocusManager:
    def __init__(self, *widgets, focus: int = 0):
        self.widgets = list(widgets)
        self.focus = focus
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")
        for w in self.widgets[self.focus + 1 :]:
            getattr(w, "dispatch", lambda e: None)("blur")

    @property
    def focused(self):
        return self.widgets[self.focus]

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


class FocusGroup:
    dispatch = DispatchBuilder()

    def __init__(self, *widgets):
        self.fm = FocusManager(*widgets)

    def __rich__(self):
        return Group(*self.fm.widgets)

    @property
    def result(self):
        return [w.result for w in self.fm.widgets]

    @dispatch.on("tab")
    def focus_advance(self):
        self.fm.forward()

    @dispatch.on("shift+tab")
    def focus_back(self):
        self.fm.back()

    @dispatch.default
    def passthrough(self, event):
        self.fm.focused.dispatch(event)


class Focusable:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, content, focus_style: Style = Style.parse("bold yellow")):
        self.content = content
        self.focus_style = focus_style

    @dispatch.on("focus")
    def on_focus(self):
        self.focus = True

    @dispatch.on("blur")
    def on_blur(self):
        self.focus = False

    @dispatch.default
    def passthrough(self, event):
        return self.content.dispatch(event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        return Styled(self.content, self.focus_style) if self.focus else self.content


class FocusableFramed:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, content):
        self.content = content
        self.focus = False

    @dispatch.on("focus")
    def on_focus(self):
        self.focus = True

    @dispatch.on("blur")
    def on_blur(self):
        self.focus = False

    @dispatch.default
    def default(self, event):
        self.content.dispatch(event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        focus = getattr(self, "focus", False)
        return Panel.fit(self.content, border_style="green" if focus else "")


# ---
