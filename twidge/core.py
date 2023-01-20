import sys
from inspect import signature
from typing import (
    BinaryIO,
    Callable,
    Iterable,
    Protocol,
    Type,
    TypeAlias,
    runtime_checkable,
)

from rich.console import Console, ConsoleOptions, RenderableType
from rich.live import Live

from twidge.terminal import chbreak, keystr


class EventBase:
    ...


Event: TypeAlias = EventBase | str | bytes


@runtime_checkable
class SingleHandler(Protocol):
    def __call__(self) -> None:
        pass


@runtime_checkable
class MultiHandler(Protocol):
    def __call__(self, event: Event) -> None:
        pass


class RichWidget(Protocol):
    def __rich__(self) -> RenderableType:
        ...

    def dispatch(self, event: Event) -> None:
        ...


class ConsoleWidget(Protocol):
    def __rich_console__(
        self, console: Console, console_options: ConsoleOptions
    ) -> Iterable[RenderableType]:
        ...

    def dispatch(self, event: Event) -> None:
        ...


Handler: TypeAlias = SingleHandler | MultiHandler
Widget: TypeAlias = RichWidget | ConsoleWidget


class Reader(Protocol):
    def __init__(self, io: BinaryIO):
        ...

    def read(self) -> Event:
        ...


class BytesReader:
    def __init__(self, io: BinaryIO):
        self.io = io

    def read(self) -> bytes:
        return self.io.read(6)


class StrReader:
    def __init__(self, io: BinaryIO):
        self.io = io
        self.reader = BytesReader(io)

    def read(self) -> str:
        return keystr(self.reader.read())


class Runner:
    def __init__(
        self,
        widget: Widget,
        stdin: int | None = None,
        reader: Type[Reader] = StrReader,
        console: Console | None = None,
    ):
        self.widget = widget
        self.stdin = stdin if stdin is not None else sys.stdin.fileno()
        self.reader = reader
        self.console = (
            console
            if console is not None
            else Console(highlight=False, markup=False, emoji=False)
        )

        self.running = False

    def run(self):
        self.running = True
        with chbreak(stdin=self.stdin), Live(
            self.widget,
            console=self.console,
            transient=True,
            auto_refresh=False,
        ) as live:
            refresh = live.refresh
            read = self.reader(open(self.stdin, "rb", buffering=0, closefd=False)).read
            dispatch = self.widget.dispatch
            while self.running:
                dispatch(read())
                refresh()
        return getattr(self.widget, "result", None)

    def stop(self):
        self.running = False

    __call__ = run


class Dispatcher:
    def __init__(
        self,
        table: dict[Event, Handler] | None = None,
        default: Handler | None = None,
    ):
        self.table = table if table is not None else {}
        self.default = default

    def dispatch(self, event: Event) -> None:
        fn = self.table.get(event, self.default)
        if fn is None:
            raise ValueError(f"No handler for {event!r}")
        match len(signature(fn).parameters):
            case 0:
                fn()
            case 1:
                fn(event)
            case _:
                raise TypeError("Handler should take one or zero arguments.")

    def update(
        self, table: dict[Event, Handler] | None = None, default: Handler | None = None
    ):
        if table:
            self.table.update(table)
        if default:
            self._default = default

    __call__ = dispatch


class RunBuilder:
    def __init__(
        self,
        stdin: int | None = None,
        reader: Type[Reader] = StrReader,
        console: Console | None = None,
    ):
        self.stdin = stdin
        self.reader = reader
        self.console = console

    def build(self, widget):
        return Runner(widget, self.stdin, self.reader, self.console)

    def __get__(self, obj, obj_type=None):
        if obj is None:
            return self
        obj.run = self.build(obj)
        return obj.run


class DispatchBuilder:
    def __init__(
        self,
        methods: dict[Event, str] | None = None,
        table: dict[Event, Handler] | None = None,
        defaultfn: Handler | str | None = None,
    ):
        self.methods = methods if methods is not None else {}
        self.table = table if table is not None else {}
        self.defaultfn = defaultfn if defaultfn is not None else {}

    def on(self, *events: Event):
        def decorate(fn: Callable):
            for e in events:
                self.methods[e] = fn.__name__
            return fn

        return decorate

    def default(self, fn: Callable):
        self.defaultfn = fn.__name__
        return fn

    def build(self, widget):
        table = self.table | {e: getattr(widget, m) for e, m in self.methods.items()}
        default = (
            getattr(widget, self.defaultfn)
            if isinstance(self.defaultfn, str)
            else self.defaultfn
        )
        return Dispatcher(table=table, default=default)

    def __get__(self, obj, obj_type=None):
        if obj is None:
            return self
        obj.dispatch = self.build(obj)
        return obj.dispatch
