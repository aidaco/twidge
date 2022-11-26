import subprocess
from rich.console import Console
from twidge.core import DispatchBuilder, RunBuilder, BytesReader


class echo:
    def __init__(self):
        self.history = ""

    def __rich__(self):
        return self.history

    run = RunBuilder()
    dispatch = DispatchBuilder()

    @dispatch.on("ctrl+c")
    def stop(self):
        self.run.stop()

    @dispatch.default
    def default(self, key: str):
        self.history += key


class echobytes:
    def __init__(self):
        self.history = b""

    def __rich__(self):
        return str(self.history)

    run = RunBuilder(reader=BytesReader)
    dispatch = DispatchBuilder()

    @dispatch.on(b"\x7f")
    def stop(self):
        self.run.stop()

    @dispatch.default
    def default(self, key: str):
        self.history += key


def test_echo():
    e = echo()
    for k in "hello":
        e.dispatch(k)
    assert e.__rich__() == "hello"


def test_echobytes():
    e = echobytes()
    for k in [b"h", b"e", b"l", b"l", b"o"]:
        e.dispatch(k)
    assert e.__rich__() == "b'hello'"
