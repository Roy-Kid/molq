"""Job commands: submit, list, status, logs, watch, cancel, inspect."""

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
    _H_JOB_ID,
    _H_PROFILE,
    _H_SCHEDULER,
    SchedulerType,
    app,
    console,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------


@app.command()
def submit(
    scheduler: Annotated[SchedulerType, typer.Argument(help=_H_SCHEDULER)],
    command: Annotated[
        list[str] | None,
        typer.Argument(help="Command and arguments to run (argv form)"),
    ] = None,
    cpu_count: Annotated[
        int | None, typer.Option("--cpus", help="CPU cores to request")
    ] = None,
    memory: Annotated[
        str | None,
        typer.Option("--mem", help="Memory request, e.g. 8G or 512M"),
    ] = None,
    time_limit: Annotated[
        str | None,
        typer.Option("--time", help="Wall-time limit, e.g. 4h, 2h30m, 04:00:00"),
    ] = None,
    partition: Annotated[
        str | None,
        typer.Option(
            "--partition",
            help="Partition / queue (SLURM partition, PBS/LSF queue)",
        ),
    ] = None,
    queue: Annotated[
        str | None,
        typer.Option("--queue", help="Deprecated alias for --partition", hidden=True),
    ] = None,
    gpu_count: Annotated[
        int | None, typer.Option("--gpus", help="GPU count to request")
    ] = None,
    gpu_type: Annotated[
        str | None, typer.Option(help="GPU type string for the scheduler")
    ] = None,
    job_name: Annotated[
        str | None, typer.Option("--name", help="Job name shown in the scheduler")
    ] = None,
    workdir: Annotated[
        str | None, typer.Option(help="Working directory for the job")
    ] = None,
    account: Annotated[
        str | None, typer.Option(help="Billing / accounting account")
    ] = None,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    retries: Annotated[
        int | None,
        typer.Option("--retries", help="Max total attempts (1 = no retry)"),
    ] = None,
    retry_on_exit_code: Annotated[
        list[int] | None,
        typer.Option(
            "--retry-on-exit-code",
            help="Only retry when exit code matches (repeatable)",
        ),
    ] = None,
    after: Annotated[
        list[str] | None,
        typer.Option(
            "--after",
            help="Run after molq job(s) reach any terminal state (repeatable)",
        ),
    ] = None,
    after_started: Annotated[
        list[str] | None,
        typer.Option(
            "--after-started",
            help="Run after molq job(s) start running (repeatable)",
        ),
    ] = None,
    after_failure: Annotated[
        list[str] | None,
        typer.Option(
            "--after-failure",
            help="Run after molq job(s) fail / cancel / time out (repeatable)",
        ),
    ] = None,
    after_success: Annotated[
        list[str] | None,
        typer.Option(
            "--after-success",
            help="Run after molq job(s) succeed (repeatable)",
        ),
    ] = None,
    block: Annotated[
        bool,
        typer.Option(help="Block until the job reaches a terminal state"),
    ] = False,
) -> None:
    """Submit a job.

    Examples:

      molq submit local echo hello

      molq submit slurm --cpus 8 --mem 32G --time 4h python train.py

      molq submit slurm --after-success $JOB1 python eval.py
    """
    from molq import (
        Duration,
        JobExecution,
        JobResources,
        JobScheduling,
        Memory,
        RetryPolicy,
    )

    cmd: list[str] = list(command) if command else []
    if not cmd:
        console.print("[red]Error: No command provided.[/]")
        raise typer.Exit(1)

    # Build resource specs
    resources = JobResources(
        cpu_count=cpu_count,
        memory=Memory.parse(memory) if memory else None,
        gpu_count=gpu_count,
        gpu_type=gpu_type,
        time_limit=Duration.parse(time_limit) if time_limit else None,
    )
    if partition is not None and queue is not None:
        console.print("[red]Error: pass --partition or --queue, not both.[/]")
        raise typer.Exit(1)
    if queue is not None and partition is None:
        console.print("[yellow]Warning: --queue is deprecated; use --partition.[/]")
        partition = queue
    scheduling = JobScheduling(partition=partition, account=account)
    execution = JobExecution(cwd=workdir, job_name=job_name)
    retry_policy = None
    if retries is not None:
        retry_policy = RetryPolicy(
            max_attempts=retries,
            retry_on_exit_codes=(
                None
                if not retry_on_exit_code
                else tuple(int(code) for code in retry_on_exit_code)
            ),
        )

    try:
        with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
            handle = submitor.submit_job(
                argv=cmd,
                resources=resources,
                scheduling=scheduling,
                execution=execution,
                retry=retry_policy,
                after_started=after_started,
                after=after,
                after_failure=after_failure,
                after_success=after_success,
            )

            rprint("[green]Job submitted[/]")
            rprint(f"  ID:        {handle.job_id}")
            rprint(f"  Scheduler: {scheduler.value}")
            rprint(f"  Command:   {' '.join(cmd)}")

            if block:
                record = handle.wait()
                rprint(f"  Status:    {record.state.value}")
            else:
                rprint("  Status:    submitted")

    except Exception as e:
        console.print(f"[red]Submission failed: {e}[/]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_jobs(
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    all: Annotated[bool, typer.Option("--all", help=_H_ALL_TERMINAL)] = False,
) -> None:
    """List jobs in this cluster namespace (active only unless --all)."""
    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        submitor.refresh_jobs()
        records = submitor.list_jobs(include_terminal=all)

    if not records:
        rprint("[dim]No jobs found.[/]")
        return

    table = Table(title="Jobs")
    table.add_column("Job ID", style="cyan", max_width=36)
    table.add_column("State", style="bold")
    table.add_column("Type")
    table.add_column("Command", max_width=40)

    for r in records:
        style = _helpers.state_style(r.state.value)
        state_value = f"[{style}]{r.state.value}[/{style}]" if style else r.state.value
        table.add_row(
            r.job_id[:12] + "...",
            state_value,
            r.command_type,
            r.command_display[:40],
        )

    rprint(table)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command()
