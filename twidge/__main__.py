from pathlib import Path

import numpy
import pandas
import typer

from . import widgets

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
    widgets.searchdf.run(df)


@cli.command()
def echo():
    widgets.echo.run()


@cli.command()
def edit(content: str = typer.Argument("")):
    print(widgets.editstr.run(content).result())


@cli.command()
def editdict(labels: str):
    print(widgets.editdict.run(labels.split(",")).result())


@cli.command()
def filterlist(options: str):
    print(widgets.filterlist.run(options.split(",")).result())


@cli.command()
def retrievelist(options: str):
    print(widgets.retrievelist.run(options.split(",")).result())


if __name__ == "__main__":
    cli()
