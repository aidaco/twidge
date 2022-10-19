import re

import pandas as pd
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from twidge.core import display, trigger


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
