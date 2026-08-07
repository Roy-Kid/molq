"""History, retention, and long-running commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer
from rich import print as rprint
from rich.table import Table

from molq.cli import _helpers
from molq.cli._app import (
    _H_ALL_TERMINAL,
    _H_CLUSTER,
    _H_CONFIG,
    _H_PROFILE,
    _H_SCHEDULER,
    SchedulerType,
    app,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


@app.command()
def history(
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    all: Annotated[bool, typer.Option("--all", help=_H_ALL_TERMINAL)] = False,
) -> None:
    """Job history table (attempt, times, exit code) for this namespace."""
    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        submitor.refresh_jobs()
        records = submitor.list_jobs(include_terminal=all)

    if not records:
        rprint("[dim]No jobs found.[/]")
        return

    table = Table(title="History")
    table.add_column("Job ID", style="cyan", max_width=36)
    table.add_column("Attempt")
    table.add_column("State", style="bold")
    table.add_column("Scheduler ID")
    table.add_column("Submitted")
    table.add_column("Finished")
    table.add_column("Exit")
    table.add_column("Command", max_width=36)

    for record in records:
        style = _helpers.state_style(record.state.value)
        state_value = (
            f"[{style}]{record.state.value}[/{style}]" if style else record.state.value
        )
        table.add_row(
            record.job_id[:12] + "...",
            str(record.attempt),
            state_value,
            record.scheduler_job_id or "-",
            _helpers.format_timestamp(record.submitted_at),
            _helpers.format_timestamp(record.finished_at),
            "-" if record.exit_code is None else str(record.exit_code),
            record.command_display[:36],
        )

    rprint(table)


@app.command()
def cleanup(
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be removed without deleting",
        ),
    ] = False,
) -> None:
    """Delete old job directories and records per retention policy."""
    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        result = submitor.cleanup_jobs(dry_run=dry_run)
    rprint(f"Job dirs: {len(result['job_dirs'])}")
    rprint(f"Records:  {len(result['records'])}")
    for path in result["job_dirs"]:
        rprint(f"  dir: {path}")
    for job_id in result["records"]:
        rprint(f"  record: {job_id}")


# ---------------------------------------------------------------------------
# monitor
# ---------------------------------------------------------------------------


@app.command()
def monitor(
    all_jobs: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Include finished jobs in the dashboard",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max job rows to show"),
    ] = 200,
    refresh: Annotated[
        float,
        typer.Option("--refresh", "-r", help="Refresh interval in seconds"),
    ] = 2.0,
    db: Annotated[
        str | None,
        typer.Option(
            "--db",
            help="Path to jobs.db (default: molcfg project path under ~/.molcrafts)",
        ),
    ] = None,
) -> None:
    """Full-screen live dashboard for jobs across all clusters (press q to quit)."""
    from molq.dashboard import MolqMonitor

    rprint("[dim]Opening monitor… (press q to close)[/dim]")
    MolqMonitor(
        db_path=db,
        include_terminal=all_jobs,
        limit=limit,
        refresh_interval=refresh,
    ).watch()
    rprint("\n[dim]Monitor closed.[/dim]")


@app.command()
def daemon(
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    once: Annotated[
        bool,
        typer.Option("--once", help="Run a single reconcile cycle and exit"),
    ] = False,
    interval: Annotated[
        float,
        typer.Option("--interval", help="Seconds between reconcile cycles"),
    ] = 5.0,
    skip_cleanup: Annotated[
        bool,
        typer.Option(
            "--skip-cleanup",
            help="Do not run retention cleanup each cycle",
        ),
    ] = False,
) -> None:
    """Background reconcile loop: poll scheduler, update store, optional cleanup.

    Loads plugins from config table plugins.<name>. When that table is absent,
    enables the official nerve plugin so job status is pushed to the local
    Nerve menu-bar hub (fail-open if Nerve is not running).

    Disable with config:

      plugins.nerve.enabled = false
    """
    with _helpers.open_submitor(
        scheduler,
        cluster,
        profile,
        config,
        default_plugins=["nerve"],
    ) as submitor:
        try:
            submitor.run_daemon(
                once=once, interval=interval, run_cleanup=not skip_cleanup
            )
        except KeyboardInterrupt:
            rprint("[dim]Daemon interrupted[/]")
