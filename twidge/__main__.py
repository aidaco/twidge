from pathlib import Path

import numpy
import pandas
import typer

from .widgets import (
    Echo,
    EditStr,
    Escape,
    Form,
    Framed,
    SearchDataFrame,
    SearchList,
    SelectList,
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
    Escape(SearchDataFrame(df)).run()


@cli.command()
def echo():
    Escape(Framed(Echo())).run()


@cli.command()
def edit(content: str = typer.Argument("")):
    print(Escape(Framed(EditStr(content))).run())


@cli.command()
def form(labels: str):
    print(Escape(Framed(Form(labels.split(",")))).run())


@cli.command()
def filter(options: str):
    print(Escape(Framed(SearchList(options.split(",")))).run())


@cli.command()
def select(options: str):
    print(Escape(Framed(SelectList(options.split(",")))).run())


if __name__ == "__main__":
    cli()
