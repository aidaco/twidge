import sys
from inspect import signature
from typing import BinaryIO, Callable, Protocol, Type, TypeAlias, runtime_checkable

from rich.console import Console
from rich.live import Live

from twidge.terminal import chbreak, keystr


class Event:
    pass


class StrEvent(Event, str):
    pass


class BytesEvent(Event, bytes):
    pass


class StrKey(StrEvent):
    pass


class BytesKey(BytesEvent):
    pass


@runtime_checkable
class SingleHandler(Protocol):
    def __call__(self) -> None:
        pass


@runtime_checkable
class MultiHandler(Protocol):
    def __call__(self, event: Event) -> None:
        pass


class WidgetMeta(type):
    def __subclasscheck__(cls, subcls):
        renderable = hasattr(subcls, "__rich__") or hasattr(subcls, "__rich_console__")
        interactive = hasattr(subcls, "dispatch") and hasattr(subcls, "result")
        return renderable and interactive

    def __instancecheck__(cls, obj):
        renderable = hasattr(obj, "__rich__") or hasattr(obj, "__rich_console__")
        interactive = hasattr(obj, "dispatch") and hasattr(obj, "result")
        return renderable and interactive


class WidgetType(metaclass=WidgetMeta):
    pass


HandlerType: TypeAlias = SingleHandler | MultiHandler


class ReaderType(Protocol):
    def __init__(self, io: BinaryIO):
        ...

    def read(self) -> Event:
        ...


class BytesReader:
    def __init__(self, io: BinaryIO):
        self.io = io

    def read(self) -> BytesKey:
        return BytesKey(self.io.read(6))


class StrReader:
    def __init__(self, io: BinaryIO):
        self.io = io
        self.reader = BytesReader(io)

    def read(self) -> StrKey:
        return StrKey(keystr(self.reader.read()))


class Runner:
    def __init__(
        self,
        widget: WidgetType,
        stdin: int | None = None,
        reader: Type[ReaderType] = StrReader,
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
        table: dict[Event, HandlerType] | None = None,
        default: HandlerType | None = None,
    ):
        self.table = table if table is not None else {}
        self.default = default

    def dispatch(self, event: Event) -> None:
        fn = self.table.get(event, self.default)
        if fn is None:
            raise ValueError(f"No handler for {event!r}")
        match len(signature(fn).parameters):
            case 0:
                fn()  # type: ignore
            case 1:
                fn(event)  # type: ignore
            case _:
                raise TypeError("Handler should take one or zero arguments.")

    def update(
        self,
        table: dict[Event, HandlerType] | None = None,
        default: HandlerType | None = None,
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
        reader: Type = StrReader,
        console: Console | None = None,
    ):
        self.stdin = stdin
        self.reader = reader
        self.console = console

    def build(self, widget: WidgetType):
        return Runner(
            widget, stdin=self.stdin, reader=self.reader, console=self.console
        )

    def __get__(self, obj, obj_type=None):
        if obj is None:
            return self
        obj.run = self.build(obj)
        return obj.run


class DispatchBuilder:
    def __init__(
        self,
        methods: dict[Event, str] | None = None,
        table: dict[Event, HandlerType] | None = None,
        defaultfn: HandlerType | str | None = None,
    ):
        self.methods = methods if methods is not None else {}
        self.table = table if table is not None else {}
        self.defaultfn = defaultfn

    def on(self, *keys: str | bytes | Event):
        def decorate(fn: Callable):
            for k in keys:
                match k:
                    case str():
                        k = StrKey(k)
                    case bytes():
                        k = BytesKey(k)
                    case _:
                        k = k
                self.methods[k] = fn.__name__
            return fn

        return decorate

    def default(self, fn: Callable):
        self.defaultfn = fn.__name__
        return fn

    def build(self, widget: WidgetType):
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
