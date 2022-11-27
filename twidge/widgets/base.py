import re
import sys
import typing

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.styled import Styled
from rich.table import Table

from twidge.core import BytesReader, Dispatch, Event, Run, SingleHandler

# --- Dispatch fragments


def ignore(event):
    pass


class IgnoreDispatch(Dispatch):
    """Dispatch that ignores events by default."""

    def __init__(self, *args, **kwargs):
        super().__init__(defaultfn=ignore)


# ---


# --- Simple Widgets


class Echo:
    def __init__(self):
        self.history = ""

    run = Run()
    dispatch = Dispatch()

    @dispatch.on("ctrl+c")
    def stop(self) -> None:
        self.run.stop()

    @dispatch.default
    def default(self, key: str):
        self.history += key

    def __rich__(self):
        return f"{self.history}"


class EchoBytes:
    def __init__(self):
        self.history = b""

    run = Run(reader=BytesReader)
    dispatch = Dispatch()

    @dispatch.on(b"\x7f")
    def stop(self):
        self.run.stop()

    @dispatch.default
    def default(self, key: str):
        self.history += key

    def __rich__(self):
        return f"{self.history}"


class Toggle:
    @property
    def result(self):
        return self.value

    def __init__(
        self,
        value: bool = True,
        true: RenderableType = "True",
        false: RenderableType = "False",
    ):
        self.value = value
        self.true = true
        self.false = false

    run = Run()
    dispatch = IgnoreDispatch()

    @dispatch.on("space")
    def toggle(self):
        self.value = not self.value

    def __rich__(self):
        return self.true if self.value else self.false


class Button:
    def __init__(self, content: RenderableType, target: typing.Callable):
        self.content = content
        self.target = target

    run = Run()
    dispatch = IgnoreDispatch()

    @dispatch.on("enter")
    def trigger(self):
        return self.target()

    def __rich__(self):
        return self.content


class Searcher:
    run = Run()
    dispatch = Dispatch()

    def __init__(self, options: list[str]):
        self.query = ""
        self.full = list(options)
        self.last = self.full

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
            content = Group(*self.last, fit=True)
        return Group(f"[bold cyan]{self.query}[/]", content)

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
    run = Run()
    dispatch = Dispatch()

    def __init__(self, options: list[str]):
        self.query = ""
        self.full = list(options)
        self.last = self.filter()

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
    run = Run()
    dispatch = Dispatch()

    def __init__(self, options: list[str]):
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

    @property
    def result(self):
        return [opt for opt, sel in zip(self.options, self.selected) if sel]


# ---

# --- Wrapper widgets


class KeyTrigger:
    def __init__(self, trigger: Event, handler: SingleHandler, content):
        self.trigger = trigger
        self.handler = handler
        self.content = content

    run = Run()

    def dispatch(self, event: Event):
        if event == self.trigger:
            self.handler()
        else:
            return self.content.dispatch(event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        return self.content


class SequenceTrigger:
    def __init__(self, trigger: list[Event], handler: SingleHandler, content):
        self.trigger = trigger
        self.events = [None] * len(trigger)
        self.handler = handler
        self.content = content

    run = Run()

    @property
    def result(self):
        return self.content.result

    def dispatch(self, event):
        self.events = self.events[1:] + [event]
        if self.events == self.trigger:
            return self.handler()
        else:
            return self.content.dispatch(event)


class Crashable(SequenceTrigger):
    def __init__(self, trigger: list[Event], content):
        super().__init__(trigger, lambda: sys.exit(), content)


class Closeable(KeyTrigger):
    def __init__(self, trigger: Event, content):
        super().__init__(trigger, self.run.stop, content)


class Framed:
    run = Run()

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
        t.add_row(f"[bold cyan]{self.label}[/]", self.content)
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
    dispatch = Dispatch()

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
    def __init__(self, content, focus_style: Style = Style.parse("bold yellow")):
        self.content = content
        self.focus_style = focus_style

    run = Run()
    dispatch = Dispatch()

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
    run = Run()

    def __init__(self, content):
        self.content = content
        self.focus = False

    dispatch = Dispatch()

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
