import pandas as pd
from rich.panel import Panel
from rich.table import Table
from textual.app import App
from textual.reactive import Reactive
from textual.widget import Widget


class FullTextSearcher(Widget):
    query = Reactive("")

    def __init__(self, df: pd.DataFrame, sep="\t", case=False):
        self.df = df
        self.case = case
        self.sep = sep
        self.full_text = df.agg(sep.join, axis=1)
        super().__init__()

    def search(self) -> pd.DataFrame:
        return self.df[self.full_text.str.contains(self.query, case=self.case)]

    def render(self):
        result = self.search() if len(self.query) > 2 else None
        if result is None:
            content = "Type to see results."
        elif len(result) > 0:
            content = Table(
                *self.df,
                expand=True,
                pad_edge=False,
                padding=0,
            )
            result.astype(str).apply(lambda r: content.add_row(*r), axis=1)
        else:
            content = "No results to show."
        return Panel(content, title=self.query, title_align="left", style="bold cyan")

    def clear(self):
        self.query = ""

    def on_key(self, event):
        if len(k := event.key) == 1:
            self.query += str(k)


def searchdf(df: pd.DataFrame) -> None:
    class SearchApp(App):
        async def on_load(self, event) -> None:
            await self.bind("escape", "quit", "Quit")
            await self.bind("ctrl+d", "clear", "Clear")

        async def on_mount(self, event) -> None:
            self.fts = FullTextSearcher(df)
            await self.view.dock(self.fts, edge="top")

        async def action_clear(self) -> None:
            self.fts.clear()

    SearchApp.run()
