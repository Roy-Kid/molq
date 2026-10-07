"""Authenticated HTTP/WS and static Web entry for the same Runtime."""

from __future__ import annotations

import asyncio
import hmac
from importlib.resources import files
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web

from molq.errors import MolqError
from molq.runtime.rpc import MAX_FRAME, decode, dispatch, error_response, event_stream
from molq.runtime.services import Runtime


def application(runtime: Runtime, token: str) -> web.Application:
    """Construct a single-owner app; TLS belongs to deployment infrastructure."""
    if not token or len(token) < 16:
        raise MolqError(
            "INVALID_INPUT",
            "Network runtime requires a token of at least 16 characters",
        )

    @web.middleware
    async def authenticate(request, handler):
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            return web.json_response(
                error_response(
                    None,
                    MolqError(
                        "PERMISSION_DENIED", "Cross-origin runtime access denied"
                    ),
                ),
                status=403,
            )
        if request.path == "/rpc" and not hmac.compare_digest(
            request.headers.get("Authorization", ""), "Bearer " + token
        ):
            return web.json_response(
                error_response(
                    None, MolqError("AUTH_REQUIRED", "Runtime bearer token required")
                ),
                status=401,
            )
        return await handler(request)

    app = web.Application(client_max_size=MAX_FRAME, middlewares=[authenticate])

    async def rpc(request):
        try:
            payload = decode(await request.read())
        except (MolqError, web.HTTPRequestEntityTooLarge) as exc:
            error = (
                exc
                if isinstance(exc, MolqError)
                else MolqError("INVALID_INPUT", "RPC frame exceeds 1 MiB")
            )
            return web.json_response(error_response(None, error, -32700), status=400)
        # Mutation completion is independent of a caller's socket lifetime.
        task = asyncio.create_task(dispatch(runtime, payload))
        pending.add(task)
        task.add_done_callback(pending.discard)
        response = await asyncio.shield(task)
        return (
            web.json_response(response)
            if response is not None
            else web.Response(status=204)
        )

    pending: set[asyncio.Task] = set()

    async def websocket(request):
        ws = web.WebSocketResponse(max_msg_size=MAX_FRAME, heartbeat=30)
        await ws.prepare(request)
        try:
            first = await asyncio.wait_for(ws.receive(), timeout=10)
            auth = decode(first.data) if first.type == WSMsgType.TEXT else {}
            if (
                not isinstance(auth, dict)
                or not isinstance(auth.get("token"), str)
                or not hmac.compare_digest(auth["token"], token)
            ):
                await ws.send_json(
                    error_response(
                        None,
                        MolqError("AUTH_REQUIRED", "First WS frame must authenticate"),
                    )
                )
                await ws.close(code=1008)
                return ws
            subscription: asyncio.Task | None = None

            async def send_events(cursor):
                async for event in event_stream(runtime, cursor):
                    if ws.closed:
                        return
                    await ws.send_json(event)

            try:
                async for message in ws:
                    if message.type != WSMsgType.TEXT:
                        continue
                    try:
                        payload = decode(message.data)
                        task = asyncio.create_task(
                            dispatch(runtime, payload, streaming=True)
                        )
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                        response = await asyncio.shield(task)
                        if response is not None:
                            await ws.send_json(response)
                        if (
                            isinstance(payload, dict)
                            and payload.get("method") == "events.subscribe"
                            and response
                            and "result" in response
                        ):
                            if subscription:
                                subscription.cancel()
                                await asyncio.gather(
                                    subscription, return_exceptions=True
                                )
                            subscription = asyncio.create_task(
                                send_events(response["result"]["cursor"])
                            )
                    except MolqError as exc:
                        await ws.send_json(error_response(None, exc, -32700))
            finally:
                if subscription:
                    subscription.cancel()
                    await asyncio.gather(subscription, return_exceptions=True)
        except (TimeoutError, MolqError):
            await ws.close(code=1008)
        return ws

    async def asset(request):
        name = request.match_info.get("name", "index.html")
        if name not in {"index.html", "app.js", "style.css", "wire.js"}:
            raise web.HTTPNotFound()
        item = files("molq.web").joinpath(name)
        return web.Response(
            body=item.read_bytes(),
            content_type={
                "html": "text/html",
                "js": "text/javascript",
                "css": "text/css",
            }[name.rsplit(".", 1)[1]],
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'",
            },
        )

    async def close(app):
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await runtime.close()

    app.router.add_post("/rpc", rpc)
    app.router.add_get("/ws", websocket)
    app.router.add_get("/", asset)
    app.router.add_get("/{name}", asset)
    app.on_cleanup.append(close)
    return app
