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

        yield (m.group("tag"), parser(m.group("literal")))

        last = f
    if last < len(text):
        yield text[last:]


class TemplateResult:
    def __init__(self, editor):
        self.editor = editor

    @property
    def substituted(self):
        return "".join(self.editor.substitute(lambda e: e.result))

    @property
    def tagged(self):
        return {t: w.result for t, w in self.editor.tagged.items()}

    @property
    def auto(self):
        return [w.result for w in self.editor.auto]

    def __str__(self):
        return self.substituted


class EditTemplate:
    run = RunBuilder()

    def __init__(self, source):
        self.tagged = {}
        self.auto = []
        self.content = []
        for e in _iterparts(source):
            if isinstance(e, tuple):
                tag, e = e
                if tag is not None:
                    if tag in self.tagged:
                        e = self.tagged[tag]
                    else:
                        self.tagged[tag] = e
                else:
                    self.auto.append(e)
            self.content.append(e)
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
        return TemplateResult(self)

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
