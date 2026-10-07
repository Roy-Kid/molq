"""One implementation of registry, submission, queries and observation."""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
import posixpath
import time
import uuid
from collections import OrderedDict
from pathlib import Path, PurePosixPath
from typing import Any

from molq.errors import MolqError
from molq.protocol import contract, validate
from molq.registry import Registry
from molq.runtime.observation import Observation, collection, key, snapshot
from molq.runtime.planning import normalize
from molq.scheduler import Scheduler, create_scheduler
from molq.transport import create_transport


class Runtime:
    """In-process services with bounded Cluster/batch concurrency, no timers."""

    def __init__(self, registry: Path):
        self.registry = Registry(registry)
        entries = self.registry.config("settings", "cache_max_entries")["value"]
        self.observation = Observation(max_entries=entries or 4096)
        self.id = uuid.uuid4().hex
        self.schedulers: dict[str, Scheduler] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.limit = asyncio.Semaphore(4)
        self.changed = asyncio.Condition()
        self.samples: dict[tuple, asyncio.Task] = {}
        self.operations: OrderedDict[str, tuple[float, str, asyncio.Task]] = (
            OrderedDict()
        )

    async def close(self) -> None:
        """Drain finite dispatched mutations and close owned infrastructure."""
        if self.operations:
            await asyncio.gather(
                *(value[2] for value in self.operations.values()),
                return_exceptions=True,
            )
        if self.samples:
            await asyncio.gather(*self.samples.values(), return_exceptions=True)
        self.registry.close()

    def _cluster(self, name: str) -> tuple[dict, Scheduler]:
        cluster = self.registry.get(name)
        identity = cluster["id"]
        if identity not in self.schedulers:
            self.schedulers[identity] = create_scheduler(
                cluster, create_transport(cluster.get("transport", {"kind": "local"}))
            )
            self.locks.setdefault(identity, asyncio.Lock())
        return cluster, self.schedulers[identity]

    def _ref(self, cluster: dict, job) -> dict:
        if not job.incarnation:
            raise MolqError(
                "JOB_IDENTITY_UNVERIFIABLE",
                "Native submit identity evidence unavailable",
                native_id=job.native_id,
            )
        return {
            "registry_id": self.registry.id,
            "cluster_id": cluster["id"],
            "native_id": job.native_id,
            "incarnation": job.incarnation,
        }

    def _check_ref(self, ref: dict) -> None:
        if ref["registry_id"] != self.registry.id:
            raise MolqError(
                "REGISTRY_MISMATCH", "JobRef belongs to a different registry"
            )

    def _definition(self, definition: dict) -> dict:
        definition = copy.deepcopy(definition)
        definition.setdefault("transport", {"kind": "local"})
        definition.setdefault("defaults", {})
        root = PurePosixPath(definition["target_root"])
        if (
            not root.is_absolute()
            or ".." in root.parts
            or "\n" in str(root)
            or "\r" in str(root)
        ):
            raise MolqError(
                "INVALID_INPUT", "target_root must be an absolute target POSIX path"
            )
        definition["target_root"] = str(root)
        return definition

    def _changed(self) -> None:
        self.observation.clear()
        self.schedulers.clear()
        # Locks outlive cached implementations so in-flight batches remain safe.

    async def call(self, method: str, params: dict) -> Any:
        """Validate one public operation, then execute it with a finite deadline."""
        schema = contract()["methods"].get(method)
        if schema is None:
            raise MolqError("METHOD_NOT_FOUND", "Unknown RPC method", method=method)
        validate(params, schema)
        request_key = params.get("request_key")
        if request_key and method in {"jobs.submit", "jobs.cancel"}:
            fingerprint = hashlib.sha256(
                json.dumps(
                    {"method": method, "params": params}, sort_keys=True
                ).encode()
            ).hexdigest()
            now = time.monotonic()
            for identity, value in list(self.operations.items()):
                if value[2].done() and now - value[0] > 600:
                    self.operations.pop(identity)
            if request_key in self.operations:
                prior = self.operations[request_key]
                if prior[1] != fingerprint:
                    raise MolqError(
                        "CONFLICT",
                        "request_key was already used for a different operation",
                    )
                return await asyncio.shield(prior[2])
            if len(self.operations) >= 1024:
                raise MolqError("STATE_BUSY", "Bounded operation-result store is full")
            task = asyncio.create_task(self._dispatch_deadline(method, params))
            self.operations[request_key] = (now, fingerprint, task)
            return await asyncio.shield(task)
        return await self._dispatch_deadline(method, params)

    async def _dispatch_deadline(self, method: str, p: dict) -> Any:
        try:
            async with asyncio.timeout(120):
                return await self._dispatch(method, p)
        except TimeoutError as exc:
            mutation = method in {
                "jobs.submit",
                "jobs.cancel",
                "jobs.cancel_many",
                "files.write",
                "files.transfer",
            }
            raise MolqError(
                "OUTCOME_UNKNOWN" if mutation else "RUNTIME_DEADLINE",
                "Runtime operation deadline exceeded",
                outcome="unknown" if mutation else "not_applied",
            ) from exc

    async def _dispatch(self, method: str, p: dict) -> Any:
        if method == "molq.hello":
            return {
                "version": {"major": 1, "minor": 0},
                "release": "0.9.0",
                "schema_version": 1,
                "registry_id": self.registry.id,
                "runtime_instance_id": self.id,
                "methods": list(contract()["methods"]),
                "limits": {"max_frame_bytes": 1048576, "batch_size": 128},
            }
        if method == "schema.discover":
            return contract()
        if method == "clusters.list":
            return self.registry.list()
        if method == "clusters.get":
            return self.registry.get(p["cluster"])
        if method in {"clusters.register", "clusters.update", "clusters.remove"}:
            definition = (
                None
                if method == "clusters.remove"
                else self._definition(
                    p["definition"] if method == "clusters.update" else p
                )
            )
            existing = self.registry.get(p["cluster"]) if p.get("cluster") else None
            if existing:
                lock = self.locks.setdefault(existing["id"], asyncio.Lock())
                async with lock:
                    result = self.registry.mutate(
                        definition,
                        key=existing["id"],
                        expected_revision=p["expected_revision"],
                    )
            else:
                result = self.registry.mutate(definition)
            self._changed()
            async with self.changed:
                self.changed.notify_all()
            return result
        if method.startswith("config.") or method.startswith("presets."):
            table = "settings" if method.startswith("config.") else "presets"
            result = self.registry.config(
                table, p.get("key"), p.get("value"), write=method.endswith(".set")
            )
            if table == "settings" and method.endswith(".set"):
                if p["key"] == "cache_max_entries":
                    self.observation.max_entries = p["value"]
                self.observation.clear()
                async with self.changed:
                    self.changed.notify_all()
            return result
        if method == "events.subscribe":
            return self.observation.since(p.get("cursor"))
        if method in {"jobs.validate", "jobs.preview", "jobs.submit"}:
            return await self._submit(method, p)
        if method in {
            "jobs.get",
            "jobs.get_many",
            "jobs.observe",
            "jobs.list",
            "jobs.history",
        }:
            return await self._query(method, p)
        if method in {"jobs.cancel", "jobs.cancel_many"}:
            return await self._cancel(p)
        if method == "logs.read":
            return await self._logs(p)
        if method.startswith("files."):
            return await self._files(method, p)
        raise MolqError("METHOD_NOT_FOUND", "Unknown RPC method")

    async def _submit(self, method: str, p: dict) -> Any:
        cluster, scheduler = self._cluster(p["cluster"])
        spec = normalize(p["spec"], cluster["defaults"])
        scheduler.validate(spec)
        if method == "jobs.validate":
            return {"spec": spec, "cluster_revision": cluster["revision"]}
        directory = posixpath.join(cluster["target_root"], uuid.uuid4().hex)
        if method == "jobs.preview":
            return {
                "spec": spec,
                "script": scheduler.render(spec, directory),
                "cluster_revision": cluster["revision"],
            }
        async with self.limit, self.locks[cluster["id"]]:
            for edge in spec["scheduling"].get("dependencies", []):
                ref = edge["ref"]
                self._check_ref(ref)
                if ref["cluster_id"] != cluster["id"]:
                    raise MolqError(
                        "INVALID_INPUT",
                        "Native dependencies must belong to the same Cluster",
                    )
                await self._identity(scheduler, ref)
            if self.registry.get(cluster["id"])["revision"] != cluster["revision"]:
                raise MolqError("CONFLICT", "Cluster changed before native submission")
            job = await scheduler.submit(spec, directory)
            ref = self._ref(cluster, job)
            value = snapshot(ref, job)
            self.observation.remember(value)
            return {
                "ref": ref,
                "snapshot": value,
                "cluster_revision": cluster["revision"],
                "outcome": "accepted",
            }

    async def _identity(self, scheduler: Scheduler, ref: dict):
        jobs = await scheduler.query_many([ref["native_id"]])
        job = jobs.get(ref["native_id"])
        if job is None or not job.incarnation:
            raise MolqError(
                "JOB_IDENTITY_UNVERIFIABLE", "Cannot confirm native allocation identity"
            )
        if job.incarnation != ref["incarnation"]:
            raise MolqError("JOB_IDENTITY_MISMATCH", "Native ID has been reused")
        return job

    async def _sample(
        self,
        cluster_id: str,
        scheduler: Scheduler,
        ids: list[str],
        *,
        history: bool = False,
    ) -> dict:
        """Coalesce identical in-flight Cluster batches, without per-Job workers."""
        identity = (cluster_id, history, tuple(sorted(set(ids))))
        task = self.samples.get(identity)
        if task is None:

            async def query():
                async with asyncio.timeout(110), self.limit, self.locks[cluster_id]:
                    return await (
                        scheduler.history(ids) if history else scheduler.query_many(ids)
                    )

            task = asyncio.create_task(query())
            self.samples[identity] = task

            def release(done):
                if self.samples.get(identity) is done:
                    self.samples.pop(identity, None)
                if not done.cancelled():
                    done.exception()

            task.add_done_callback(release)
        return await asyncio.shield(task)

    async def _many(
        self,
        refs: list[dict],
        consistency: str = "live",
        max_age: float = 5,
        *,
        history: bool = False,
    ) -> dict:
        groups: dict[str, list[dict]] = {}
        found: dict[str, dict] = {}
        errors = []
        for ref in refs:
            self._check_ref(ref)
            cached = (
                self.observation.cached(
                    ref, max_age=max_age if consistency == "bounded" else None
                )
                if consistency != "live"
                else None
            )
            if cached:
                found[key(ref)] = cached
            elif consistency == "cached":
                error = MolqError("CACHE_MISS", "No cached observation").to_wire()
                found[key(ref)] = snapshot(ref, None, error=error)
                errors.append(error)
            else:
                groups.setdefault(ref["cluster_id"], []).append(ref)

        async def sample(identity: str, batch: list[dict]):
            _, scheduler = self._cluster(identity)
            try:
                jobs = await self._sample(
                    identity,
                    scheduler,
                    [r["native_id"] for r in batch],
                    history=history,
                )
                for ref in batch:
                    job = jobs.get(ref["native_id"])
                    if job is not None and job.incarnation != ref["incarnation"]:
                        error = MolqError(
                            "JOB_IDENTITY_MISMATCH", "Native identity no longer matches"
                        ).to_wire()
                        errors.append(error)
                        found[key(ref)] = snapshot(ref, None, error=error)
                    else:
                        value = snapshot(ref, job)
                        found[key(ref)] = value
                        self.observation.remember(value)
            except MolqError as exc:
                error = exc.to_wire()
                errors.append(error)
                for ref in batch:
                    stale = self.observation.cached(ref, max_age=None)
                    value = snapshot(ref, None, error=error)
                    if stale:
                        value["last_known"] = stale
                    found[key(ref)] = value

        await asyncio.gather(
            *(sample(identity, batch) for identity, batch in groups.items())
        )
        return collection([found[key(ref)] for ref in refs], errors)

    async def _list(self, cluster_name: str) -> tuple[dict, list[dict]]:
        cluster, scheduler = self._cluster(cluster_name)
        async with self.limit, self.locks[cluster["id"]]:
            jobs = await scheduler.list()
        values = []
        for job in jobs:
            if not job.incarnation:
                raise MolqError(
                    "JOB_IDENTITY_UNVERIFIABLE",
                    "Queue entry lacks stable native submit identity",
                )
            value = snapshot(self._ref(cluster, job), job)
            self.observation.remember(value)
            values.append(value)
        return cluster, values

    async def _query(self, method: str, p: dict) -> dict:
        if method == "jobs.list":
            _, values = await self._list(p["cluster"])
            return collection(values)
        if method == "jobs.get":
            result = await self._many(
                [p["ref"]],
                p.get("consistency", "live"),
                p.get(
                    "max_age",
                    self.registry.config("settings", "cache_max_age")["value"] or 5,
                ),
            )
            if errors := result["coverage"]["errors"]:
                raise MolqError.from_wire(errors[0])
            return result
        refs = p.get("refs")
        cluster = None
        if p.get("cluster"):
            cluster = self.registry.get(p["cluster"])
        scope = json.dumps(
            {
                "cluster": cluster["id"] if cluster else None,
                "refs": sorted(key(r) for r in refs) if refs else None,
            },
            sort_keys=True,
        )
        if refs is None:
            if cluster is None:
                raise MolqError(
                    "INVALID_INPUT", "observe requires explicit refs or Cluster"
                )
            _, values = await self._list(cluster["id"])
            refs = [s["ref"] for s in values]
            prior = self.observation.baselines.get(p.get("cursor", ""))
            if prior and prior[1] == scope:
                known = {key(r) for r in refs}
                refs.extend(
                    s["ref"]
                    for identity, s in prior[2].items()
                    if identity not in known
                )
        if cluster and any(r["cluster_id"] != cluster["id"] for r in refs):
            raise MolqError(
                "INVALID_INPUT", "Observation refs do not match Cluster scope"
            )
        result = await self._many(
            refs,
            p.get("consistency", "live"),
            p.get(
                "max_age",
                self.registry.config("settings", "cache_max_age")["value"] or 5,
            ),
            history=method == "jobs.history",
        )
        if method != "jobs.observe":
            return result
        observed = self.observation.observe(result, scope, p.get("cursor"))
        if observed["changes"]:
            async with self.changed:
                self.changed.notify_all()
        return observed

    async def _cancel(self, p: dict) -> dict:
        refs = p.get("refs", [p["ref"]] if "ref" in p else [])
        results = []
        # Per-Cluster batching, no permanent Job workers or per-Job timers.
        for ref in refs:
            try:
                self._check_ref(ref)
                cluster, scheduler = self._cluster(ref["cluster_id"])
                async with self.limit, self.locks[cluster["id"]]:
                    job = await self._identity(scheduler, ref)
                    outcome = await scheduler.cancel(job)
                results.append({"ref": ref, **outcome})
            except MolqError as exc:
                if len(refs) == 1:
                    raise
                results.append({"ref": ref, "error": exc.to_wire()})
        return (
            results[0]
            if "ref" in p
            else {
                "results": results,
                "partial_failure": any("error" in r for r in results),
            }
        )

    def _target_path(self, cluster: dict, path: str) -> str:
        root = PurePosixPath(cluster["target_root"])
        result = PurePosixPath(path) if path.startswith("/") else root / path
        if ".." in result.parts or result != root and root not in result.parents:
            raise MolqError(
                "PERMISSION_DENIED", "File operations are scoped to Cluster target_root"
            )
        if cluster["transport"]["kind"] == "local":
            resolved = Path(str(result)).resolve()
            base = Path(str(root)).resolve()
            if resolved != base and base not in resolved.parents:
                raise MolqError("PERMISSION_DENIED", "File symlink escapes target root")
        return str(result)

    async def _logs(self, p: dict) -> dict:
        ref = p["ref"]
        self._check_ref(ref)
        cluster, scheduler = self._cluster(ref["cluster_id"])
        job = await self._identity(scheduler, ref)
        stream = p.get("stream", "stdout")
        path = job.stdout_path if stream == "stdout" else job.stderr_path
        if path is None:
            if not job.workdir:
                raise MolqError("FILE_UNAVAILABLE", "Native log location unavailable")
            path = posixpath.join(job.workdir, stream)
        path = self._target_path(cluster, path)
        data = await scheduler.transport.read(
            path, offset=p.get("offset", 0), limit=p.get("limit", 262144)
        )
        return {
            "text": data.decode("utf-8", "replace"),
            "next_offset": p.get("offset", 0) + len(data),
            "bytes_read": len(data),
        }

    async def _files(self, method: str, p: dict) -> dict:
        if method == "files.transfer":
            source, ss = self._cluster(p["source_cluster"])
            destination, ds = self._cluster(p["destination_cluster"])
            src = self._target_path(source, p["source_path"])
            dst = self._target_path(destination, p["destination_path"])
            import shlex

            st, dt = source["transport"], destination["transport"]
            args = ["rsync", "-a"]
            runner = ss.transport
            if st != dt:
                args.extend(["-e", "ssh -T -o BatchMode=yes"])
                if st["kind"] == "local" and dt["kind"] == "ssh":
                    args.extend(["--", src, dt["alias"] + ":" + shlex.quote(dst)])
                elif st["kind"] == "ssh" and dt["kind"] == "local":
                    runner = ds.transport
                    args.extend(["--", st["alias"] + ":" + shlex.quote(src), dst])
                else:
                    raise MolqError(
                        "TRANSFER_UNSUPPORTED",
                        "Two distinct SSH targets require explicit staging; no remote alias guessing",
                    )
            else:
                args.extend(["--", src, dst])
            if st == dt and src == dst:
                raise MolqError(
                    "INVALID_INPUT", "Transfer source and destination are the same file"
                )
            async with self.limit:
                result = await runner.run(args, timeout=90)
            if result.returncode:
                raise MolqError(
                    "FILE_UNAVAILABLE",
                    "Target rsync transfer failed",
                    outcome="unknown",
                    returncode=result.returncode,
                )
            size = await ss.transport.run(["wc", "-c", src])
            return {
                "outcome": "applied",
                "bytes": int(size.text.split()[0]) if not size.returncode else None,
            }
        cluster, scheduler = self._cluster(p["cluster"])
        path = self._target_path(cluster, p["path"])
        if method == "files.read":
            data = await scheduler.transport.read(
                path, offset=p.get("offset", 0), limit=p.get("limit", 262144)
            )
            return {
                "data": base64.b64encode(data).decode(),
                "next_offset": p.get("offset", 0) + len(data),
            }
        try:
            data = base64.b64decode(p["data"], validate=True)
        except ValueError as exc:
            raise MolqError("INVALID_INPUT", "File content must be base64") from exc
        if len(data) > 262144:
            raise MolqError("INVALID_INPUT", "File chunk too large")
        await scheduler.transport.write(path, data, offset=p.get("offset"))
        return {"outcome": "applied", "next_offset": p.get("offset", 0) + len(data)}
