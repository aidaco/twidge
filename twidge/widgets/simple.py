import typing
from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.style import Style
from rich.text import Text

from twidge.core import BytesReader, DispatchBuilder, Event, RunBuilder


class Echo:
    """Echo the str representation of each keypress to the screen."""

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
    """Echo the bytes representation of each keypress to the screen."""

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


class Cycler:
    dispatch = DispatchBuilder()
    run = RunBuilder()

    def __init__(
        self,
        *options: str,
        key=str,
        focus_style: str | Style = Style.parse("bright_yellow on magenta"),
        blur_style: str | Style = Style.parse("white on black"),
    ):
        self.options = options
        self.key = key
        self.len = len(self.options)
        self.index = 0
        self.focus = True
        self.focus_style = focus_style
        self.blur_style = blur_style

    @property
    def result(self):
        return self.options[self.index]

    @dispatch.on("space", "right")
    def forward(self):
        self.index = (self.index + 1) % self.len

    @dispatch.on("left")
    def back(self):
        self.index = (self.index - 1) % self.len

    @dispatch.default
    def drop_events(self, event: Event):
        pass

    def __rich__(self):
        def create(i, o):
            return Text(self.key(o), style=self.focus_style if self.focus else self.blur_style) if i == 0 else Text(self.key(o))
        return Group(
            *(
                create(i, o)
                for i, o in enumerate(
                    self.options[self.index :] + self.options[: self.index]
                )
            )
        )


__all__ = ["Button", "Cycler", "Echo", "EchoBytes", "Toggle"]
