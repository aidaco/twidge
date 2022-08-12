import functools

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from . import terminal


class Editor:
    def __init__(self, text="", show_cursor=True):
        self.lines = list(text.split("\n"))
        self.cursor = [0, 0]
        self.show_cursor = show_cursor

    def result(self) -> str:
        return "\n".join(self.lines)

    def __rich__(self):
        if not self.show_cursor:
            nl = "\n"
            return f"[bold cyan]{nl.join(self.lines)}[/]"
        text = "[bold cyan]"

        # Render lines before cursor, if any
        if self.cursor[0] != 0:
            text += escape("\n".join(self.lines[: self.cursor[0]]) + "\n")

        # Render cursor line
        line = self.lines[self.cursor[0]]
        if self.cursor[1] >= len(line):
            text += line + "[on cyan] [/]"
        else:
            text += (
                line[: self.cursor[1]]
                + "[on cyan]"
                + line[self.cursor[1]]
                + "[/]"
                + line[self.cursor[1] + 1 :]
            )

        # Render lines after cursor, if any
        if self.cursor[0] < len(self.lines) - 1:
            text += escape("\n" + "\n".join(self.lines[self.cursor[0] + 1 :]))

        return text + "[/]"

    def cursor_left(self):
        if self.cursor[1] != 0:
            self.cursor[1] -= 1
            if self.lines[self.cursor[0]][self.cursor[1]] == "\n":
                self.cursor[1] -= 1
        else:
            if self.cursor[0] != 0:
                self.cursor[0] = self.cursor[0] - 1
                self.cursor[1] = len(self.lines[self.cursor[0]]) - 1

    def cursor_right(self):
        if self.cursor[1] < len(self.lines[self.cursor[0]]) - 1:
            self.cursor[1] += 1
        else:
            if self.cursor[0] < len(self.lines) - 1:
                self.cursor[0] += 1
                self.cursor[1] = 0

    def cursor_up(self):
        if self.cursor[0] > 0:
            self.cursor[0] -= 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    def cursor_down(self):
        if self.cursor[0] < len(self.lines) - 1:
            self.cursor[0] += 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    def next_word(self):
        line = self.lines[self.cursor[0]]
        next_space = line[self.cursor[1] :].find(" ")
        if next_space == -1:
            self.cursor[1] = len(line)
        else:
            self.cursor[1] = self.cursor[1] + next_space + 1

    def prev_word(self):
        line = self.lines[self.cursor[0]]
        prev_space = line[: self.cursor[1] - 1][::-1].find(" ")
        if prev_space < 0:
            self.cursor[1] = 0
        else:
            self.cursor[1] = self.cursor[1] - prev_space - 1

    def delete_word(self):
        prev_space = self.lines[self.cursor[0]][: self.cursor[1] - 1][::-1].find(" ")
        if prev_space == -1:
            n = 0
        else:
            n = self.cursor[1] - prev_space - 2
        self.lines[self.cursor[0]] = (
            self.lines[self.cursor[0]][:n]
            + self.lines[self.cursor[0]][self.cursor[1] :]
        )
        self.cursor[1] = n

    def insert(self, char: str):
        if len(char) > 1:
            return
        if char == "\n":
            rest = self.lines[self.cursor[0]][self.cursor[1] :]
            self.lines[self.cursor[0]] = self.lines[self.cursor[0]][: self.cursor[1]]
            self.lines.insert(self.cursor[0] + 1, rest)
            self.cursor[0] += 1
            self.cursor[1] = 0
            return
        line = self.lines[self.cursor[0]]
        if line == "":
            line = char
        else:
            line = line[: self.cursor[1]] + char + line[self.cursor[1] :]
        self.cursor[1] += len(char)
        self.lines[self.cursor[0]] = line

    def backspace(self):
        if self.cursor[1] != 0:
            self.lines[self.cursor[0]] = (
                self.lines[self.cursor[0]][: self.cursor[1] - 1]
                + self.lines[self.cursor[0]][self.cursor[1] :]
            )
            self.cursor[1] -= 1
        else:
            if self.cursor[0] != 0:
                length = len(self.lines[self.cursor[0] - 1])
                self.lines[self.cursor[0] - 1] = (
                    self.lines[self.cursor[0] - 1] + self.lines[self.cursor[0]]
                )
                self.cursor[1] = length
                del self.lines[self.cursor[0]]
                self.cursor[0] -= 1

    @functools.cached_property
    def __dict_dispatch__(self):
        return {
            "space": lambda: self.insert(" "),
            "enter": lambda: self.insert("\n"),
            "backspace": self.backspace,
            "tab": lambda: self.insert("\t"),
            "left": self.cursor_left,
            "right": self.cursor_right,
            "down": self.cursor_down,
            "up": self.cursor_up,
            "ctrl+h": self.delete_word,
            "ctrl+left": self.prev_word,
            "ctrl+right": self.next_word,
            "default": self.insert,
        }

    def run(self):
        terminal.display(
            self,
            terminal.dict_dispatcher(self),
            escape=terminal.escape_sequence(["ctrl+x"]),
        )


class DictEditor:
    def __init__(self, content: dict[str, str] | list[str], display=lambda x: x):
        self.display = display
        if isinstance(content, list):
            self.editors = {k: Editor(show_cursor=False) for k in content}
        else:
            self.editors = {k: Editor(v, show_cursor=False) for k, v in content.items()}

    def result(self):
        return {key: editor.result() for key, editor in self.editors.items()}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for k, e in self.editors.items():
            t.add_row(f"[bold yellow]{self.display(k)}[/]", e)
        return Panel(t, border_style="magenta")

    def run(self):
        terminal.display(
            self,
            terminal.focus_dispatcher(list(self.editors.values())),
            escape=terminal.escape_sequence(["ctrl+x"]),
        )


def editstr(content: str) -> str:
    e = Editor(content)
    e.run()
    return e.result()


def editdict(content: dict[str, str] | list[str]) -> dict:
    e = DictEditor(content)
    e.run()
    return e.result()
