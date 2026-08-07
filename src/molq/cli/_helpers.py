"""Helpers shared by the molq command modules.

Commands reach these through the module (``_helpers.open_submitor(...)``)
rather than importing the names directly, so tests have one stable patch
target regardless of which command module they exercise.
"""

from __future__ import annotations

import shlex
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

import typer

from molq.cli._app import SchedulerType

if TYPE_CHECKING:
    from molq import Cluster, JobRecord, Submitor


def is_ssh_alias(name: str, ssh_config: str | None = None) -> bool:
    """True when *name* is a ``Host`` alias the user declared in ssh config.

    Deliberately parse-based rather than ``ssh -G``-based: ``ssh -G`` prints a
    resolved config block for *any* string, so it can never tell a real
    destination from a typo or from molq's own ``cli_<scheduler>`` namespace.
    """
    from molq.ssh_config import ssh_alias_names

    try:
        return name in set(ssh_alias_names(ssh_config))
    except OSError:
        return False


def resolve_target(
    scheduler: SchedulerType,
    cluster_name: str,
    *,
    ssh_requested: bool,
) -> Cluster:
    """Build the destination Cluster for a job command.

    SSH is used only when the caller explicitly named a cluster *and* that
    name is a configured ``Host`` alias.  Everything else — including the
    default ``cli_<scheduler>`` namespace — runs on this host.
    """
    from molq import Cluster

    if ssh_requested and is_ssh_alias(cluster_name):
        try:
            return Cluster.from_ssh_alias(cluster_name, scheduler=scheduler.value)
        except OSError as exc:
            # The alias is real but OpenSSH is unusable (no client on PATH).
            # Say so instead of silently running the job on the wrong machine.
            raise typer.BadParameter(
                f"{cluster_name!r} is an SSH alias but it cannot be resolved: {exc}"
            ) from exc
    return Cluster(cluster_name, scheduler.value)


@contextmanager
def open_submitor(
    scheduler: SchedulerType,
    cluster: str | None = None,
    profile: str | None = None,
    config_path: str | None = None,
    *,
    default_plugins: list[str] | None = None,
) -> Iterator[Submitor]:
    """Open a Submitor for the CLI and guarantee its connection is closed.

    Args:
        default_plugins: Official plugins to enable when config has no
            ``[plugins]`` section (e.g. daemon defaults to ``["nerve"]``).
    """
    from molq import Cluster, Submitor
    from molq.config import enabled_plugin_names, load_config, load_profile

    cfg = load_config(config_path)
    plugin_names = enabled_plugin_names(cfg.plugins, default_official=default_plugins)
    plugin_configs = cfg.plugins

    if profile:
        loaded = load_profile(profile, config_path)
        if loaded.scheduler != scheduler.value:
            raise typer.BadParameter(
                f"profile {profile!r} uses scheduler {loaded.scheduler!r}, "
                f"not {scheduler.value!r}"
            )
        cluster_name = cluster or loaded.cluster_name
        target = Cluster(
            cluster_name,
            scheduler.value,
            host=loaded.host,
            scheduler_options=loaded.scheduler_options,
        )
        submitor = Submitor(
            target,
            defaults=loaded.defaults,
            jobs_dir=loaded.jobs_dir,
            default_retry_policy=loaded.retry,
            retention_policy=loaded.retention,
            profile_name=loaded.name,
            plugins=plugin_names or None,
            plugin_configs=plugin_configs or None,
        )
    else:
        cluster_name = cluster or f"cli_{scheduler.value}"
        target = resolve_target(
            scheduler, cluster_name, ssh_requested=cluster is not None
        )
        submitor = Submitor(
            target=target,
            plugins=plugin_names or None,
            plugin_configs=plugin_configs or None,
        )
    try:
        yield submitor
    finally:
        submitor.close()


def format_timestamp(value: float | None) -> str:
    if value is None:
        return "-"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def state_style(state: str) -> str:
    return {
        "running": "green",
        "succeeded": "green",
        "failed": "red",
        "cancelled": "yellow",
        "timed_out": "yellow",
        "lost": "red",
        "queued": "cyan",
        "submitted": "cyan",
    }.get(state, "")