def status(
    job_id: Annotated[str, typer.Argument(help=_H_JOB_ID)],
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
) -> None:
    """Show current state of one job (refreshes from the scheduler first)."""
    from molq import JobNotFoundError

    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        submitor.refresh_jobs()
        try:
            record = submitor.get_job(job_id)
        except JobNotFoundError:
            rprint(f"[yellow]Job {job_id} not found[/]")
            raise typer.Exit(1)

    rprint(f"Job {record.job_id}:")
    rprint(f"  State:   [bold]{record.state.value}[/]")
    rprint(f"  Type:    {record.command_type}")
    rprint(f"  Command: {record.command_display}")
    if record.exit_code is not None:
        rprint(f"  Exit:    {record.exit_code}")
    if record.failure_reason:
        rprint(f"  Reason:  {record.failure_reason}")


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------


@app.command()
def logs(
    job_id: Annotated[str, typer.Argument(help=_H_JOB_ID)],
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    stream: Annotated[
        str,
        typer.Option(
            "--stream",
            help="Log stream: stdout | stderr | both",
        ),
    ] = "stdout",
    tail: Annotated[
        int | None,
        typer.Option("--tail", help="Show only the last N lines"),
    ] = None,
    follow: Annotated[
        bool,
        typer.Option(
            "--follow",
            "-f",
            help="Follow the log until the job finishes (like tail -f)",
        ),
    ] = False,
) -> None:
    """Print job stdout/stderr logs."""
    from molq import JobNotFoundError

    stream_name = stream.lower()
    if stream_name not in {"stdout", "stderr", "both"}:
        console.print("[red]--stream must be one of: stdout, stderr, both[/]")
        raise typer.Exit(1)

    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        submitor.refresh_jobs()
        try:
            record = submitor.get_job(job_id)
        except JobNotFoundError:
            rprint(f"[yellow]Job {job_id} not found[/]")
            raise typer.Exit(1)
        try:
            if follow:
                _helpers.follow_logs(submitor, job_id, stream_name, tail)
            else:
                paths = _helpers.log_paths(submitor, record, stream_name)
                labeled = stream_name == "both"
                emitted = False
                for name, path in paths.items():
                    content = _helpers.read_log(submitor, path, tail)
                    if content:
                        emitted = True
                        _helpers.emit_log_text(name, content, labeled=labeled)
                if not emitted:
                    rprint(f"[dim]{stream_name} log is empty[/]")
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1)


