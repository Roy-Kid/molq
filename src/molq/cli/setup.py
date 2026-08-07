"""Setup commands: cluster discovery, workspace sync, plugin listing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer
from rich import print as rprint
from rich.table import Table

from molq.cli import _helpers
from molq.cli._app import (
    _H_CONFIG,
    _H_PROFILE,
    app,
    console,
)

if TYPE_CHECKING:
    from molq import Cluster


# ---------------------------------------------------------------------------
# clusters — discovery from ~/.ssh/config + molq config profiles
# ---------------------------------------------------------------------------


clusters_app = typer.Typer(
    name="clusters",
    help="Discover destinations from profiles and ~/.ssh/config.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(clusters_app, name="clusters")


def _profile_destinations(config_path: str | None) -> list[dict[str, str]]:
    from molq import load_config

    rows: list[dict[str, str]] = []
    cfg = load_config(config_path)
    for profile in cfg.profiles.values():
        rows.append(
            {
                "name": profile.cluster_name,
                "source": f"profile:{profile.name}",
                "scheduler": profile.scheduler,
                "target": profile.host or "(local)",
            }
        )
    return rows


def _ssh_destinations(ssh_config: str | None) -> list[dict[str, str]]:
    from molq import list_ssh_hosts

    rows: list[dict[str, str]] = []
    for host in list_ssh_hosts(ssh_config):
        rows.append(
            {
                "name": host.alias,
                "source": "ssh_config",
                "scheduler": "?",
                "target": host.target,
            }
        )
    return rows


@clusters_app.command("list")
def clusters_list(
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    ssh_config: Annotated[
        str | None,
        typer.Option(
            help="Path to OpenSSH config (default: ~/.ssh/config)",
        ),
    ] = None,
) -> None:
    """List known clusters (molq profiles + SSH Host aliases)."""
    profile_rows = _profile_destinations(config)
    ssh_rows = _ssh_destinations(ssh_config)

    if not profile_rows and not ssh_rows:
        rprint("[dim]No clusters discovered.[/]")
        return

    table = Table(title="Clusters")
    table.add_column("Name", style="cyan")
    table.add_column("Source")
    table.add_column("Scheduler")
    table.add_column("Target")
    for row in profile_rows + ssh_rows:
        table.add_row(row["name"], row["source"], row["scheduler"], row["target"])
    rprint(table)


@clusters_app.command("show")
def clusters_show(
    name: Annotated[
        str,
        typer.Argument(help="Profile name, cluster_name, or SSH Host alias"),
    ],
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    ssh_config: Annotated[
        str | None,
        typer.Option(
            help="Path to OpenSSH config (default: ~/.ssh/config)",
        ),
    ] = None,
) -> None:
    """Show profile or SSH settings for one cluster name."""
    from molq import load_config, resolve_ssh_host

    cfg = load_config(config)
    profile = next(
        (p for p in cfg.profiles.values() if p.name == name or p.cluster_name == name),
        None,
    )
    if profile is not None:
        rprint(f"[bold]Profile:[/] {profile.name}")
        rprint(f"  Cluster:   {profile.cluster_name}")
        rprint(f"  Scheduler: {profile.scheduler}")
        rprint(f"  Host:      {profile.host or '(local)'}")
        if profile.scheduler_options is not None:
            rprint(f"  Options:   {profile.scheduler_options}")
        if profile.jobs_dir:
            rprint(f"  Jobs dir:  {profile.jobs_dir}")
        return

    try:
        host = resolve_ssh_host(name)
    except OSError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    rprint(f"[bold]SSH alias:[/] {host.alias}")
    rprint(f"  Hostname:      {host.hostname or '-'}")
    rprint(f"  User:          {host.user or '-'}")
    rprint(f"  Port:          {host.port or 22}")
    rprint(f"  IdentityFile:  {host.identity_file or '-'}")
    if host.proxy_jump:
        rprint(f"  ProxyJump:     {host.proxy_jump}")
    if host.forward_agent:
        rprint("  ForwardAgent:  yes")


# ---------------------------------------------------------------------------
# workspace — remote file sync via rsync
# ---------------------------------------------------------------------------

workspace_app = typer.Typer(
    name="workspace",
    help="Sync files to/from a cluster workspace (rsync-backed).",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(workspace_app, name="workspace")


def _resolve_cluster(
    cluster: str | None,
    profile: str | None,
    config_path: str | None,
) -> Cluster:
    """Resolve a Cluster from --cluster (SSH alias) or --profile."""
    from molq import Cluster, load_profile
    from molq.ssh_config import ssh_alias_names

    if profile:
        loaded = load_profile(profile, config_path)
        return Cluster(
            loaded.cluster_name,
            loaded.scheduler,
            host=loaded.host,
            scheduler_options=loaded.scheduler_options,
        )
    if cluster:
        # --cluster on a workspace command means "the remote side", so an
        # unknown name is an error rather than a silent fall back to local:
        # syncing into a local directory you did not ask for is worse than
        # refusing.
        if not _helpers.is_ssh_alias(cluster):
            known = ssh_alias_names()
            hint = f" Known aliases: {', '.join(known)}." if known else ""
            raise typer.BadParameter(
                f"{cluster!r} is not a Host alias in ~/.ssh/config.{hint}"
            )
        return Cluster.from_ssh_alias(cluster)
    return Cluster("local", "local")


@workspace_app.command("sync")
def workspace_sync(
    local: Annotated[str, typer.Argument(help="Local file or directory")],
    cluster: Annotated[
        str | None, typer.Option(help="SSH Host alias or cluster name")
    ] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    path: Annotated[
        str,
        typer.Option("--path", "-p", help="Remote workspace path (default: .)"),
    ] = ".",
    pull: Annotated[
        bool,
        typer.Option(
            "--pull",
            help="Pull remote → local (default is push local → remote)",
        ),
    ] = False,
    delete: Annotated[
        bool,
        typer.Option("--delete", help="Delete dest files not present in source"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show transfer plan without copying",
        ),
    ] = False,
) -> None:
    """Sync files between local and remote via rsync.

    Default is push (local → remote). Use --pull for remote → local.

    Examples:

      molq workspace sync ./src --cluster dardel -p /cfs/.../runs

      molq workspace sync --pull ./results --cluster dardel -p /cfs/.../runs
    """
    from molq.workspace import Workspace

    target = _resolve_cluster(cluster, profile, config)
    remote = Workspace(cluster=target, name="sync", path=path)
    remote.ensure()

    if pull:
        if dry_run:
            rprint(f"[dim]Would pull {remote.path} → {local}[/]")
        else:
            remote.download("", local, recursive=True)
            rprint(f"[green]Pulled[/] {remote.path} → {local}")
    else:
        if dry_run:
            rprint(f"[dim]Would push {local} → {remote.path}[/]")
        else:
            remote.upload(local, recursive=True)
            rprint(f"[green]Pushed[/] {local} → {remote.path}")

    # TODO: wire --delete through transport when rsync --delete support is added


@workspace_app.command("list")
def workspace_list(
    cluster: Annotated[
        str | None, typer.Option(help="SSH Host alias or cluster name")
    ] = None,
    profile: Annotated[str | None, typer.Option(help=_H_PROFILE)] = None,
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
    path: Annotated[
        str,
        typer.Option("--path", "-p", help="Remote workspace path (default: .)"),
    ] = ".",
) -> None:
    """List files under a remote workspace path."""
    from molq.workspace import Workspace

    target = _resolve_cluster(cluster, profile, config)
    remote = Workspace(cluster=target, name="list", path=path)
    files = remote.list_files()
    if not files:
        rprint("[dim](empty)[/]")
        return
    for f in files:
        rprint(f"  {f}")


# ---------------------------------------------------------------------------
# plugins — official + third-party
# ---------------------------------------------------------------------------


plugins_app = typer.Typer(
    name="plugins",
    help="List molq plugins (official builtins and third-party entry points).",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(plugins_app, name="plugins")


@plugins_app.command("list")
def plugins_list(
    config: Annotated[str | None, typer.Option(help=_H_CONFIG)] = None,
) -> None:
    """Show available plugins and whether they are enabled in config."""
    from molq.config import enabled_plugin_names, load_config
    from molq.plugin import available_plugins

    cfg = load_config(config)
    available = available_plugins()
    enabled = set(enabled_plugin_names(cfg.plugins, default_official=None))
    # When config has no [plugins] at all, daemon still defaults nerve — note that.
    daemon_default = not cfg.plugins

    if not available:
        rprint("[dim]No plugins discovered.[/]")
        return

    table = Table(title="Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Source")
    table.add_column("Config")
    table.add_column("Notes")

    for name in sorted(available):
        source = available[name]
        pcfg = cfg.plugins.get(name, {})
        if name in enabled:
            state = "enabled"
        elif pcfg.get("enabled") is False:
            state = "disabled"
        elif daemon_default and name == "nerve":
            state = "default*"
        else:
            state = "off"
        note = ""
        if daemon_default and name == "nerve":
            note = "daemon enables when plugins table missing"
        elif source.startswith("builtin:"):
            note = "official (ships with molq)"
        elif source.startswith("entry_point:"):
            note = "third-party (pip entry point)"
        table.add_row(name, source.split(":", 1)[0], state, note)

    rprint(table)
    if daemon_default:
        rprint(
            "\n[dim]* default: molq daemon loads nerve when config has no "
            "plugins table. Set plugins.nerve.enabled = false to turn off.[/]"
        )
