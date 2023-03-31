import pytest

from twidge.widgets.base import (
    Button,
    Echo,
    EchoBytes,
    Indexer,
    Searcher,
    Selector,
    Toggle,
)
from twidge.widgets.editors import EditFloatString, EditString


def test_echo():
    e = Echo()
    for k in "hello":
        e.dispatch(k)
    assert e.__rich__() == "hello"


def test_echobytes():
    e = EchoBytes()
    for k in [b"h", b"e", b"l", b"l", b"o"]:
        e.dispatch(k)
    assert e.__rich__() == "b'hello'"


def test_toggle():
    t = Toggle()
    t.dispatch("space")
    assert t.__rich__() == "False"
    t.dispatch("enter")
    assert t.__rich__() == "False"
    t.dispatch("space")
    assert t.__rich__() == "True"


def test_button():
    flag = False

    def mark():
        nonlocal flag
        flag = True

    b = Button("hello", mark)
    assert not flag
    assert b.__rich__() == "hello"
    b.dispatch("enter")
    assert flag


def test_searcher():
    opts = ["aa", "ab", "bb", "a", "c"]
    s = Searcher(opts)
    s.dispatch("a")
    assert s.result == ["aa", "ab", "a"]
    s.dispatch("a")
    assert s.result == ["aa"]
    s.dispatch("ctrl+d")
    assert s.result == opts


def test_indexer():
    opts = ["a", "b", "c", "d", "e", "f"]
    i = Indexer(opts)
    i.dispatch("3")
    i.dispatch(" ")
    i.dispatch("1")
    assert i.result == ["c", "a"]


def test_selector():
    opts = ["a", "b", "c", "d", "e", "f"]
    s = Selector(opts)
    s.dispatch("tab")
    s.dispatch("space")
    s.dispatch("shift+tab")
    s.dispatch("shift+tab")
    s.dispatch("enter")
    assert s.result == ["b", "f"]


def test_editstring():
    content = "hello world"
    e = EditString(content)
    e.dispatch("end")
    e.dispatch("backspace")
    assert e.result == content[:-1]
    e.dispatch("ctrl+h")
    assert e.result == "hello"
    e.dispatch("\n")
    assert e.result == "hello\n"
    e.dispatch("right")
    assert e.result == "hello\n"


def test_editfloatstring():
    e = EditFloatString()
    e.dispatch("1")
    assert e.result == 1.0
    e.dispatch(".")
    assert e.result == 1.0
    e.dispatch("a")
    with pytest.raises(ValueError):
        e.result
    e.dispatch("backspace")
    e.dispatch("5")
    assert e.result == 1.5
