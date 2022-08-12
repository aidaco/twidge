#! /usr/bin/env python
import shutil
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

cli = typer.Typer()
HERE = Path()
SUBPACKAGES = [p for p in HERE.iterdir() if p.is_dir() and (p / "__init__.py").exists()]
MODULES = [p for p in HERE.glob("*.py")]


def sh(*parts: str | Any):
    global console
    sp = list(map(str, parts))
    console.rule(" ".join(sp))
    subprocess.run(sp, capture_output=False)


@cli.command()
def clean(
    pycache: bool = True, mypycache: bool = True, ipynb: bool = True, dist: bool = True
):
    flagged: list[tuple[bool, str]] = [
        (pycache, "**/__pycache__"),
        (mypycache, "**/.mypy_cache"),
        (ipynb, "**/.ipynb_checkpoints"),
        (dist, "dist"),
    ]
    global console
    paths = []
    for flag, path in flagged:
        for match in HERE.glob(path):
            shutil.rmtree(match, ignore_errors=True)
            paths.append(match)
    if paths:
        console.print("Removed: ", " ".join(map(str, paths)))


@cli.command()
def fix(fmt: bool = True, isort: bool = True):
    global console
    for path in [*MODULES, *SUBPACKAGES]:
        if fmt:
            sh("python", "-m", "black", "--target-version", "py310", path)
        if isort:
            sh("python", "-m", "isort", "--profile", "black", path)


@cli.command()
def check(type_check: bool = True, lint: bool = True):
    global console
    for path in [*MODULES, *SUBPACKAGES]:
        if type_check:
            sh("python", "-m", "mypy", path)
        if lint:
            sh("python", "-m", "flake8", path)


if __name__ == "__main__":
    console = Console()
    cli()