# ---------------------------------------------------------------------------
# watch
# ---------------------------------------------------------------------------


@app.command()
def watch(
    job_id: Annotated[str | None, typer.Argument(help=_H_JOB_ID)] = None,
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    timeout: Annotated[
        float | None,
        typer.Option(help="Give up after this many seconds"),
    ] = None,
    all_jobs: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Watch every active job in this namespace",
        ),
    ] = False,
) -> None:
    """Block until a job finishes (or all active jobs with --all)."""
    from molq import JobNotFoundError
    from molq.errors import MolqTimeoutError

    if all_jobs and job_id is not None:
        console.print("[red]Cannot combine --all with a job ID[/]")
        raise typer.Exit(1)
    if not all_jobs and job_id is None:
        console.print("[red]Provide a job ID or use --all[/]")
        raise typer.Exit(1)

    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        if all_jobs:
            submitor.refresh_jobs()
            active = [r for r in submitor.list_jobs(include_terminal=False)]
            if not active:
                rprint("[dim]No active jobs.[/]")
                return
            rprint(f"[dim]Watching {len(active)} active job(s)…[/]")
            try:
                records = submitor.watch_jobs(None, timeout=timeout)
            except MolqTimeoutError:
                console.print("[red]Timeout waiting for jobs[/]")
                raise typer.Exit(1)
            except KeyboardInterrupt:
                rprint("[dim]Interrupted[/]")
                return

            watched_ids = {r.job_id for r in active}
            table = Table(title="Watched Jobs")
            table.add_column("Job ID", style="cyan", max_width=36)
            table.add_column("State", style="bold")
            table.add_column("Exit")
            table.add_column("Command", max_width=40)
            for r in records:
                if r.job_id not in watched_ids:
                    continue
                style = _helpers.state_style(r.state.value)
                state_value = (
                    f"[{style}]{r.state.value}[/{style}]" if style else r.state.value
                )
                table.add_row(
                    r.job_id[:12] + "...",
                    state_value,
                    "-" if r.exit_code is None else str(r.exit_code),
                    r.command_display[:40],
                )
            rprint(table)
            return

        # Narrowed by the guards at the top of the function:
        # if not all_jobs and job_id is None we already exited.
        assert job_id is not None
        try:
            record = submitor.get_job(job_id)
        except JobNotFoundError:
            rprint(f"[yellow]Job {job_id} not found[/]")
            raise typer.Exit(1)

        if record.state.is_terminal:
            rprint(f"Job {job_id}: [bold]{record.state.value}[/]")
            return

        try:
            handle_record = submitor._monitor_instance.wait_one(job_id, timeout=timeout)
            rprint(f"Job {job_id}: [bold]{handle_record.state.value}[/]")
            if handle_record.exit_code is not None:
                rprint(f"  Exit code: {handle_record.exit_code}")
        except MolqTimeoutError:
            console.print(f"[red]Timeout waiting for job {job_id}[/]")
            raise typer.Exit(1)
        except KeyboardInterrupt:
            rprint("[dim]Interrupted[/]")


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


@app.command()
def cancel(
    job_id: Annotated[str, typer.Argument(help=_H_JOB_ID)],
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
) -> None:
    """Cancel a job on the scheduler and mark it cancelled in the store."""
    from molq import JobNotFoundError

    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        try:
            submitor.cancel_job(job_id)
            rprint(f"[green]Job {job_id} cancelled[/]")
        except JobNotFoundError:
            rprint(f"[yellow]Job {job_id} not found[/]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Cancel failed: {e}[/]")
            raise typer.Exit(1)


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


