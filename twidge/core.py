import contextlib
import functools
import os
import sys
import termios
import typing

from rich.console import Console
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


ALTMAP = {
    b"\x1ba": "alt+a",
    b"\x1bb": "alt+b",
    b"\x1bc": "alt+c",
    b"\x1bd": "alt+d",
    b"\x1be": "alt+e",
    b"\x1bf": "alt+f",
    b"\x1bg": "alt+g",
    b"\x1bh": "alt+h",
    b"\x1bi": "alt+i",
    b"\x1bj": "alt+j",
    b"\x1bk": "alt+k",
    b"\x1bl": "alt+l",
    b"\x1bm": "alt+m",
    b"\x1bn": "alt+n",
    b"\x1bo": "alt+o",
    b"\x1bp": "alt+p",
    b"\x1bq": "alt+q",
    b"\x1br": "alt+r",
    b"\x1bs": "alt+s",
    b"\x1bt": "alt+t",
    b"\x1bu": "alt+u",
    b"\x1bv": "alt+v",
    b"\x1bw": "alt+w",
    b"\x1bx": "alt+x",
    b"\x1by": "alt+y",
    b"\x1bz": "alt+z",
}


KEYMAP = CTRLMAP | ALTMAP | FUNCTIONMAP | SPECIALMAP


def keystr(ch: bytes) -> str:
    return KEYMAP.get(ch, ch.decode())


def chreader(stdin: int = sys.stdin.fileno()) -> typing.Callable[[], bytes | None]:
    io = open(stdin, "rb", buffering=0, closefd=False)

    def read() -> bytes | None:
        return io.read(6)

    return read


@contextlib.contextmanager
def chbreak(
    stdin: int = sys.stdin.fileno(),
    block: bool = True,
    reader: typing.Callable[[int], typing.Callable[[], bytes | None]] = chreader,
):
    """Opens stdin for reading in character break mode; on entrance, returns a read function. Unix only."""

    try:
        old = termios.tcgetattr(stdin)
        mode = old.copy()

        # This section is a modified version of tty.setraw
        # Removing OPOST fixes issues with carriage returns.
        # Needs further investigation.
        mode[0] &= ~(
            termios.BRKINT
            | termios.ICRNL
            | termios.INPCK
            | termios.ISTRIP
            | termios.IXON
        )
        mode[2] &= ~(termios.CSIZE | termios.PARENB)
        mode[2] |= termios.CS8
        mode[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        mode[6][termios.VMIN] = 1
        mode[6][termios.VTIME] = 0
        termios.tcsetattr(stdin, termios.TCSAFLUSH, mode)
        # End of modified tty.setraw

        os.set_blocking(stdin, block)
        yield reader(stdin)

    finally:
        os.set_blocking(stdin, not block)
        termios.tcsetattr(stdin, termios.TCSADRAIN, old)


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
