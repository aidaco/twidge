import re
import typing
from functools import partial
from math import ceil, floor

from rich.measure import Measurement
from rich.style import Style
from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from twidge.core import DispatchBuilder, RunBuilder
from twidge.widgets.wrappers import FocusManager


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
        yield from (Text(line[:width]) for line in slines)

        # Render cursor line
        yield (
            Text(sstr) + Text(cstr, style="grey30 on grey70") + Text(estr)
            if self.focus
            else Text(sstr) + Text(cstr) + Text(estr)
        )

        # Render lines after cursor, if any
        yield from (Text(line[:width]) for line in elines)

    def __rich_measure__(self, console, options):
        width = max(len(line) for line in self.lines) + 1
        return Measurement(width, width)

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
        sec = line[self.cursor[1] + 1 :]
        m = re.search(r"\W|$", sec)
        next_non_word = m.end()
        self.cursor[1] = self.cursor[1] + next_non_word + 1

    @dispatch.on("ctrl+left")
    def prev_word(self):
        line = self.lines[self.cursor[0]]
        sec = line[: self.cursor[1]][::-1]
        m = re.search(r"\W\w|$", sec)
        prev_non_word = m.end()
        self.cursor[1] = self.cursor[1] - prev_non_word

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
        line = self.lines[self.cursor[0]]
        sec = line[: self.cursor[1]][::-1]
        m = re.search(r"(?>.)\b|$", sec)
        prev_non_word = m.end()
        n = self.cursor[1] - prev_non_word
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
        match char.split('\r'): # Raw stdin doesn't translate \r to \n
            case [ch]:
                line = self.lines[self.cursor[0]]
                line = line[: self.cursor[1]] + ch + line[self.cursor[1] :]
                self.cursor[1] += len(ch)
                self.lines[self.cursor[0]] = line
            case [first, last]:
                line = self.lines[self.cursor[0]]
                line1 = line[:self.cursor[1]] + first
                line2 = last + line[self.cursor[1]:]
                self.lines[self.cursor[0]] = line1
                self.lines.insert(self.cursor[0] + 1, line2)
                self.cursor[0] += 1
                self.cursor[1] = len(last)
            case [first, *middle, last]:
                line = self.lines[self.cursor[0]]
                line1 = line[:self.cursor[1]] + first
                line2 = last + line[self.cursor[1]:]
                self.lines[self.cursor[0]:self.cursor[0]+1] = [line1] + middle + [line2]
                self.cursor[0] += len(middle) + 1
                self.cursor[1] = len(last)


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

def EditEnumString(enum_cls):
    return ParsedEditString(parser=enum_cls)


class EditDict:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, content: dict[str, str]):
        self.content = content
        self.editors = {EditString(k): EditString(v) for k, v in content.items()}
        self.focuser = FocusManager(*(w for kv in self.editors.items() for w in kv))

    @property
    def result(self):
        return {k.result: v.result for k, v in self.editors.items()}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for k, v in self.editors.items():
            t.add_row(Styled(k, style="bright_green"), v)
        return t

    @dispatch.on("tab")
    def focus_advance(self):
        self.focuser.forward()

    @dispatch.on("shift+tab")
    def focus_back(self):
        self.focuser.back()

    @dispatch.default
    def passthrough(self, event):
        self.focuser.focused.dispatch(event)


__all__ = ["EditString", "EditDict"]
