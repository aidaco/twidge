from rich.markup import escape
from rich.table import Table
from rich.console import Group
from rich.panel import Panel

from twidge.core import TUI, on, default, autodispatch

from .mixins import AutoFocus
from .utility import focusgroup


class editbool(AutoFocus, AutoDispatch, TUI):
    def __init__(self, value: bool):
        self.value = value
        self.focus = True

    def __rich__(self):
        if self.focus:
            return "[green]True[/]" if self.value else "[red]False[/]"
        else:
            return "True" if self.value else "False"

    @default
    def switch(self, key):
        self.value = not self.value

    def result(self):
        return self.value


class editstr(AutoDispatch, AutoFocus, TUI):
    def __init__(self, text="", show_cursor=True):
        self.lines = list(text.split("\n"))
        self.cursor = [0, 0]
        self.show_cursor = True
        self.focus = True

    def result(self) -> str:
        return "\n".join(self.lines)

    def __rich__(self):
        if not self.focus and not self.show_cursor:
            nl = "\n"
            return f"[bold cyan]{nl.join(self.lines)}[/]" if self.focus else nl.join(self.lines)
        text = "[bold cyan]" if self.focus else ""

        # Render lines before cursor, if any
        if self.cursor[0] != 0:
            text += escape("\n".join(self.lines[: self.cursor[0]]) + "\n")

        # Render cursor line
        line = self.lines[self.cursor[0]]
        if self.cursor[1] >= len(line):
            text += line + ("[on cyan] [/]" if self.focus else "")
        else:
            text += (
                line[: self.cursor[1]]
                + ("[on cyan]" if self.focus else "")
                + line[self.cursor[1]]
                + ("[/]" if self.focus else "")
                + line[self.cursor[1] + 1 :]
            )

        # Render lines after cursor, if any
        if self.cursor[0] < len(self.lines) - 1:
            text += escape("\n" + "\n".join(self.lines[self.cursor[0] + 1 :]))

        return text + ("[/]" if self.focus else "")


    @on("left")
    def cursor_left(self):
        if self.cursor[1] != 0:
            self.cursor[1] -= 1
            if self.lines[self.cursor[0]][self.cursor[1]] == "\n":
                self.cursor[1] -= 1
        else:
            if self.cursor[0] != 0:
                self.cursor[0] = self.cursor[0] - 1
                self.cursor[1] = len(self.lines[self.cursor[0]]) - 1

    @on("right")
    def cursor_right(self):
        if self.cursor[1] < len(self.lines[self.cursor[0]]):
            self.cursor[1] += 1
        else:
            if self.cursor[0] < len(self.lines) - 1:
                self.cursor[0] += 1
                self.cursor[1] = 0

    @on("up")
    def cursor_up(self):
        if self.cursor[0] > 0:
            self.cursor[0] -= 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    @on("down")
    def cursor_down(self):
        if self.cursor[0] < len(self.lines) - 1:
            self.cursor[0] += 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    @on("ctrl+right")
    def next_word(self):
        line = self.lines[self.cursor[0]]
        next_space = line[self.cursor[1] :].find(" ")
        if next_space == -1:
            self.cursor[1] = len(line)
        else:
            self.cursor[1] = self.cursor[1] + next_space + 1

    @on("ctrl+left")
    def prev_word(self):
        line = self.lines[self.cursor[0]]
        prev_space = line[: self.cursor[1] - 1][::-1].find(" ")
        if prev_space < 0:
            self.cursor[1] = 0
        else:
            self.cursor[1] = self.cursor[1] - prev_space - 1

    @on("home")
    def cursor_home(self):
        self.cursor[1] = 0

    @on("end")
    def cursor_end(self):
        self.cursor[1] = len(self.lines[self.cursor[0]])

    @on("ctrl+h")
    def delete_word(self):
        prev_space = self.lines[self.cursor[0]][: self.cursor[1] - 1][::-1].find(" ")
        if prev_space == -1:
            n = 0
        else:
            n = self.cursor[1] - prev_space - 2
        self.lines[self.cursor[0]] = (
            self.lines[self.cursor[0]][:n] + self.lines[self.cursor[0]][self.cursor[1] :]
        )
        self.cursor[1] = n

    @trigger.default
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

    @on("backspace")
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

    @on("space")
    def space(self):
        self.insert(" ")

    @on("enter")
    def enter(self):
        self.insert("\n")

    @on("tab")
    def tab(self):
        self.insert("\t")


class watchcursor(TUI):
    """Display cursor position with an editor."""

    def __init__(self, editor):
        self.editor = editor

    def __rich__(self):
        return Group(Panel.fit(f"Cursor: {self.editor.cursor}"), self.editor)

    def dispatch(self, key):
        self.editor.dispatch(key)


class editdict(TUI):
    def __init__(self, content: dict[str, str] | list[str], display=lambda x: x):
        self.display = display
        if isinstance(content, list):
            self.editors = {k: editstr(show_cursor=False) for k in content}
        else:
            self.editors = {k: editstr(v, show_cursor=False) for k, v in content.items()}
        self.fg = focusgroup(*list(self.editors.values()))

    def dispatch(self, key):
        self.fg.dispatch(key)

    def result(self):
        return {key: editor.result() for key, editor in self.editors.items()}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for k, e in self.editors.items():
            t.add_row(f"[bold yellow]{self.display(k)}[/]", e)
        return t
