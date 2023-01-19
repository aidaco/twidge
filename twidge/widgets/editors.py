import typing
from functools import partial
from math import ceil, floor

from rich.style import Style
from rich.styled import Styled
from rich.text import Text

from twidge.core import DispatchBuilder, RunBuilder


class EditString:
    run = RunBuilder()
    dispatch = DispatchBuilder()

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

    @property
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
        yield from (line[:width] for line in slines)

        # Render cursor line
        yield (
            Text(sstr) + Text(cstr, style="grey30 on grey70") + Text(estr)
            if self.focus
            else Text(sstr) + Text(cstr) + Text(estr)
        )

        # Render lines after cursor, if any
        yield from (line[:width] for line in elines)

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

    @dispatch.on("focus")
    def on_focus(self):
        self.focus = True

    @dispatch.on("blur")
    def on_blur(self):
        self.focus = False

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


class ValidatedEditString:
    def __init__(self, editor: EditString):
        self.editor = editor

    def __rich__(self):
        return (
            self.editor
            if self.validate(self.editor.text)
            else Styled(self.editor, style=Style(color="red"))
        )

    def dispatch(self, event):
        return self.editor.dispatch(event)

    @property
    def result(self):
        if self.validate(self.editor.result):
            return self.editor.result

    def validate(self, text) -> bool:
        raise TypeError("Subclasses should override validate.")


class ParsedEditString:
    def __init__(self, parser, editor=None):
        self.parser = parser
        self.editor = editor if editor is not None else EditString(multiline=False)

    def run(self):
        self.editor.run()

    def dispatch(self, key):
        self.editor.dispatch(key)

    def __rich__(self):
        try:
            self.parser(self.editor.result)
            return self.editor
        except ValueError:
            return Styled(self.editor, style=Style(color="red"))

    @property
    def result(self):
        return self.parser(self.editor.result)


def parse_numeric(text):
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return complex(text)


EditIntString = partial(ParsedEditString, parser=int)
EditFloatString = partial(ParsedEditString, parser=float)
EditComplexString = partial(ParsedEditString, parser=complex)
EditNumericString = partial(ParsedEditString, parser=parse_numeric)
EditEnumString = lambda enum_cls: ParsedEditString(parser=enum_cls)
