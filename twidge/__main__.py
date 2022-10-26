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
    widgets.SearchDataFrame(df).run()


@cli.command()
def echo():
    widgets.Echo().run()


@cli.command()
def edit(content: str = typer.Argument("")):
    print(widgets.EditStr(content).run())


@cli.command()
def editdict(labels: str):
    print(widgets.editdict.run(labels.split(",")))


@cli.command()
def filterlist(options: str):
    print(widgets.SearchList(options.split(","))))


@cli.command()
def retrievelist(options: str):
    print(widgets.SelectList(options.split(",")).run())


if __name__ == "__main__":
    cli()
