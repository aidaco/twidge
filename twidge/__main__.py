from pathlib import Path

import typer

from .widgets import (
    Close,
    Echo,
    EchoBytes,
    EditString,
    EditTemplate,
    Form,
    Framed,
    Indexer,
    Searcher,
    Selector,
)

cli = typer.Typer()


@cli.command()
def echo():
    Close(Framed(Echo())).run()


@cli.command()
def echobytes():
    Close(Framed(EchoBytes())).run()


@cli.command()
def edit(content: str = typer.Argument("")):
    print(Close(Framed(EditString(content))).run())


@cli.command()
def template(
    content: str = typer.Argument(""),
    path: Path = typer.Option(None),
    escape: bool = False,
):
    content = content or path.read_text()
    if escape:
        content = content.encode("utf-8").decode("unicode_escape")
    print(Close(Framed(EditTemplate(content))).run())


@cli.command()
def form(labels: str):
    print(Close(Framed(Form(labels.split(",")))).run())


@cli.command()
def filter(options: str):
    print(Close(Framed(Searcher(options.split(",")))).run())


@cli.command()
def index(options: str):
    print(Close(Framed(Indexer(options.split(",")))).run())


@cli.command()
def select(options: str):
    print(Close(Framed(Selector(options.split(",")))).run())


if __name__ == "__main__":
    cli()
