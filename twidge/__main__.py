import typer

from .widgets import (
    Closeable,
    Echo,
    EditString,
    Form,
    Framed,
    Indexer,
    Searcher,
    Selector,
)

cli = typer.Typer()


@cli.command()
def echo():
    Closeable(Framed(Echo())).run()


@cli.command()
def edit(content: str = typer.Argument("")):
    print(Closeable(Framed(EditString(content))).run())


@cli.command()
def form(labels: str):
    print(Closeable(Framed(Form(labels.split(",")))).run())


@cli.command()
def filter(options: str):
    print(Closeable(Framed(Searcher(options.split(",")))).run())


@cli.command()
def index(options: str):
    print(Closeable(Framed(Indexer(options.split(",")))).run())


@cli.command()
def select(options: str):
    print(Closeable(Framed(Selector(options.split(",")))).run())


if __name__ == "__main__":
    cli()