def log_paths(
    submitor: Submitor, record: JobRecord, stream_name: str
) -> dict[str, str]:
    """Resolve stream name -> log path *on the cluster's filesystem*.

    Log paths recorded in job metadata live wherever the job ran, so
    existence is checked through the transport rather than with a local
    ``Path.exists()`` — otherwise every remote job reports a missing log.
    """
    stream_keys = {
        "stdout": "molq.stdout_path",
        "stderr": "molq.stderr_path",
    }
    wanted = ("stdout", "stderr") if stream_name == "both" else (stream_name,)
    transport = submitor.target.transport
    result: dict[str, str] = {}
    for key in wanted:
        value = record.metadata.get(stream_keys[key])
        if not value:
            raise FileNotFoundError(f"No {key} log is recorded for job {record.job_id}")
        if not transport.exists(value):
            raise FileNotFoundError(f"{key} log does not exist: {value}")
        result[key] = value
    return result


def emit_log_text(stream_name: str, text: str, *, labeled: bool) -> None:
    if not text:
        return
    if not labeled:
        sys.stdout.write(text)
        sys.stdout.flush()
        return
    for chunk in text.splitlines(keepends=True):
        sys.stdout.write(f"[{stream_name}] {chunk}")
    sys.stdout.flush()


def read_log(submitor: Submitor, path: str, tail: int | None) -> str:
    """Read a log through the transport, optionally only its last *tail* lines."""
    transport = submitor.target.transport
    if tail is None:
        return transport.read_bytes(path).decode("utf-8", errors="replace")
    # Let the far side do the tailing so a multi-gigabyte log does not cross
    # the network just to show 50 lines.
    result = transport.run(
        ["sh", "-c", f"tail -n {int(tail)} {shlex.quote(path)} 2>/dev/null || true"]
    )
    return result.stdout


def read_log_from(submitor: Submitor, path: str, offset: int) -> str:
    """Return log bytes past *offset* (1-based for ``tail -c``)."""
    result = submitor.target.transport.run(
        ["sh", "-c", f"tail -c +{offset + 1} {shlex.quote(path)} 2>/dev/null || true"]
    )
    return result.stdout


def follow_poll_interval(submitor: Submitor) -> float:
    """Poll faster locally than over the network."""
    from molq.transport import LocalTransport

    return 0.2 if isinstance(submitor.target.transport, LocalTransport) else 1.0


def follow_logs(
    submitor: Submitor, job_id: str, stream_name: str, tail: int | None
) -> None:
    record = submitor.get_job(job_id)
    paths = log_paths(submitor, record, stream_name)
    labeled = stream_name == "both"
    interval = follow_poll_interval(submitor)

    # Byte offsets rather than open file handles: a remote log has no local
    # descriptor to seek, and `tail -c +N` transfers only the new bytes.
    offsets: dict[str, int] = {}
    for name, path in paths.items():
        initial = read_log(submitor, path, tail)
        emit_log_text(name, initial, labeled=labeled)
        offsets[name] = submitor.target.transport.getsize(path)

    while True:
        emitted = False
        for name, path in paths.items():
            chunk = read_log_from(submitor, path, offsets[name])
            if chunk:
                emitted = True
                offsets[name] += len(chunk.encode("utf-8"))
                emit_log_text(name, chunk, labeled=labeled)

        record = submitor.get_job(job_id)
        if record.state.is_terminal and not emitted:
            break

        submitor.refresh_jobs()
        time.sleep(interval)


def dependency_relation_state(dependency_type: str, record: JobRecord) -> str:
    from molq.store import dependency_relation_state

    return dependency_relation_state(dependency_type, record.state, record.started_at)


def dependency_marker(relation_state: str) -> str:
    return {"satisfied": "✓", "pending": "·", "impossible": "!"}.get(
        relation_state, "·"
    )
