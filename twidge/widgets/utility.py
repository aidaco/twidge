import typing

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from twidge.core import display, trigger


class echo(display):
    def __init__(self):
        self.keys = []

    def __trigger__(self, key):
        self.keys.append(key)

    def __rich__(self):
        return Panel(
            "[cyan]"
            + " ".join(
                f"'{ch}'"
                for ch in map(
                    lambda s: s.encode("unicode_escape").decode(),
                    self.keys,
                )
            )
            + "[/]"
        )


class escape(display):
    def __init__(self, widget, key: str = "ctrl+c"):
        self.key = key
        self.widget = widget

    def __rich__(self):
        return self.widget

    def __trigger__(self, key):
        if key == self.key:
            raise display.ExitTUI("Shit")
        else:
            self.widget.__trigger__(key)


class button(trigger.auto, display):
    def __init__(self, content, target: typing.Callable):
        self.content = content
        self.target = target
        self.focus = True

    def __rich__(self):
        return Panel.fit(self.content, style="green" if self.focus else "")

    @trigger.on("focus")
    def onfocus(self):
        self.focus = True

    @trigger.on("blur")
    def onblur(self):
        self.focus = False

    @trigger.on("enter")
    def click(self):
        self.target()

    @trigger.default
    def drop(self, key):
        ...


class frame(display):
    def __init__(self, content):
        self.content = content

    def __rich__(self):
        return Panel.fit(self.content)

    def __trigger__(self, key):
        self.content.__trigger__(key)

    def result(self):
        return self.content.result()


class labelled(display):
    def __init__(self, label, widget):
        self.widget = widget
        self.label = label

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        t.add_row(f"[bold yellow]{self.label}[/]", self.widget)
        return t

    def __trigger__(self, key):
        self.widget.__trigger__(key)

    def result(self):
        return self.widget.result()


class focusgroup(trigger.auto, display):
    def __init__(self, *widgets):
        self.widgets = list(widgets)
        self.focus = 0
        getattr(self.widgets[0], "__trigger__", lambda e: None)("focus")
        for w in self.widgets[1:]:
            getattr(w, "__trigger__", lambda e: None)("blur")

    def __rich__(self):
        return Group(*self.widgets)

    @trigger.on("tab")
    def focus_next(self):
        getattr(self.widgets[self.focus], "__trigger__", lambda e: None)("blur")
        if self.focus == len(self.widgets) - 1:
            self.focus = 0
        else:
            self.focus += 1
        getattr(self.widgets[self.focus], "__trigger__", lambda e: None)("focus")

    @trigger.on("shift+tab")
    def focus_previous(self):
        getattr(self.widgets[self.focus], "__trigger__", lambda e: None)("blur")
        if self.focus == 0:
            self.focus = len(self.widgets) - 1
        else:
            self.focus -= 1
        getattr(self.widgets[self.focus], "__trigger__", lambda e: None)("focus")

    @trigger.default
    def dispatch(self, key):
        self.widgets[self.focus].__trigger__(key)

    def result(self):
        return [w.result() for w in self.widgets]
