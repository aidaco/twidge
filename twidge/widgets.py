import re
import typing

import pandas as pd
from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.segment import Segments
from rich.style import Style

from twidge.core import TUI, AutoDispatch, Exit, default, on


class AutoFocus(AutoDispatch):
    """Subclasses are a assigned a managed self.focus: bool attribute."""

    @on("focus")
    def onfocus(self):
        self.focus = True

    @on("blur")
    def onblur(self):
        self.focus = False


class Echo(TUI):
    def __init__(self):
        self.keys = []

    def dispatch(self, key):
        self.keys.append(key)

    def __rich__(self):
        chars = (f"'{ch}'" for ch in self.keys)
        return "[cyan]" + " ".join(chars) + "[/]"


class Escape(TUI):
    def __init__(self, widget, key: str = "ctrl+c"):
        self.key = key
        self.widget = widget

    def __rich__(self):
        return self.widget

    def result(self):
        return self.widget.result()

    def dispatch(self, key):
        if key == self.key:
            raise Exit("Bye")
        else:
            self.widget.dispatch(key)

class Abort(TUI):
    def __init__(self, widget, seq: list[str] = ["escape", "escape", "escape"]):
        self.seq = seq
        self.keys = ['']*len(seq)
        self.widget = widget

    def __rich__(self):
        return self.widget

    def result(self):
        return self.widget.result()

    def dispatch(self, key):
        self.keys = self.keys[1:] + [key]
        if self.keys == self.seq:
            raise SystemExit()
        else:
            self.widget.dispatch(key)

class Framed(TUI):
    def __init__(self, content):
        self.content = content

    def __rich__(self):
        return Panel.fit(self.content)

    def dispatch(self, key):
        self.content.dispatch(key)

    def result(self):
        return self.content.result()


class Labelled(TUI):
    def __init__(self, label, widget):
        self.widget = widget
        self.label = label

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        t.add_row(f"[bold yellow]{self.label}[/]", self.widget)
        return t

    def dispatch(self, key):
        self.widget.dispatch(key)

    def result(self):
        return self.widget.result()


class Toggle(TUI, AutoFocus):
    def __init__(self, value: bool, on_true, on_false):
        self.value = value
        self.on_true = on_true
        self.on_false = on_false
        self.focus = True

    def __rich_console__(self, console, options):
        if self.focus:
            return self.on_true if self.value else self.on_false
        else:
            return Segments.apply_style(console.render_lines(self.value), Style.null())

    @default
    def switch(self, key):
        self.value = not self.value

    def result(self):
        return self.value


class Button(TUI, AutoDispatch):
    def __init__(self, content, target: typing.Callable):
        self.content = content
        self.target = target
        self.focus = True

    def __rich__(self):
        return Panel.fit(self.content, style="green" if self.focus else "")

    @on("focus")
    def onfocus(self):
        self.focus = True

    @on("blur")
    def onblur(self):
        self.focus = False

    @on("enter")
    def click(self):
        self.target()

    @default
    def drop(self, key):
        ...


class FocusFramed(Framed, AutoFocus):
    def __rich__(self):
        return Panel.fit(self.content, border_style="green" if self.focus else "gray")


class FocusGroup(TUI, AutoDispatch):
    def __init__(self, *widgets):
        self.widgets = list(widgets)
        self.focus = 0
        getattr(self.widgets[0], "dispatch", lambda e: None)("focus")
        for w in self.widgets[1:]:
            getattr(w, "dispatch", lambda e: None)("blur")

    def __rich__(self):
        return Group(*self.widgets)

    @on("tab")
    def focus_next(self):
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("blur")
        if self.focus == len(self.widgets) - 1:
            self.focus = 0
        else:
            self.focus += 1
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")

    @on("shift+tab")
    def focus_previous(self):
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("blur")
        if self.focus == 0:
            self.focus = len(self.widgets) - 1
        else:
            self.focus -= 1
        getattr(self.widgets[self.focus], "dispatch", lambda e: None)("focus")

    @default
    def dispatch_to_focus(self, key):
        self.widgets[self.focus].dispatch(key)

    def result(self):
        return [w.result() for w in self.widgets]


