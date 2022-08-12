from rich.panel import Panel

from . import terminal


class Echo:
    def __init__(self):
        self.keys = []

    def dispatch(self, key):
        match key:
            case "ctrl+d":
                self.keys = []
            case "space":
                self.keys.append(" ")
            case "enter":
                self.keys.append("\n")
            case "backspace":
                self.keys = self.keys[:-1]
            case _:
                self.keys.append(key)


class EchoBytes(Echo):
    def __rich__(self):
        return Panel("[cyan]" + " ".join(map(str, self.keys)) + "[/]")

    def run(self):
        terminal.display(
            self,
            self.dispatch,
            reader=terminal.bytesiter,
            escape=terminal.escape_sequence([b"\x1b", b"\x1b", b"\x1b"]),
        )


class EchoStr(Echo):
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

    def run(self):
        terminal.display(self, self.dispatch, reader=terminal.striter)


def echostr() -> None:
    EchoStr().run()


def echobytes() -> None:
    EchoBytes().run()
