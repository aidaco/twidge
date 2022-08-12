from pathlib import Path

import numpy
import pandas
import typer

from . import echoers, editors, searchers

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
    searchers.searchdf(df)


@cli.command()
def echo(fmt: str = "str"):
    """fmt can be 'str' or 'bytes'."""
    match fmt:
        case "bytes":
            echoers.echobytes()
        case "str":
            echoers.echostr()


@cli.command()
def edit(content: str = typer.Argument("")):
    print(editors.editstr(content))


@cli.command()
def editdict(labels: str):
    print(editors.editdict(labels.split(",")))


if __name__ == "__main__":
    cli()
