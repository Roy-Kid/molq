"""Profile and config loading for molq."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from molcfg import ConfigLoader, OneOf, YamlFileSource
from molcfg import ValidationError as CfgValidationError
from molcfg import validate as cfg_validate

from molq.errors import ConfigError
from molq.models import RetentionPolicy, RetryPolicy, SubmitorDefaults
from molq.options import (
    OPTIONS_TYPE_MAP,
    LocalSchedulerOptions,
    LSFSchedulerOptions,
    PBSSchedulerOptions,
    SchedulerOptions,
    SlurmSchedulerOptions,
)
from molq.serde import (
    deserialize_execution,
    deserialize_resources,
    deserialize_retention_policy,
    deserialize_retry_policy,
    deserialize_scheduling,
)


@dataclass(frozen=True)
class MolqProfile:
    """Named profile loaded from the molq config file (molcfg path)."""

    name: str
    scheduler: str
    cluster_name: str
    defaults: SubmitorDefaults = field(default_factory=SubmitorDefaults)
    scheduler_options: SchedulerOptions | None = None
    retry: RetryPolicy | None = None
    retention: RetentionPolicy = field(default_factory=RetentionPolicy)
    jobs_dir: str | None = None
    #: SSH destination for this profile — anything ``ssh`` accepts, including a
    #: ``~/.ssh/config`` alias.  ``None`` runs on the current host.
    host: str | None = None


@dataclass(frozen=True)
class MolqConfig:
    """Loaded molq configuration."""

    profiles: dict[str, MolqProfile]
    #: Plugin name → free-form config mapping (``[plugins.<name>]``).
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)


# Validation schema for a single profile section
class _ProfileSchema:
    scheduler: str
    cluster_name: str
    jobs_dir: str | None = None
    host: str | None = None
    __constraints__: dict = {"scheduler": [OneOf(*OPTIONS_TYPE_MAP.keys())]}


def default_config_path() -> Path:
    """Return the canonical molq config.yaml path, bootstrapping the dir.

    Delegates to :func:`molcfg.paths.project_config_dir` so the dir is
    created idempotently on first call and ``MOLCRAFTS_HOME`` is
    honoured for redirection (tests, ops, multi-user hosts).
    """
    from molcfg.paths import project_config_dir

    return project_config_dir("molq") / "config.yaml"


def _reject_superseded_toml(config_path: Path) -> None:
    """Fail loudly when only the retired ``config.toml`` is present.

    molq reads YAML. A leftover TOML file would otherwise be skipped in
    silence and molq would start with no profiles at all — every cluster
    the user configured simply gone, with no error to explain it.
    """
    legacy = config_path.with_suffix(".toml")
    if not legacy.exists():
        return
    raise ConfigError(
        f"{legacy} is a TOML config; molq reads YAML. "
        f"Rewrite it as {config_path.name} — the keys are unchanged, only "
        f"the syntax differs.",
        path=str(legacy),
    )


def load_config(path: str | Path | None = None) -> MolqConfig:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if not config_path.exists():
        _reject_superseded_toml(config_path)
        return MolqConfig(profiles={}, plugins={})

    cfg = ConfigLoader([YamlFileSource(config_path)]).load()
    raw_profiles = cfg.get("profiles")
    profiles: dict[str, MolqProfile] = {}
    if raw_profiles:
        for name, section in raw_profiles.items():
            data: dict[str, Any] = (
                section.to_dict() if hasattr(section, "to_dict") else section
            )
            profiles[name] = _parse_profile(name, data)

    plugins = _parse_plugins_section(cfg.get("plugins"))
    return MolqConfig(profiles=profiles, plugins=plugins)


def _parse_plugins_section(raw: Any) -> dict[str, dict[str, Any]]:
    """Parse ``[plugins.<name>]`` tables into plain dicts."""
    if raw is None:
        return {}
    if hasattr(raw, "to_dict"):
        raw = raw.to_dict()
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, section in raw.items():
        if hasattr(section, "to_dict"):
            section = section.to_dict()
        if isinstance(section, dict):
            out[str(name)] = dict(section)
        else:
            out[str(name)] = {"enabled": bool(section)}
    return out


def enabled_plugin_names(
    plugins: dict[str, dict[str, Any]],
    *,
    default_official: Sequence[str] | None = None,
) -> list[str]:
    """Names to load: explicit enabled plugins, or *default_official* when empty.

    A plugin with ``enabled = false`` is never loaded. When the config has no
    ``[plugins]`` entries at all, *default_official* (e.g. ``["nerve"]`` for
    daemon) is used.
    """
    if not plugins:
        return list(default_official or [])
    names: list[str] = []
    for name, pcfg in plugins.items():
        if pcfg.get("enabled", True) is False:
            continue
        names.append(name)
    return names


def load_profile(name: str, path: str | Path | None = None) -> MolqProfile:
    config = load_config(path)
    profile = config.profiles.get(name)
    if profile is None:
        raise ConfigError(f"Profile {name!r} not found", profile=name)
    return profile


def _parse_profile(name: str, data: dict[str, Any]) -> MolqProfile:
    try:
        cfg_validate(data, _ProfileSchema, allow_extra=True)
    except CfgValidationError as exc:
        raise ConfigError(
            f"Profile {name!r} is invalid: {'; '.join(exc.errors)}",
            profile=name,
        ) from exc

    scheduler: str = data["scheduler"]
    cluster_name: str = data["cluster_name"]

    defaults = data.get("defaults", {})
    scheduler_options = _parse_scheduler_options(
        scheduler, data.get("scheduler_options")
    )
    return MolqProfile(
        name=name,
        scheduler=scheduler,
        cluster_name=cluster_name,
        defaults=SubmitorDefaults(
            resources=deserialize_resources(defaults.get("resources", {}))
            if defaults.get("resources")
            else None,
            scheduling=deserialize_scheduling(defaults.get("scheduling", {}))
            if defaults.get("scheduling")
            else None,
            execution=deserialize_execution(defaults.get("execution", {}))
            if defaults.get("execution")
            else None,
        ),
        scheduler_options=scheduler_options,
        retry=deserialize_retry_policy(data.get("retry")),
        retention=deserialize_retention_policy(data.get("retention")),
        jobs_dir=data.get("jobs_dir"),
        host=data.get("host"),
    )


def _parse_scheduler_options(
    scheduler: str,
    data: dict[str, Any] | None,
) -> SchedulerOptions | None:
    if not data:
        return None
    if scheduler == "slurm":
        return SlurmSchedulerOptions(**data)
    if scheduler == "pbs":
        return PBSSchedulerOptions(**data)
    if scheduler == "lsf":
        return LSFSchedulerOptions(**data)
    return LocalSchedulerOptions(**data)
