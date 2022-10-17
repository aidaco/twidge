import re

import pandas as pd
from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .core import display, focusdispatcher, trigger


class echo(display):
    def __init__(self):
        self.keys = []

    def __trigger__(self, key):
        self.keys.append(key)

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


class editstr(trigger.auto, display):
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

    @trigger.on("left")
    def cursor_left(self):
        if self.cursor[1] != 0:
            self.cursor[1] -= 1
            if self.lines[self.cursor[0]][self.cursor[1]] == "\n":
                self.cursor[1] -= 1
        else:
            if self.cursor[0] != 0:
                self.cursor[0] = self.cursor[0] - 1
                self.cursor[1] = len(self.lines[self.cursor[0]]) - 1

    @trigger.on("right")
    def cursor_right(self):
        if self.cursor[1] < len(self.lines[self.cursor[0]]) - 1:
            self.cursor[1] += 1
        else:
            if self.cursor[0] < len(self.lines) - 1:
                self.cursor[0] += 1
                self.cursor[1] = 0

    @trigger.on("up")
    def cursor_up(self):
        if self.cursor[0] > 0:
            self.cursor[0] -= 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    @trigger.on("down")
    def cursor_down(self):
        if self.cursor[0] < len(self.lines) - 1:
            self.cursor[0] += 1
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))

    @trigger.on("ctrl+right")
    def next_word(self):
        line = self.lines[self.cursor[0]]
        next_space = line[self.cursor[1] :].find(" ")
        if next_space == -1:
            self.cursor[1] = len(line)
        else:
            self.cursor[1] = self.cursor[1] + next_space + 1

    @trigger.on("ctrl+left")
    def prev_word(self):
        line = self.lines[self.cursor[0]]
        prev_space = line[: self.cursor[1] - 1][::-1].find(" ")
        if prev_space < 0:
            self.cursor[1] = 0
        else:
            self.cursor[1] = self.cursor[1] - prev_space - 1

    @trigger.on("ctrl+h")
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

    @trigger.on("backspace")
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

    @trigger.on("space")
    def space(self):
        self.insert(" ")

    @trigger.on("enter")
    def enter(self):
        self.insert("\n")

    @trigger.on("tab")
    def tab(self):
        self.insert("\t")


class editdict(display):
    def __init__(self, content: dict[str, str] | list[str], display=lambda x: x):
        self.display = display
        if isinstance(content, list):
            self.editors = {k: editstr(show_cursor=False) for k in content}
        else:
            self.editors = {
                k: editstr(v, show_cursor=False) for k, v in content.items()
            }
        self.__trigger__ = focusdispatcher(list(self.editors.values())).__trigger__

    def result(self):
        return {key: editor.result() for key, editor in self.editors.items()}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for k, e in self.editors.items():
            t.add_row(f"[bold yellow]{self.display(k)}[/]", e)
        return Panel(t, border_style="magenta")


class searchdf(trigger.auto, display):
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
        return Panel(content, title=self.query, title_align="left", style="bold cyan")

    def search(self) -> pd.DataFrame:
        return self.subset[self.full_text.str.contains(self.query, case=self.case)]

    def refresh(self):
        if len(self.query) == 0:
            self.subset = self.data
        else:
            self.subset = self.search()

    @trigger.on("ctrl+d")
    def clear(self):
        self.query = ""
        self.refresh()

    @trigger.on("backspace")
    def backspace(self):
        self.query = self.query[:-1]
        self.refresh()

    @trigger.default
    def update(self, key):
        if len(k := key) == 1:
            self.query += str(k)
            self.refresh()


class filterlist(trigger.auto, display):
    def __init__(self, options: list[str]):
        self.options = options
        self.reset()

    def filter(self):
        return {e for e in self.subset if re.search(self.query, e, re.IGNORECASE)}

    def result(self):
        return list(self.subset)

    def __rich__(self):
        if len(self.subset) == 0:
            content = "No matches."
        else:
            content = Group(*self.subset, fit=True)
        return Panel(content, title=self.query, title_align="left", style="bold cyan")

    def refresh(self):
        self.subset = self.filter()

    def reset(self):
        self.query = ""
        self.subset = set(self.options)

    @trigger.on("ctrl+d")
    def clear(self):
        self.reset()

    @trigger.on("backspace")
    def backspace(self):
        self.query = self.query[:-1]
        self.refresh()

    @trigger.default
    def update(self, key):
        if len(k := key) == 1:
            self.query += str(k)
            self.refresh()


class retrievelist(filterlist):
    def __rich__(self):
        table = Table.grid(padding=(0, 1, 0, 0))
        table.add_column()
        table.add_column()
        for i, o in enumerate(self.options):
            if o in self.subset:
                table.add_row(f"[cyan]{i+1}[/]", f"[on green]{o}[/]")
            else:
                table.add_row(f"[cyan]{i+1}[/]", f"[bold yellow]{o}[/]")
        return Panel(
            table,
            title=f"[bold yellow]{self.query}[/]",
            title_align="left",
            border_style="magenta",
        )

    def reset(self):
        self.query = ""
        self.subset = {}

    @trigger.on("space")
    def space(self):
        self.update(" ")

    def filter(self):
        try:
            indices = (
                int(m.group(1)) - 1
                for m in re.compile(r"\W*(\d+)\W*").finditer(self.query)
            )
            return [self.options[i] for i in indices]
        except (ValueError, IndexError):
            return {}
