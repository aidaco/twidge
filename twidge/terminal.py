import os
import sys
import termios
import time
import typing

from rich.console import Console
from rich.live import Live

from . import keymap


class Reader(typing.Protocol):
    def __call__(self, io: typing.BinaryIO) -> typing.Any:
        ...


def bytereader(io: typing.BinaryIO) -> typing.Callable[[], bytes | None]:
    """Returns byte representation of the keypress or None if not ready."""

    def inner() -> bytes | None:
        return io.read(6)

    return inner


def strreader(io: typing.BinaryIO) -> typing.Callable[[], str | None]:
    """Returns str representation of the keypress or None if not ready."""
    read = bytereader(io)

    def inner() -> str | None:
        ch = read()
        return ch if ch is None else keymap.to_str(ch)

    return inner


def bytegetter(io: typing.BinaryIO) -> typing.Callable[[], bytes]:
    """Wait for the next keypress."""
    read = bytereader(io)

    def inner() -> bytes:
        while not (ch := read()):
            time.sleep(0.0001)
        return ch

    return inner


def strgetter(io: typing.BinaryIO) -> typing.Callable[[], str]:
    """Wait for the next keypress, represented as str."""
    get = bytegetter(io)

    def inner() -> str:
        return keymap.to_str(get())

    return inner


def bytesiter(io: typing.BinaryIO) -> typing.Iterator[bytes | None]:
    read = bytereader(io)
    while True:
        yield read()


def striter(io: typing.BinaryIO) -> typing.Iterator[str | None]:
    read = strreader(io)
    while True:
        yield read()


class raw:
    """Context manager for putting the terminal into raw mode.

    On entrance, returns itself."""

    def __init__(self, reader: Reader, stdin: int = sys.stdin.fileno()):
        self.reader = reader
        self.stdin = stdin

    def begin(self):
        self.io = open(self.stdin, "rb", closefd=False)
        self.old = termios.tcgetattr(self.io)

        # This section is a modified version of tty.setraw
        # Removing OPOST fixes issues with carriage returns.
        # Needs further investigation.
        mode = self.old.copy()
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
        termios.tcsetattr(self.stdin, termios.TCSAFLUSH, mode)
        # End of modified tty.setraw

        os.set_blocking(self.stdin, False)

    def end(self):
        os.set_blocking(self.stdin, True)
        termios.tcsetattr(self.stdin, termios.TCSADRAIN, self.old)

    def __enter__(self):
        self.begin()
        return self.reader(self.io)

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.end()


def escape_sequence(sequence: list = ["escape", "escape", "escape"]):
    history = []

    def does_escape(value) -> bool:
        nonlocal history
        history.append(value)
        history = history[-len(sequence) :]
        if history == sequence:
            return True
        return False

    return does_escape


def dict_dispatcher(target) -> typing.Callable[[str], None]:
    fnmap = target.__dict_dispatch__

    def inner(key: str) -> None:
        if (f := fnmap.get(key, None)) is not None:
            f()
        else:
            fnmap["default"](key)

    return inner


def focus_dispatcher(targets: list) -> typing.Callable[[str], None]:
    focus: int = 0
    dds = [dict_dispatcher(t) for t in targets]
    targets[focus].show_cursor = True

    def inner(key: str) -> None:
        nonlocal focus
        match key:
            case "tab":
                targets[focus].show_cursor = False
                focus = (focus + 1) % len(targets)
                targets[focus].show_cursor = True
            case "shift+tab":
                targets[focus].show_cursor = False
                focus = (focus - 1) % len(targets)
                targets[focus].show_cursor = True
            case _:
                dds[focus](key)

    return inner


def display(
    content,
    dispatch: typing.Callable[[str], None],
    reader: Reader = striter,
    escape: typing.Callable[[str], bool] = escape_sequence(["ctrl+x"]),
    console: Console = Console(),
    stdin: int = sys.stdin.fileno(),
):

    with Live(content, console=console, transient=True, auto_refresh=False) as live:
        with raw(reader, stdin=stdin) as keys:
            for k in keys:
                if k is not None:
                    if escape(k):
                        break
                    else:
                        dispatch(k)
                try:
                    live.refresh()
                except BlockingIOError:
                    pass
                time.sleep(0)