class SearchList(TUI, AutoDispatch):
    def __init__(self, options: list[str]):
        self.options = options
        self.reset()

    def filter(self):
        return [e for e in self.subset if re.search(self.query, e, re.IGNORECASE)]

    def result(self):
        return self.subset

    def __rich__(self):
        if len(self.subset) == 0:
            content = "No matches."
        else:
            content = Group(*self.subset, fit=True)
        return Group(f"[bold cyan]{self.query}[/]", content)

    def refresh(self):
        self.subset = self.filter()

    def reset(self):
        """Resets to like-new."""
        self.query = ""
        self.subset = self.options
        self.refresh()

    def recalculate(self):
        """Keep query, reset options and rerun search."""
        self.subset = self.options
        self.refresh()

    @on("ctrl+d")
    def clear(self):
        self.reset()

    @on("backspace")
    def backspace(self):
        self.query = self.query[:-1]
        self.recalculate()

    @default
    def update(self, key):
        if len(k := key) == 1:
            self.query += str(k)
            self.refresh()


class SearchDataFrame(SearchList):
    def __init__(self, df: pd.DataFrame, sep="\t", case=False):
        self.data = df
        self.subset = df
        self.case = case
        self.sep = sep
        self.full_text = df.agg(sep.join, axis=1)
        self.query = ""

    def __rich__(self):
        if len(self.subset) == 0:
            content = "No matches."
        else:
            content = Table(
                *self.subset,
                expand=True,
                pad_edge=False,
                padding=0,
            )
            self.subset.astype(str).apply(lambda r: content.add_row(*r), axis=1)
        return Group(f"[bold cyan]{self.query}[/]", content)

    def search(self) -> pd.DataFrame:
        return self.subset[self.full_text.str.contains(self.query, case=self.case)]

    def refresh(self):
        if len(self.query) == 0:
            self.subset = self.data
        else:
            self.subset = self.search()

    def result(self):
        return self.subset


class SelectList(SearchList):
    RE_NUMSEQ = re.compile(r"\W*(\d+)\W*")

    def __rich__(self):
        table = Table.grid(padding=(0, 1, 0, 0))
        table.add_column()
        table.add_column()
        for i, o in enumerate(self.options):
            if o in self.subset:
                table.add_row(f"[cyan]{i+1}[/]", f"[on green]{o}[/]")
            else:
                table.add_row(f"[cyan]{i+1}[/]", f"{o}")
        return Group(f"[bold yellow]{self.query}[/]", table)

    def reset(self):
        self.query = ""
        self.subset = []

    @on("space")
    def space(self):
        self.update(" ")

    def filter(self):
        try:
            return [
                self.options[int(m.group(1)) - 1]
                for m in self.RE_NUMSEQ.finditer(self.query)
            ]
        except (ValueError, IndexError):
            return []


class EditStr(TUI, AutoFocus):
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
            return (
                f"[bold cyan]{nl.join(self.lines)}[/]"
                if self.focus
                else nl.join(self.lines)
            )
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


class WatchCursor(TUI):
    """Display cursor position with an editor."""

    def __init__(self, editor):
        self.editor = editor

    def __rich__(self):
        return Group(Panel.fit(f"Cursor: {self.editor.cursor}"), self.editor)

    def dispatch(self, key):
        self.editor.dispatch(key)


class Form(FocusGroup):
    def __init__(self, content: list[str]):
        self.labels = content
        super().__init__(*(EditStr(show_cursor=False) for k in content))

    def result(self):
        return {l: w.result() for l, w in zip(self.labels, self.widgets)}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for l, w in zip(self.labels, self.widgets):
            t.add_row(f"[bold yellow]{l}[/]", w)
        return t
