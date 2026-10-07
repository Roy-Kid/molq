"""Optional periodic peer client: cadence/notification, never state diff."""

from __future__ import annotations

import asyncio
import json

from molq.client.async_wire import AsyncWire
from molq.errors import MolqError


async def run(
    *,
    endpoint: str | None = None,
    registry: str | None = None,
    token: str | None = None,
    clusters: list[str] | None = None,
    interval: float = 5,
    once: bool = False,
    nerve_endpoint: str | None = None,
) -> None:
    """Observe Cluster batches through RPC with finite notification/backoff.

    Args:
        endpoint: Shared Runtime endpoint; recommended for background use.
        registry: Temporary stdio registry for standalone observation.
        token: Runtime credential.
        clusters: Explicit scopes, or registered destinations.
        interval: Client-owned cadence, independent of Cluster definitions.
        once: Sample once and exit.
        nerve_endpoint: Optional notification receiver; failures are fail-open.
    """
    if interval <= 0:
        raise MolqError("INVALID_INPUT", "Observer interval must be positive")
    from aiohttp import ClientError, ClientSession, ClientTimeout

    cursors = {}
    backoff = interval
    wire = AsyncWire(endpoint=endpoint, registry=registry, token=token)
    try:
        await wire.connect()
        async with ClientSession(timeout=ClientTimeout(total=5)) as notifications:
            names = clusters or [c["id"] for c in await wire.call("clusters.list")]
            while True:
                try:
                    for name in names:
                        observed = await wire.call(
                            "jobs.observe",
                            {
                                "cluster": name,
                                **(
                                    {"cursor": cursors[name]} if name in cursors else {}
                                ),
                            },
                        )
                        cursors[name] = observed["cursor"]
                        for event in observed["changes"]:
                            print(
                                json.dumps(
                                    {
                                        "jsonrpc": "2.0",
                                        "method": "events",
                                        "params": event,
                                    }
                                ),
                                flush=True,
                            )
                            if nerve_endpoint:
                                try:
                                    async with notifications.post(
                                        nerve_endpoint, json=event
                                    ) as response:
                                        await response.content.read(65536)
                                except (ClientError, TimeoutError, OSError):
                                    pass
                    backoff = interval
                except MolqError as exc:
                    print(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "method": "observer.error",
                                "params": exc.to_wire(),
                            }
                        ),
                        flush=True,
                    )
                    backoff = min(60, max(interval, backoff * 2))
                if once:
                    return
                await asyncio.sleep(backoff)
    finally:
        await wire.close()
