import typing
from math import ceil, floor

from rich.console import Group
from rich.markup import escape
from rich.panel import Panel

from twidge.core import Dispatcher, Runner
from twidge.widgets.base import Wrapper, Close


class StringView:
    dispatch = Dispatcher().autofocus()

    def __init__(
        self,
        text: str = "",
        multiline: bool = True,
        overflow: typing.Literal["wrap", "scroll"] = "scroll",
    ):
        self.lines = list(text.split("\n"))
        self.cursor = [0, 0]
        self.focus = True
        self.multiline = multiline
        self.overflow = overflow

    def result(self) -> str:
        return "\n".join(self.lines)

    def __rich__(self):
        return self

    def __rich_console__(self, console, options):
        width, height = options.max_width, options.max_height - 2
        slines, cline, elines = _scrollview(self.lines, self.cursor[0], height)

        match self.overflow:
            case "scroll":
                if not 0 <= self.cursor[1] < len(cline):
                    sstr, cstr, estr = (
                        cline[max(0, self.cursor[1] - (width - 1)) : self.cursor[1]],
                        " ",
                        "",
                    )
                else:
                    sstr, cstr, estr = _scrollview(cline, self.cursor[1], width)
            case "wrap":
                if not 0 <= self.cursor[1] < len(cline):
                    sstr, cstr, estr = cline, " ", ""
                else:
                    sstr, cstr, estr = _fullview(cline, self.cursor[1], width)

        # Render lines before cursor, if any
        yield from (escape(line[:width]) for line in slines)

        # Render cursor line
        yield (
            f"[bold yellow]{escape(sstr)}[on cyan]{cstr}[/]{escape(estr)}[/]"
            if self.focus
            else f"{escape(sstr)}{escape(cstr)}{escape(estr)}"
        )

        # Render lines after cursor, if any
        yield from (escape(line[:width]) for line in elines)

    @dispatch.on("left")
    def cursor_left(self):
        if self.cursor[1] != 0:
            self.cursor[1] -= 1
        else:
            if self.cursor[0] != 0:
                self.cursor[0] -= 1
                self.cursor[1] = len(self.lines[self.cursor[0]])

    @dispatch.on("right")
    def cursor_right(self):
        if self.cursor[1] < len(self.lines[self.cursor[0]]):
            self.cursor[1] += 1
        else:
            if self.cursor[0] < len(self.lines) - 1:
                self.cursor[0] += 1
                self.cursor[1] = 0

    @dispatch.on("ctrl+right")
    def next_word(self):
        line = self.lines[self.cursor[0]]
        next_space = line[self.cursor[1] :].find(" ")
        if next_space == -1:
            self.cursor[1] = len(line)
        else:
            self.cursor[1] = self.cursor[1] + next_space + 1

    @dispatch.on("ctrl+left")
    def prev_word(self):
        line = self.lines[self.cursor[0]]
        prev_space = line[max(0, self.cursor[1] - 2) :: -1].find(" ")
        if prev_space < 0:
            self.cursor[1] = 0
        else:
            self.cursor[1] = self.cursor[1] - prev_space - 1

    @dispatch.on("home")
    def cursor_home(self):
        self.cursor[1] = 0

    @dispatch.on("end")
    def cursor_end(self):
        self.cursor[1] = len(self.lines[self.cursor[0]])

    @dispatch.on("up")
    def cursor_up(self):
        if self.multiline and self.cursor[0] > 0:
            self.cursor[0] -= 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    @dispatch.on("down")
    def cursor_down(self):
        if self.multiline and self.cursor[0] < len(self.lines) - 1:
            self.cursor[0] += 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    @dispatch.default
    def dropkeys(self, _):
        ...


def _fullview(content, center, width):
    """Pass through a full view of the content without truncation. Wraps lines."""
    return content[:center], content[center], content[center + 1 :]


def _scrollview(content, center, width):
    """Split a sequence content about the pivot index into
    start, center, end with fixed total width. Pivot must be < len(content).
    """
    width = width - 1
    # len of portion
    lstart = len(content[:center])
    lend = len(content[center + 1 :])

    # offset from center, floor/ceil accounts for odd widths
    ostart = ceil(width / 2) + max(0, floor(width / 2) - lend)
    oend = floor(width / 2) + max(0, ceil(width / 2) - lstart)

    # bounding index in seq
    istart = max(0, center - ostart)
    iend = min(center + 1 + oend, len(content))

    # partition content
    start = content[istart:center]
    end = content[center + 1 : iend]
    center = content[center]
    return start, center, end


class EditString(StringView):
    dispatch = Dispatcher().autofocus()

    @dispatch.on("backspace")
    def backspace(self):
        if self.cursor[1] != 0:
            self.lines[self.cursor[0]] = (
                self.lines[self.cursor[0]][: self.cursor[1] - 1]
                + self.lines[self.cursor[0]][self.cursor[1] :]
            )
            self.cursor[1] -= 1
        else:
            if self.multiline and self.cursor[0] != 0:
                length = len(self.lines[self.cursor[0] - 1])
                self.lines[self.cursor[0] - 1] = (
                    self.lines[self.cursor[0] - 1] + self.lines[self.cursor[0]]
                )
                self.cursor[1] = length
                del self.lines[self.cursor[0]]
                self.cursor[0] -= 1

    @dispatch.on("ctrl+h")
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

    @dispatch.on("enter")
    def newline(self):
        if self.multiline:
            rest = self.lines[self.cursor[0]][self.cursor[1] :]
            self.lines[self.cursor[0]] = self.lines[self.cursor[0]][: self.cursor[1]]
            self.lines.insert(self.cursor[0] + 1, rest)
            self.cursor[0] += 1
            self.cursor[1] = 0

    @dispatch.default
    def insert(self, char: str):
        char = "\t" if char == "tab" else char
        char = " " if char == "space" else char

        if len(char) > 1:
            return
        line = self.lines[self.cursor[0]]
        if line == "":
            line = char
        else:
            line = line[: self.cursor[1]] + char + line[self.cursor[1] :]
        self.cursor[1] += len(char)
        self.lines[self.cursor[0]] = line


class WatchCursor(Wrapper):
    """Display cursor position with an editor."""

    def __rich__(self):
        return Group(Panel.fit(f"Cursor: {self.content.cursor}"), self.content)
