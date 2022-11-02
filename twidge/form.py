from twidge.widgets import FocusGroup
from twidge.editors import EditLine, EditMultiline


class Form(FocusGroup):
    def __init__(self, content: list[str]):
        self.labels = content
        super().__init__(*(EditLine() for k in content))

    def result(self):
        return {l: w.result() for l, w in zip(self.labels, self.widgets)}

    def __rich__(self):
        t = Table.grid(padding=(0, 1, 0, 0))
        t.add_column()
        t.add_column()
        for l, w in zip(self.labels, self.widgets):
            t.add_row(f"[bold yellow]{l}[/]", w)
        return t
