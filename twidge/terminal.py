import string
import sys
import termios
from contextlib import contextmanager

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
        fd = stdin if stdin is not None else sys.stdin.fileno()
        old = termios.tcgetattr(fd)
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
        termios.tcsetattr(fd, termios.TCSAFLUSH, mode)
        # End of modified tty.setraw

        # Non-blocking io; disabled b/c tricky.
        # os.set_blocking(fd, False)
        yield
    finally:

        # Resume blocking io, see above.
        # os.set_blocking(fd, True)
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
