import re
from functools import cached_property
from typing import Any, Callable

from rich.console import RenderableType
from rich.text import Text

from twidge.core import RunBuilder, WidgetType
from twidge.widgets.inline import InlineCycler, InlineEditor
from twidge.widgets.wrappers import FocusManager

Identifier = r"[^\d\W]\w*"
Spec = rf"(?P<tag>{Identifier})?(?::(?P<literal>[^{{}}]*))?"
FieldPattern = re.compile("(?<!{)(?:{{2})*({" + Spec + "})(?:}{2})*(?!})")
# Placeholder = "(?<!{)(?:{{2})*({([^{}]*)})(?:}{2})*(?!})"


def _parse_literal(source: str | None) -> WidgetType:
    if source is None:
        return InlineEditor()  # type: ignore
    try:
        return eval(
            source, {"__builtins__": {"str": InlineEditor, "opt": InlineCycler}}
        )
    except Exception:
        raise ValueError(f'Unable to parse "{source}".')


def _iterparts(
    text: str,
    parser: Callable[[str], WidgetType] = _parse_literal,
    pattern: re.Pattern = FieldPattern,
):
    last = 0
    for m in pattern.finditer(text):
        i, f = m.span(1)
        yield text[last:i]

        # TODO: Replace the uncommented line when better tag supprt.
        # yield (m.group("tag"), parser(m.group("literal")))
        yield parser(m.group("literal"))

        last = f
    if last < len(text):
        yield text[last:]


class EditTemplate:
    run = RunBuilder()

    def __init__(self, source):
        self.content = list(_iterparts(source))
        self.fm = FocusManager(*self.widgets)

    def substitute(self, fn: Callable[[WidgetType], Any]):
        yield from (fn(c) if isinstance(c, WidgetType) else c for c in self.content)

    def filter(self, fn: Callable[[RenderableType | WidgetType], bool]):
        yield from (c for c in self.content if fn(c))

    @cached_property
    def widgets(self):
        seen = set()
        return [
            c
            for c in self.filter(lambda e: isinstance(e, WidgetType))
            if not (c in seen or seen.add(c))
        ]

    @property
    def result(self):
        return "".join(self.substitute(lambda e: e.result))

    def dispatch(self, event):
        match event:
            case "tab":
                self.fm.forward()
            case "shift+tab":
                self.fm.back()
            case _:
                self.fm.focused.dispatch(event)

    def __rich_console__(self, console, console_options):
        return [Text(s, end="") if isinstance(s, str) else s for s in self.content]


__all__ = ["EditTemplate"]
