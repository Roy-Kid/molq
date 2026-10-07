"""Runtime-owned destination/config persistence; never job history."""

from __future__ import annotations

import builtins
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from molq.errors import MolqError

SCHEMA_VERSION = 1
SETTINGS = {
    "default_cluster": str,
    "cache_max_age": (int, float),
    "cache_max_entries": int,
}


def default_registry() -> Path:
    """Return the native registry location without creating anything."""
    if path := os.environ.get("MOLQ_REGISTRY"):
        return Path(path).expanduser()
    if os.name == "nt":
        return (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "molq/registry.db"
        )
    return (
        Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
        / "molq/registry.db"
    )


class Registry:
    """Short SQLite transactions for one active Runtime and accidental overlap."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=0.1, isolation_level=None)
        try:
            tables = {
                r[0]
                for r in self.db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            owned = {"schema_meta", "clusters", "settings", "presets"}
            if tables - owned or tables and "schema_meta" not in tables:
                raise MolqError(
                    "STATE_SCHEMA_INCOMPATIBLE",
                    "Registry contains an unsupported or legacy schema",
                )
            if "schema_meta" in tables:
                meta = dict(self.db.execute("SELECT key,value FROM schema_meta"))
                if meta.get("schema_version") != str(SCHEMA_VERSION):
                    raise MolqError(
                        "STATE_SCHEMA_INCOMPATIBLE", "Unsupported registry schema"
                    )
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""CREATE TABLE IF NOT EXISTS schema_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS clusters(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,definition TEXT NOT NULL,revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS presets(key TEXT PRIMARY KEY,value TEXT NOT NULL);""")
            self.db.execute(
                "INSERT OR IGNORE INTO schema_meta VALUES (?,?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO schema_meta VALUES (?,?)",
                ("registry_id", str(uuid.uuid4())),
            )
            self.id = dict(self.db.execute("SELECT key,value FROM schema_meta"))[
                "registry_id"
            ]
        except sqlite3.OperationalError as exc:
            self.db.close()
            raise MolqError("STATE_BUSY", "Cannot open registry configuration") from exc
        except BaseException:
            self.db.close()
            raise

        if os.name != "nt":
            path.chmod(0o600)

    def close(self) -> None:
        """Release the owned registry connection."""
        self.db.close()

    def list(self) -> builtins.list[dict[str, Any]]:
        """Return destination definitions, without live state."""
        return [
            self._row(row)
            for row in self.db.execute(
                "SELECT id,definition,revision FROM clusters ORDER BY name"
            )
        ]

    def get(self, key: str) -> dict[str, Any]:
        """Resolve only explicitly registered names or stable IDs."""
        row = self.db.execute(
            "SELECT id,definition,revision FROM clusters WHERE id=? OR name=?",
            (key, key),
        ).fetchone()
        if row is None:
            raise MolqError("CLUSTER_NOT_FOUND", "Unknown Cluster", cluster=key)
        return self._row(row)

    @staticmethod
    def _row(row: tuple) -> dict[str, Any]:
        return {**json.loads(row[1]), "id": row[0], "revision": row[2]}

    def mutate(
        self,
        definition: dict[str, Any] | None,
        *,
        key: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Register/update/remove with bounded, revision-checked writes."""
        try:
            self.db.execute("BEGIN IMMEDIATE")
            if key is None:
                identity = str(uuid.uuid4())
                assert definition is not None
                self.db.execute(
                    "INSERT INTO clusters VALUES (?,?,?,1)",
                    (identity, definition["name"], json.dumps(definition)),
                )
            else:
                old = self.get(key)
                identity = old["id"]
                if old["revision"] != expected_revision:
                    raise MolqError(
                        "CONFLICT",
                        "Cluster revision changed",
                        current_revision=old["revision"],
                    )
                if definition is None:
                    self.db.execute("DELETE FROM clusters WHERE id=?", (identity,))
                else:
                    for field in ("scheduler", "transport", "target_root"):
                        if old.get(field) != definition.get(field):
                            raise MolqError(
                                "INVALID_INPUT",
                                "Changed compute destination requires a new Cluster ID",
                                field=field,
                            )
                    self.db.execute(
                        "UPDATE clusters SET name=?,definition=?,revision=revision+1 WHERE id=?",
                        (definition["name"], json.dumps(definition), identity),
                    )
            result = (
                self.get(identity) if definition is not None else {"removed": identity}
            )
            self.db.execute("COMMIT")
            return result
        except sqlite3.IntegrityError as exc:
            self.db.execute("ROLLBACK")
            raise MolqError("CONFLICT", "Cluster name already registered") from exc
        except sqlite3.OperationalError as exc:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise MolqError(
                "STATE_BUSY", "Registry busy; retry this configuration operation"
            ) from exc
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def config(
        self,
        table: str,
        key: str | None = None,
        value: Any = None,
        *,
        write: bool = False,
    ) -> Any:
        """Read/write fixed owned-state namespaces, with no Job namespace."""
        if table not in {"settings", "presets"}:
            raise MolqError("INVALID_INPUT", "Invalid owned-state namespace")
        if table == "settings" and (
            key is None
            or key not in SETTINGS
            or (write and not isinstance(value, SETTINGS[key]))
        ):
            raise MolqError(
                "INVALID_INPUT", "Unknown or invalid runtime setting", key=key
            )
        if (
            table == "settings"
            and write
            and key != "default_cluster"
            and (isinstance(value, bool) or value <= 0 or value > 1000000)
        ):
            raise MolqError("INVALID_INPUT", "Runtime setting out of range", key=key)
        try:
            if write:
                self.db.execute(
                    f"INSERT INTO {table} VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, json.dumps(value)),
                )
                return {"key": key, "value": value}
            if key is None:
                return [
                    {"key": k, "value": json.loads(v)}
                    for k, v in self.db.execute(
                        f"SELECT key,value FROM {table} ORDER BY key"
                    )
                ]
            row = self.db.execute(
                f"SELECT value FROM {table} WHERE key=?", (key,)
            ).fetchone()
            return {"key": key, "value": json.loads(row[0]) if row else None}
        except sqlite3.OperationalError as exc:
            raise MolqError("STATE_BUSY", "Registry busy") from exc
