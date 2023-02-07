from rich.style import Style
from rich.text import Text

from twidge.core import DispatchBuilder, Event, RunBuilder, StrEvent
from twidge.widgets.editors import _fullview, _scrollview


class InlineEditor:
    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(self, text: str = "", scroll: bool = True):
        self.text = text
        self.cursor = 0
        self.focus = True
        self.scroll = scroll

    @property
    def result(self) -> str:
        return self.text

    def __rich_console__(self, console, options):
        width = options.size.width

        if self.scroll:
            if 0 <= self.cursor < len(self.text):
                sstr, cstr, estr = _scrollview(self.text, self.cursor, width)
            else:
                sstr, cstr, estr = (
                    self.text[max(0, self.cursor - (width - 1)) : self.cursor],
                    " ",
                    "",
                )
        else:
            if 0 <= self.cursor < len(self.text):
                sstr, cstr, estr = _fullview(self.text, self.cursor, width)
            else:
                sstr, cstr, estr = self.text, " ", ""

        yield (
            Text(sstr, style=Style(color="bright_yellow", bold=True), end="")
            + Text(
                cstr, style=Style(color="grey30", bgcolor="grey70", bold=True), end=""
            )
            + Text(estr, style=Style(color="bright_yellow", bold=True), end="")
            if self.focus
            else Text(sstr, end="") + Text(cstr, end="") + Text(estr, end="")
        )

    @dispatch.on("left")
    def cursor_left(self):
        if self.cursor != 0:
            self.cursor -= 1

    @dispatch.on("right")
    def cursor_right(self):
        if self.cursor < len(self.text):
            self.cursor += 1

    @dispatch.on("ctrl+right")
    def next_word(self):
        next_space = self.text[self.cursor :].find(" ")
        if next_space == -1:
            self.cursor = len(self.text)
        else:
            self.cursor = self.cursor + next_space + 1

    @dispatch.on("ctrl+left")
    def prev_word(self):
        prev_space = self.text[max(0, self.cursor - 2) :: -1].find(" ")
        if prev_space < 0:
            self.cursor = 0
        else:
            self.cursor = self.cursor - prev_space - 1

    @dispatch.on("home")
    def cursor_home(self):
        self.cursor = 0

    @dispatch.on("end")
    def cursor_end(self):
        self.cursor = len(self.text)

    @dispatch.on("backspace")
    def backspace(self):
        if self.cursor != 0:
            self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
            self.cursor -= 1

    @dispatch.on("ctrl+h")
    def delete_word(self):
        prev_space = self.text[: self.cursor - 1][::-1].find(" ")
        if prev_space == -1:
            n = 0
        else:
            n = self.cursor - prev_space - 2
        self.text = self.text[:n] + self.text[self.cursor :]
        self.cursor = n

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
        if self.cursor == len(self.text):
            self.text += char
        else:
            self.text = self.text[: self.cursor] + char + self.text[self.cursor :]
        self.cursor += len(char)


class InlineCycler:
    dispatch = DispatchBuilder()
    run = RunBuilder()

    def __init__(
        self,
        *options: str,
        key=str,
        focus_style: str | Style = Style.parse("bright_yellow on magenta"),
        blur_style: str | Style = Style.parse("white on black"),
    ):
        self.options = options
        self.key = key
        self.len = len(self.options)
        self.index = 0
        self.focus = True
        self.focus_style = focus_style
        self.blur_style = blur_style

    @dispatch.on(StrEvent("focus"))
    def on_focus(self):
        self.focus = True

    @dispatch.on(StrEvent("blur"))
    def on_blur(self):
        self.focus = False

    @dispatch.on("space", "right")
    def forward(self):
        self.index = (self.index + 1) % self.len

    @dispatch.on("left")
    def back(self):
        self.index = (self.index - 1) % self.len

    @dispatch.default
    def drop_events(self, event: Event):
        pass

    def __rich__(self):
        opt = self.key(self.options[self.index])
        if self.focus:
            return Text(f"←{opt}→", style="bright_yellow", end="")
        else:
            return Text(opt, end="")

    @property
    def result(self):
        return self.options[self.index]


__all__ = ["InlineEditor", "InlineCycler"]
