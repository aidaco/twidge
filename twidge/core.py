import functools
import os
import sys
import termios
import typing

from rich.console import Console
from rich.live import Live

from . import keymap


class chbreak:
    """Opens stdin for reading in character break mode. Unix only.

    Returns a reader object with readstr and readbyte methods."""

    def __init__(
        self,
        stdin: int = sys.stdin.fileno(),
        block: bool = True,
    ):
        self.stdin = stdin
        self.block = block

    class reader:
        def __init__(self, io: typing.BinaryIO):
            self.io = io

        def readbyte(self) -> bytes | None:
            return self.io.read(6)

        def readstr(self) -> typing.Callable[[], str | None]:
            return ch if (ch := self.readbyte()) is None else keymap.to_str(ch)

    def __enter__(self):
        self.old = termios.tcgetattr(self.stdin)
        mode = self.old.copy()

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
        termios.tcsetattr(self.stdin, termios.TCSAFLUSH, mode)
        # End of modified tty.setraw

        if not self.block:
            os.set_blocking(self.stdin, False)

        return self.reader(open(self.stdin, "rb", buffering=0, closefd=False))

    def __exit__(self, exc_type, exc_value, exc_tb):
        if not self.block:
            os.set_blocking(self.stdin, True)
        termios.tcsetattr(self.stdin, termios.TCSADRAIN, self.old)


class trigger:
    @staticmethod
    def on(*events):
        def decorate(fn: typing.Callable) -> typing.Callable:
            fn.__trigger_on__ = getattr(fn, "__trigger_on__", []) + list(events)
            return fn

        return decorate

    @classmethod
    def default(cls, fn: typing.Callable):
        fn.__trigger_on__ = getattr(fn, "__trigger_on__", []) + ["default"]
        return fn

    class auto:
        @functools.cached_property
        def __trigger_table__(self):
            return {
                tag: meth
                for attr in dir(self)
                if attr != "__trigger_table__"
                and callable((meth := getattr(self, attr)))
                and (tags := getattr(meth, "__trigger_on__", None)) is not None
                for tag in tags
            }

        def __trigger__(self, event):
            table = self.__trigger_table__

            def default():
                table.get("default")(event)

            table.get(event, default)()


class focusdispatcher(trigger.auto):
    """Dispatch events to sequence of widgets by active focus, cycles with 'tab' and 'shift+tab'."""

    def __init__(self, widgets: list | None = None, start: int = 0):
        self.focus: int = start
        self.targets = widgets if widgets is not None else []
        if widgets:
            self.targets[self.focus].show_cursor = True

    @trigger.on("tab")
    def forward(self, _=None):
        self.targets[self.focus].show_cursor = False
        self.focus = (self.focus + 1) % len(self.targets)
        self.targets[self.focus].show_cursor = True

    @trigger.on("shift+tab")
    def back(self, _=None):
        self.targets[self.focus].show_cursor = False
        self.focus = (self.focus - 1) % len(self.targets)
        self.targets[self.focus].show_cursor = True

    @trigger.default
    def bubble(self, key):
        if self.targets:
            self.targets[self.focus].__trigger__(key)


def _make_escape(sequence: list[str]) -> typing.Callable[[str], bool]:
    history = []

    def does_escape(value: str) -> bool:
        nonlocal history
        history.append(value)
        history = history[-len(sequence) :]
        if history == sequence:
            return True
        return False

    return does_escape


class display:
    """Terminal widget mix-in with `run` and `show`. Class must be a Rich Renderable and have a __trigger__ method."""

    def show(self, escape: list[str] = ["ctrl+x"], console: None | Console = None):
        escape = _make_escape(escape)
        console = console or Console()
        with Live(self, console=console, transient=True, auto_refresh=False) as live:
            with chbreak() as reader:
                while not escape((key := reader.readstr())):
                    self.__trigger__(key)
                    live.refresh()

    @classmethod
    def run(cls, *args, **kwargs):
        w = cls(*args, **kwargs)
        w.show()
        return w
