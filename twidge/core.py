from contextlib import contextmanager
import string
import os
import sys
import termios
from inspect import signature
from dataclasses import dataclass, field
from typing import Callable, Protocol, Any, BinaryIO, TypeAlias, runtime_checkable

from rich.console import Console, RenderableType
from rich.live import Live

SPECIALMAP = {
    b" ": "space",
    b"\t": "tab",
    b"\r": "enter",
    b"\x1b": "escape",
    b"\x7f": "backspace",
    b"\x1b[3~": "delete",
    b"\x1b[A": "up",
    b"\x1b[B": "down",
    b"\x1b[D": "left",
    b"\x1b[C": "right",
    b"\x1b[H": "home",
    b"\x1b[F": "end",
    b"\x1b[Z": "shift+tab",
    b"\x1b[2~": "insert",
    b"\x1b[6~": "pagedown",
    b"\x1b[5~": "pageup",
}


FUNCTIONMAP = {
    b"\x1bOP": "f1",
    b"\x1bOQ": "f2",
    b"\x1bOR": "f3",
    b"\x1bOS": "f4",
    b"\x1b[15~": "f5",
    b"\x1b[17~": "f6",
    b"\x1b[18~": "f7",
    b"\x1b[19~": "f8",
    b"\x1b[20~": "f9",
    b"\x1b[21~": "f10",
    b"\x1b[24~": "f12",
}


CTRLMAP = {
    b"\x01": "ctrl+a",
    b"\x02": "ctrl+b",
    b"\x03": "ctrl+c",
    b"\x04": "ctrl+d",
    b"\x05": "ctrl+e",
    b"\x06": "ctrl+f",
    b"\x07": "ctrl+g",
    b"\x08": "ctrl+h",
    b"\x09": "ctrl+i",  # == \t == tab
    b"\x0a": "ctrl+j",  # == \n == newline
    b"\x0b": "ctrl+k",
    b"\x0c": "ctrl+l",
    b"\x0d": "ctrl+m",  # == \r == enter
    b"\x0e": "ctrl+n",
    b"\x0f": "ctrl+o",
    b"\x10": "ctrl+p",
    b"\x11": "ctrl+q",
    b"\x12": "ctrl+r",
    b"\x13": "ctrl+s",
    b"\x14": "ctrl+t",
    b"\x15": "ctrl+u",
    b"\x16": "ctrl+v",
    b"\x17": "ctrl+w",
    b"\x18": "ctrl+x",
    b"\x19": "ctrl+y",
    b"\x1a": "ctrl+z",
    b"\x1b[1;5A": "ctrl+up",
    b"\x1b[1;5B": "ctrl+down",
    b"\x1b[1;5C": "ctrl+right",
    b"\x1b[1;5D": "ctrl+left",
}

ALTMAP = {b"\x1b" + ch.encode(): f"alt+{ch}" for ch in string.ascii_lowercase}
KEYMAP = CTRLMAP | ALTMAP | FUNCTIONMAP | SPECIALMAP


def keystr(ch: bytes) -> str:
    return KEYMAP.get(ch, ch.decode())


@contextmanager
def chbreak(
    stdin: int | None = None,
):
    """Configures stdin for reading in character break mode;
    IO sold separate. Unix specific."""

    try:
        stdin = stdin or sys.stdin.fileno()
        old = termios.tcgetattr(stdin)
        mode = old.copy()

        # This section is a modified version of tty.setraw
        # Removing OPOST fixes issues with carriage returns.
        # Needs further investigation.
        mode[0] &= ~(
            termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON
        )
        mode[2] &= ~(termios.CSIZE | termios.PARENB)
        mode[2] |= termios.CS8
        mode[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        mode[6][termios.VMIN] = 1
        mode[6][termios.VTIME] = 0
        termios.tcsetattr(stdin, termios.TCSAFLUSH, mode)
        # End of modified tty.setraw

        # Non-blocking io; disabled b/c tricky.
        # os.set_blocking(stdin, False)
        yield
    finally:

        # Resume blocking io, see above.
        # os.set_blocking(stdin, True)
        termios.tcsetattr(stdin, termios.TCSADRAIN, old)


class EventBase:
    ...


class ResponseBase:
    ...


Event: TypeAlias = EventBase | str | bytes
Response: TypeAlias = ResponseBase | str | bytes | None
SingleHandler: TypeAlias = Callable[[], Response | None]
MultiHandler: TypeAlias = Callable[[Event], Response | None]
Handler: TypeAlias = SingleHandler | MultiHandler


class Reader(Protocol):
    def __init__(self, io: BinaryIO):
        ...

    def read(self) -> Event:
        ...


class Dispatcher(Protocol):
    dispatch: MultiHandler


class Runner(Protocol):
    def __init__(self, widget, *args, **kwargs):
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


class BytesReader:
    def __init__(self, io: BinaryIO):
        self.io = io

    def read(self) -> bytes:
        return self.io.read(6)


class StrReader(BytesReader):
    def read(self) -> str:
        return keystr(super().read())


Widget: TypeAlias = Dispatcher | RenderableType  # no type intersection op


@dataclass
class WidgetRunner:
    widget: Widget
    reader: Reader = StrReader
    stdin: int | None = None
    console: Console | None = None
    stopped: bool = False

    def start(self):
        self.stdin = self.stdin or sys.stdin.fileno()
        self.console = self.console or Console()
        with Live(
            self.widget,
            console=self.console,
            transient=True,
            auto_refresh=False,
        ) as live:
            with chbreak(stdin=self.stdin):
                read = self.reader(open(self.stdin, "rb", buffering=0, closefd=False)).read
                self.stopped = False
                while not self.stopped:
                    self.widget.dispatch(read())
                    live.refresh()

    def stop(self):
        self.stopped = True

    __call__ = start


@dataclass
class WidgetDispatcher:
    widget: Widget
    table: dict[Event, Handler] = field(default_factory=dict)
    default: Handler | None = None

    def dispatch(self, event: Event) -> Response:
        fn = self.table.get(event, self.default)
        if fn is None:
            raise ValueError(f"No handler for {event}")
        match len(signature(fn).parameters):
            case 0:
                return fn()
            case 1:
                return fn(event)
            case _:
                raise TypeError(f"Handler should take one or zero arguments.")

    __call__ = dispatch

    def update(self, table: dict[Event, Handler], default: Handler | None = None):
        self.table.update(table)
        if default is not None:
            self._default = default
        return self


class RunBuilder:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __get__(self, obj, obj_type=None):
        obj.run = WidgetRunner(obj, *self.args, **self.kwargs)
        return obj.run


@dataclass
class DispatchBuilder:
    handler_methods: dict[Event, str] = field(default_factory=dict)
    table: dict[Event, Handler] = field(default_factory=dict)
    defaultfn: Handler | None = None

    def on(self, *events: Event) -> Callable[[Handler], Handler]:
        def decorate(fn: Handler) -> Handler:
            for e in events:
                self.handler_methods[e] = fn.__name__
            return fn

        return decorate

    def default(self, fn: Handler) -> Handler:
        self.defaultfn = fn.__name__
        return fn

    def __get__(self, obj, obj_type=None):
        if obj is None:
            return self
        table = self.table | {e: getattr(obj, m) for e, m in self.handler_methods.items()}
        default = (
            getattr(obj, self.defaultfn) if isinstance(self.defaultfn, str) else self.defaultfn
        )
        obj.dispatch = WidgetDispatcher(obj, table=table, default=default)
        return obj.dispatch