@app.command()
def inspect(
    job_id: Annotated[str, typer.Argument(help=_H_JOB_ID)],
    scheduler: Annotated[
        SchedulerType, typer.Argument(help=_H_SCHEDULER)
    ] = SchedulerType.local,
    cluster: Annotated[str | None, typer.Option(help=_H_CLUSTER)] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
) -> None:
    """Full job record: metadata, dependencies, and state transition timeline."""
    from molq import JobNotFoundError

    with _helpers.open_submitor(scheduler, cluster, profile, config) as submitor:
        submitor.refresh_jobs()
        try:
            record = submitor.get_job(job_id)
            transitions = submitor.get_transitions(job_id)
            family = submitor.get_retry_family(job_id)
            dependencies = submitor.get_dependencies(job_id)
            dependents = submitor.get_dependents(job_id)
            upstream_lines: list[str] = []
            downstream_lines: list[str] = []
            for dependency in dependencies:
                dep_record = submitor.get_job(dependency.dependency_job_id)
                relation_state = _helpers.dependency_relation_state(
                    dependency.dependency_type, dep_record
                )
                upstream_lines.append(
                    f"      {_helpers.dependency_marker(relation_state)} "
                    f"{dependency.dependency_job_id}  {dependency.dependency_type}  "
                    f"{dep_record.state.value}  scheduler={dependency.scheduler_dependency}"
                )
            for dependent in dependents:
                dependent_record = submitor.get_job(dependent.job_id)
                relation_state = _helpers.dependency_relation_state(
                    dependent.dependency_type, record
                )
                downstream_lines.append(
                    f"      {_helpers.dependency_marker(relation_state)} "
                    f"{dependent.job_id}  {dependent.dependency_type}  "
                    f"{dependent_record.state.value}"
                )
        except JobNotFoundError:
            rprint(f"[yellow]Job {job_id} not found[/]")
            raise typer.Exit(1)

    rprint(f"Job {record.job_id}:")
    rprint(f"  Cluster:        {record.cluster_name}")
    rprint(f"  Scheduler:      {record.scheduler}")
    rprint(f"  Root Job ID:    {record.root_job_id}")
    rprint(f"  Attempt:        {record.attempt}")
    rprint(f"  Previous:       {record.previous_attempt_job_id or '-'}")
    rprint(f"  Scheduler ID:   {record.scheduler_job_id or '-'}")
    rprint(f"  State:          [bold]{record.state.value}[/]")
    rprint(f"  Command:        {record.command_display}")
    rprint(f"  Command Type:   {record.command_type}")
    rprint(f"  Working Dir:    {record.cwd}")
    rprint(f"  Submitted At:   {_helpers.format_timestamp(record.submitted_at)}")
    rprint(f"  Started At:     {_helpers.format_timestamp(record.started_at)}")
    rprint(f"  Finished At:    {_helpers.format_timestamp(record.finished_at)}")
    rprint(
        f"  Exit Code:      {record.exit_code if record.exit_code is not None else '-'}"
    )
    rprint(f"  Failure:        {record.failure_reason or '-'}")
    rprint(f"  Job Dir:        {record.metadata.get('molq.job_dir', '-')}")
    rprint(f"  Stdout:         {record.metadata.get('molq.stdout_path', '-')}")
    rprint(f"  Stderr:         {record.metadata.get('molq.stderr_path', '-')}")
    rprint(f"  Profile:        {record.profile_name or '-'}")

    rprint("  Retry Family:")
    for member in family:
        rprint(
            f"    attempt {member.attempt}: {member.job_id} "
            f"[bold]{member.state.value}[/]"
        )

    rprint("  Dependencies:")
    if dependencies:
        rprint("    Upstream:")
        for line in upstream_lines:
            rprint(line)
    else:
        rprint("    Upstream: -")

    if dependents:
        rprint("    Downstream:")
        for line in downstream_lines:
            rprint(line)
    else:
        rprint("    Downstream: -")

    rprint("  Timeline:")
    for transition in transitions:
        old_state = transition.old_state.value if transition.old_state else "-"
        reason = f" ({transition.reason})" if transition.reason else ""
        rprint(
            f"    {_helpers.format_timestamp(transition.timestamp)}  "
            f"{old_state} -> {transition.new_state.value}{reason}"
        )
