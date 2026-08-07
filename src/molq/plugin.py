"""Plugin host for molq.

Official plugins ship under :mod:`molq.plugins` and are loaded by name.
Third-party plugins register via the ``molq.plugins`` setuptools entry-point
group and are discovered at load time.

Plugins attach to a :class:`PluginContext` (event bus + record accessors +
config). They must not import scheduler/store internals; they observe
lifecycle through :class:`~molq.callbacks.EventBus` only.
"""

from __future__ import annotations

import importlib
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from molq._log import get_logger
from molq.callbacks import EventBus
from molq.models import JobRecord

logger = get_logger(__name__)

# Official plugins: name → "module:attr" factory (attr is callable → MolqPlugin).
BUILTIN_PLUGIN_FACTORIES: dict[str, str] = {
    "nerve": "molq.plugins.nerve:create_plugin",
}

ENTRY_POINT_GROUP = "molq.plugins"


@dataclass(frozen=True)
class PluginContext:
    """Read-only surface a plugin may use after attach.

    Intentionally narrow: no scheduler/store write path.
    """

    event_bus: EventBus
    cluster_name: str
    config: Mapping[str, Any]
    get_record: Callable[[str], JobRecord | None]
    list_active_records: Callable[[], list[JobRecord]]
    list_records: Callable[[], list[JobRecord]]


@runtime_checkable
class MolqPlugin(Protocol):
    """Lifecycle observer attached to a Submitor session."""

    @property
    def name(self) -> str:
        """Stable plugin id (config key / entry-point name)."""
        ...

    def attach(self, ctx: PluginContext) -> None:
        """Subscribe to events; must be fail-open and non-blocking."""
        ...

    def detach(self) -> None:
        """Unsubscribe and release resources. Safe to call multiple times."""
        ...


def _resolve_factory(spec: str) -> Callable[[], MolqPlugin]:
    """Resolve ``module:attr`` to a zero-arg factory."""
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError(f"Invalid plugin factory spec: {spec!r}")
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    if not callable(factory):
        raise TypeError(f"Plugin factory {spec!r} is not callable")
    return factory  # type: ignore[return-value]


def discover_third_party_factories() -> dict[str, Callable[[], MolqPlugin]]:
    """Load third-party factories from setuptools entry points.

    Official names in :data:`BUILTIN_PLUGIN_FACTORIES` win on conflict.
    """
    found: dict[str, Callable[[], MolqPlugin]] = {}
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        return found

    eps = entry_points()
    # Python 3.12+: EntryPoints.select; older returns dict-like.
    if hasattr(eps, "select"):
        selected = eps.select(group=ENTRY_POINT_GROUP)
    else:  # pragma: no cover
        selected = eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[union-attr]

    for ep in selected:
        name = ep.name
        if name in BUILTIN_PLUGIN_FACTORIES:
            logger.warning(
                f"Third-party entry point {name!r} conflicts with official plugin; ignoring"
            )
            continue
        try:
            factory = ep.load()
        except Exception:
            logger.exception(f"Failed to load entry point plugin {name!r}")
            continue
        if not callable(factory):
            logger.warning(f"Entry point plugin {name!r} is not callable; ignoring")
            continue
        found[name] = factory  # type: ignore[assignment]
    return found


def available_plugins() -> dict[str, str]:
    """Return ``{name: source}`` for builtin + discovered third-party plugins."""
    out = {name: f"builtin:{spec}" for name, spec in BUILTIN_PLUGIN_FACTORIES.items()}
    for name in discover_third_party_factories():
        out[name] = f"entry_point:{ENTRY_POINT_GROUP}"
    return out


def create_plugin(name: str) -> MolqPlugin:
    """Instantiate a plugin by name (builtin first, then entry points)."""
    if name in BUILTIN_PLUGIN_FACTORIES:
        factory = _resolve_factory(BUILTIN_PLUGIN_FACTORIES[name])
        plugin = factory()
    else:
        third = discover_third_party_factories()
        if name not in third:
            raise KeyError(
                f"Unknown plugin {name!r}. Available: {sorted(available_plugins())}"
            )
        plugin = third[name]()
    if not isinstance(plugin, MolqPlugin):
        # Protocol check is structural; still require name + attach/detach.
        if not hasattr(plugin, "name") or not hasattr(plugin, "attach"):
            raise TypeError(f"Plugin {name!r} does not implement MolqPlugin")
    return plugin


class PluginManager:
    """Owns attached plugin instances for one Submitor."""

    def __init__(self) -> None:
        self._plugins: list[MolqPlugin] = []
        self._lock = threading.Lock()

    @property
    def attached(self) -> tuple[MolqPlugin, ...]:
        with self._lock:
            return tuple(self._plugins)

    def load(
        self,
        names: Sequence[str],
        *,
        ctx_factory: Callable[[str, Mapping[str, Any]], PluginContext],
        configs: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> list[str]:
        """Attach plugins by name. Returns names successfully attached.

        Failures are logged and skipped (fail-open for observability plugins).
        """
        configs = configs or {}
        attached_names: list[str] = []
        for name in names:
            pcfg = dict(configs.get(name, {}))
            if pcfg.get("enabled", True) is False:
                logger.info(f"Plugin {name!r} disabled in config; skipping")
                continue
            try:
                plugin = create_plugin(name)
                ctx = ctx_factory(name, pcfg)
                plugin.attach(ctx)
            except Exception:
                logger.exception(f"Failed to attach plugin {name!r}")
                continue
            with self._lock:
                self._plugins.append(plugin)
            attached_names.append(name)
            logger.info(f"Attached plugin {name!r}")
        return attached_names

    def detach_all(self) -> None:
        with self._lock:
            plugins = list(self._plugins)
            self._plugins.clear()
        for plugin in plugins:
            try:
                plugin.detach()
            except Exception:
                logger.exception(
                    f"Plugin {getattr(plugin, 'name', plugin)!r} detach failed"
                )


def store_context_factory(
    event_bus: EventBus,
    cluster_name: str,
    store: Any,
) -> Callable[[str, Mapping[str, Any]], PluginContext]:
    """Build the ``ctx_factory`` :meth:`PluginManager.load` expects.

    Binds a plugin's read-only view to one cluster's slice of the store. The
    accessors are closures rather than the store itself so a plugin cannot
    reach a write method or another cluster's records.
    """

    def make(name: str, config: Mapping[str, Any]) -> PluginContext:
        return PluginContext(
            event_bus=event_bus,
            cluster_name=cluster_name,
            config=config,
            get_record=store.get_record,
            list_active_records=lambda: store.get_active_records(cluster_name),
            list_records=lambda: store.list_records(
                cluster_name, include_terminal=True
            ),
        )

    return make
