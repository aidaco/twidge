from math import ceil, floor

from rich.console import Group
from rich.markup import escape
from rich.panel import Panel

from twidge.widgets import TUI, AutoFocus, default, on


class EditLine(TUI, AutoFocus):
    def __init__(self, text: str = ""):
        self.line = text.replace("\n", "")
        self.cursor = 0
        self.focus = True

    def __rich__(self):
        return self

    def result(self):
        return self.line

    def __rich_console__(self, console, options):
        width = options.max_width
        if self.cursor == len(self.line):
            start, cursor, end = (
                self.line[max(0, self.cursor - (width - 1)) : self.cursor],
                " ",
                "",
            )
        else:
            start, cursor, end = _fixed_width_partition(self.line, self.cursor, width)
        yield (
            f"[bold cyan]{start}[on cyan]{cursor}[/]{end}[/]"
            if self.focus
            else f"{start}{cursor}{end}"
        )

    @on("left")
    def cursor_left(self):
        self.cursor = max(0, self.cursor - 1)

    @on("right")
    def cursor_right(self):
        self.cursor = min(len(self.line), self.cursor + 1)

    @on("ctrl+right")
    def next_word(self):
        next_space = self.line[self.cursor :].find(" ")
        if next_space == -1:
            self.cursor = len(self.line)
        else:
            self.cursor = self.cursor + next_space + 1

    @on("ctrl+left")
    def prev_word(self):
        prev_space = self.line[max(0, self.cursor - 2) :: -1].find(" ")
        if prev_space < 0:
            self.cursor = 0
        else:
            self.cursor = self.cursor - prev_space - 1

    @on("home")
    def cursor_home(self):
        self.cursor = 0

    @on("end")
    def cursor_end(self):
        self.cursor = len(self.line)

    @on("ctrl+h")
    def delete_word(self):
        prev_space = self.line[self.cursor - 1 :: -1].find(" ")
        if prev_space == -1:
            n = 0
        else:
            n = self.cursor - prev_space - 1
        self.line = self.line[:n] + self.line[self.cursor :]
        self.cursor = n

    @default
    def insert(self, char: str):
        if len(char) > 1 or char == "\n":
            return
        self.line = self.line[: self.cursor] + char + self.line[self.cursor :]
        self.cursor += 1

    @on("backspace")
    def backspace(self):
        if self.cursor == 0:
            return
        self.line = self.line[: self.cursor - 1] + self.line[self.cursor :]
        self.cursor -= 1

    @on("space")
    def space(self):
        self.insert(" ")

    @on("tab")
    def tab(self):
        self.insert("\t")


class EditMultiline(TUI, AutoFocus):
    def __init__(self, text: str = ""):
        self.lines = list(text.split("\n"))
        self.cursor = [0, 0]
        self.focus = True

    def result(self) -> str:
        return "\n".join(self.lines)

    def __rich__(self):
        return self

    def __rich_console__(self, console, options):
        width, height = options.max_width, options.max_height - 2
        slines, cline, elines = _fixed_width_partition(
            self.lines, self.cursor[0], height
        )

        if not 0 <= self.cursor[1] < len(cline):
            sstr, cstr, estr = (
                cline[max(0, self.cursor[1] - (width - 1)) : self.cursor[1]],
                " ",
                "",
            )
        else:
            sstr, cstr, estr = _fixed_width_partition(cline, self.cursor[1], width)

        # Render lines before cursor, if any
        yield from (escape(line[:width]) for line in slines)

        # Render cursor line
        yield (
            f"[bold yellow]{escape(sstr)}[on cyan]{cstr}[/]{escape(estr)}[/]"
            if self.focus
            else f"{escape(sstr)}[on white]{escape(cstr)}[/]{escape(estr)}"
        )

        # Render lines after cursor, if any
        yield from (escape(line[:width]) for line in elines)

    @on("left")
    def cursor_left(self):
        if self.cursor[1] != 0:
            self.cursor[1] -= 1
        else:
            if self.cursor[0] != 0:
                self.cursor[0] -= 1
                self.cursor[1] = len(self.lines[self.cursor[0]])

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
        prev_space = line[max(0, self.cursor[1] - 2) :: -1].find(" ")
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
            self.lines[self.cursor[0]][:n]
            + self.lines[self.cursor[0]][self.cursor[1] :]
        )
        self.cursor[1] = n

    @default
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


def _fixed_width_partition(content, pivot, width):
    """Split a sequence content about the pivot index into
    start, center, end with fixed total width. Pivot must be < len(content).
    """
    width = width - 1
    # len of portion
    lstart = len(content[:pivot])
    lend = len(content[pivot + 1 :])

    # offset from pivot, floor/ceil accounts for odd widths
    ostart = ceil(width / 2) + max(0, floor(width / 2) - lend)
    oend = floor(width / 2) + max(0, ceil(width / 2) - lstart)

    # bounding index in seq
    istart = max(0, pivot - ostart)
    iend = min(pivot + 1 + oend, len(content))

    # partition content
    start = content[istart:pivot]
    center = content[pivot]
    end = content[pivot + 1 : iend]
    return start, center, end


class WatchCursor(TUI):
    """Display cursor position with an editor."""

    def __init__(self, editor):
        self.editor = editor

    def __rich__(self):
        return Group(Panel.fit(f"Cursor: {self.editor.cursor}"), self.editor)

    def dispatch(self, key):
        if hasattr(self.editor, "dispatch"):
            self.editor.dispatch(key)

    def result(self):
        return self.editor.result()
