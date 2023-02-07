import sys
import typing

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.styled import Styled
from rich.text import Text

from twidge.core import DispatchBuilder, Event, RunBuilder, StrEvent, WidgetType

ContentType: typing.TypeAlias = WidgetType | RenderableType


def _safedispatch(obj: typing.Any, event: Event):
    """Attempt to dispatch and silence if the object doesn't have a dispatch method."""

    try:
        fn = obj.dispatch
    except AttributeError:
        return
    else:
        fn(event)


class Close:
    def __init__(
        self, content: ContentType, *, close: str = "ctrl+w", crash: str = "ctrl+c"
    ):
        self.content = content
        self.close_event = close
        self.crash_event = crash

    run = RunBuilder()
    dispatch = DispatchBuilder()

    def close(self):
        self.run.stop()

    def crash(self):
        sys.exit(1)

    @dispatch.default
    def passthrough(self, event: Event):
        match event:
            case self.close_event:
                self.close()
            case self.crash_event:
                self.crash()
            case _:
                _safedispatch(self.content, event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        return self.content


class Framed:
    """Applies a frame to the content."""

    def __init__(
        self, content: ContentType, *, style: str | Style = Style.parse("white")
    ):
        self.content = content
        self.style = style

    dispatch = DispatchBuilder()

    @dispatch.default
    def passthrough(self, event: Event):
        _safedispatch(self.content, event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        return Panel.fit(self.content, border_style=self.style)


class Labelled:
    def __init__(
        self,
        content: ContentType,
        *,
        label: str,
        style: str | Style = Style.parse("bold cyan"),
    ):
        self.content = content
        self.label = label
        self.style = Style.parse(style) if isinstance(style, str) else style

    def __rich__(self):
        label = Text(self.label, style=self.style, end="")
        return Group(label, self.content)

    dispatch = DispatchBuilder()

    @dispatch.default
    def passthrough(self, event: Event):
        _safedispatch(self.content, event)

    @property
    def result(self):
        return self.content.result


class FocusManager:
    def __init__(self, *widgets, focus: int = 0):
        self.widgets = list(widgets)
        self.focus = focus
        _safedispatch(self.focused, StrEvent("focus"))
        for w in self.blurred:
            _safedispatch(w, StrEvent("blur"))

    @property
    def blurred(self):
        """Iterator over widgets that are not focused."""
        yield from (w for i, w in enumerate(self.widgets) if i != self.focus)

    @property
    def focused(self):
        """The currently focused item."""
        return self.widgets[self.focus]

    def forward(self):
        """Focus the next item."""
        _safedispatch(self.widgets[self.focus], StrEvent("blur"))
        if self.focus == len(self.widgets) - 1:
            self.focus = 0
        else:
            self.focus += 1
        _safedispatch(self.widgets[self.focus], StrEvent("focus"))

    def back(self):
        """Focus the previous item."""
        _safedispatch(self.widgets[self.focus], StrEvent("blur"))
        if self.focus == 0:
            self.focus = len(self.widgets) - 1
        else:
            self.focus -= 1
        _safedispatch(self.widgets[self.focus], StrEvent("focus"))


class FocusGroup:
    """Renders a group of Widgets with focus dispatching."""

    dispatch = DispatchBuilder()

    def __init__(self, *widgets):
        self.fm = FocusManager(*widgets)

    def __rich__(self):
        return Group(*self.fm.widgets)

    @property
    def result(self):
        return [w.result for w in self.fm.widgets]

    @dispatch.on("tab")
    def focus_advance(self):
        self.fm.forward()

    @dispatch.on("shift+tab")
    def focus_back(self):
        self.fm.back()

    @dispatch.default
    def passthrough(self, event):
        self.fm.focused.dispatch(event)


class FocusStyled:
    """Apply the given focus and blur styles to a widget that otherwise wouldnt respond."""

    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(
        self,
        content,
        blur_style: str | Style = Style.parse("white on black"),
        focus_style: str | Style = Style.parse("bold yellow"),
    ):
        self.content = content
        self.focus_style = focus_style
        self.focus_style = (
            Style.parse(focus_style) if isinstance(focus_style, str) else focus_style
        )
        self.blur_style = (
            Style.parse(blur_style) if isinstance(blur_style, str) else blur_style
        )

    @dispatch.on("focus")
    def on_focus(self):
        self.focus = True

    @dispatch.on("blur")
    def on_blur(self):
        self.focus = False

    @dispatch.default
    def passthrough(self, event):
        return self.content.dispatch(event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        return Styled(self.content, self.focus_style) if self.focus else self.content


class FocusFramed:
    """A focus-sensitive colored frame."""

    run = RunBuilder()
    dispatch = DispatchBuilder()

    def __init__(
        self,
        content,
        blur_style: str | Style = Style.parse("white on black"),
        focus_style: str | Style = Style.parse("yellow"),
    ):
        self.content = content
        self.focus = False
        self.blur_style = (
            Style.parse(blur_style) if isinstance(blur_style, str) else blur_style
        )
        self.focus_style = (
            Style.parse(focus_style) if isinstance(focus_style, str) else focus_style
        )

    @dispatch.on("focus")
    def on_focus(self):
        self.focus = True

    @dispatch.on("blur")
    def on_blur(self):
        self.focus = False

    @dispatch.default
    def default(self, event):
        self.content.dispatch(event)

    @property
    def result(self):
        return self.content.result

    def __rich__(self):
        style = self.focus_style if getattr(self, "focus", False) else self.blur_style
        return Panel.fit(self.content, border_style=style)


__all__ = [
    "Close",
    "Labelled",
    "Framed",
    "FocusManager",
    "FocusFramed",
    "FocusGroup",
    "FocusStyled",
]
