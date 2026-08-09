"""The Typer application object and the constants every command shares.

Split out so command modules can import ``app`` without importing each other.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer
from rich.console import Console

_H_SCHEDULER = "Scheduler backend: local | slurm | pbs | lsf"
_H_JOB_ID = "Molq job ID (UUID)"
_H_CLUSTER = "Cluster namespace (default: profile cluster_name or cli_<scheduler>)"
_H_PROFILE = "Named profile from config.yaml"
_H_CONFIG = "Path to config.yaml (default via molcfg / ~/.molcrafts/molq/…)"
_H_ALL_TERMINAL = "Include finished jobs (succeeded / failed / cancelled / …)"

_APP_HELP = """\
Unified job queue for [bold]local[/] execution and HPC ([bold]SLURM[/], [bold]PBS[/], [bold]LSF[/]).

[bold]Jobs[/]       submit · list · status · logs · watch · cancel · inspect
[bold]History[/]    history · cleanup
[bold]Live[/]       monitor · daemon
[bold]Setup[/]      clusters · workspace · plugins

Most job commands take a [cyan]SCHEDULER[/] argument and optional \
[cyan]--cluster[/] / [cyan]--profile[/] / [cyan]--config[/].
"""

app = typer.Typer(
    name="molq",
    help=_APP_HELP,
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

console = Console(stderr=True)


def _version_callback(requested: bool) -> None:
    if not requested:
        return
    from importlib.metadata import PackageNotFoundError, version

    try:
        print(version("molcrafts-molq"))
    except PackageNotFoundError:  # running from a source tree, not installed
        print("unknown")
    raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show the installed molq version and exit.",
        ),
    ] = False,
) -> None:
    """Root callback — exists so ``molq --version`` works before any command."""


class SchedulerType(StrEnum):
    local = "local"
    slurm = "slurm"
    pbs = "pbs"
    lsf = "lsf"
