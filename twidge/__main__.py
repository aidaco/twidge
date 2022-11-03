from pathlib import Path

import numpy
import pandas
import typer

from .widgets import (
    Close,
    DataFrameSearcher,
    Echo,
    EditString,
    Form,
    Framed,
    ListIndexer,
    ListSearcher,
)

cli = typer.Typer()


@cli.command()
def search(file: str):
    path = Path(file)
    if not path.exists() or path.is_dir():
        raise ValueError("Path must be an extant file.")

    match path.suffix:
        case ".csv":
            df = pandas.read_csv(path)
        case ".xls":
            df = pandas.read_excel(path)
    df = df.replace(numpy.nan, "-").astype(str)
    Close("ctrl+c", Framed(DataFrameSearcher(df))).run()


@cli.command()
def echo():
    Close("ctrl+c", Framed(Echo())).run()


@cli.command()
def edit(content: str = typer.Argument("")):
    print(Close("ctrl+c", Framed(EditString(content))).run())


@cli.command()
def form(labels: str):
    print(Close("ctrl+c", Framed(Form(labels.split(",")))).run())


@cli.command()
def filter(options: str):
    print(Close("ctrl+c", Framed(ListSearcher(options.split(",")))).run())


@cli.command()
def select(options: str):
    print(Close("ctrl+c", Framed(ListIndexer(options.split(",")))).run())


if __name__ == "__main__":
    cli()
