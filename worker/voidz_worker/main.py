"""Voidz Worker — node agent.

Runs on every infrastructure node. Responsibilities:

* HTTP API for the Voidz Console (auth via shared worker token):
    POST /worker/api/instances/:id/launch     deploy a Voidz Core container
    POST /worker/api/instances/:id/stop
    POST /worker/api/instances/:id/restart
    POST /worker/api/instances/:id/remove
    GET  /worker/api/instances/:id/status     (+ health probe of the Core)
    GET  /worker/api/instances/:id/logs
    GET  /worker/api/instances/:id/proxy      reverse proxy into the instance
    GET  /worker/api/metrics                  node CPU/RAM/disk + capacity
* Heartbeat loop: reports node status/capacity to the Console so the
  scheduler can place deployments.
* Reverse proxying: the worker forwards instance traffic
  (``GET /worker/api/instances/:id/proxy``) — in production the edge proxy
  routes ``<name>-<id>.voidz.app`` directly to the instance's loopback port.

Isolation: instances run under the driver (Docker with hard limits, or the
process driver with rlimits for development). The worker never exposes the
Docker socket to instances.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
import time
from pathlib import Path

import httpx
import psutil
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import registry
from .direct_token import decode as decode_direct_token
from .driver import BaseDriver, DriverError, LaunchSpec, select_driver
from .logging import get, setup_logging
from .version import info as worker_info

# Client-facing transport paths Core actually exposes (see core/voidz_core/app.py):
# ws/{uuid} (VLESS), trojan-ws, ss-ws, and the xhttp packet-up/stream-up/downlink
# routes. Nothing under core/api/* (the Core management API) may ever be reached
# through a token-authenticated public route — only through the bearer-token
# -protected /proxy route below, which only the Console itself can call.
def _is_public_client_path(path: str) -> bool:
    return (path in ("trojan-ws", "ss-ws")
            or path.startswith(("ws/", "xhttp-siz10/", "txhttp-siz10/")))


def _origin_client_ip(headers, direct_host: str | None) -> str:
    """The real, original client IP for this connection — used by Core's
    per-link device cap, so getting it wrong silently disables that cap.

    Both routes into this function are safe to trust X-Forwarded-For on.
    The internal route is only reachable with the worker token, and only
    the Console holds that, setting the header itself from the client IP
    it observed. The public direct route (/pub/{token}/...) has no such
    hop in front of it in code, but Railway's own edge terminates every
    connection before it reaches this worker and was confirmed (by
    sending a deliberately spoofed X-Forwarded-For/X-Real-Ip end to end
    and inspecting what actually arrived here) to overwrite both headers
    with its own observed values every time — a client cannot make either
    header carry anything but their real address. ``direct_host`` is the
    TCP/ASGI peer, used only when neither header is present."""
    fwd = headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return direct_host or "unknown"

setup_logging(os.environ.get("VOIDZ_LOG_LEVEL", "info"))
log = get("runtime", "voidz.worker")

WORKER_TOKEN = os.environ.get("VOIDZ_WORKER_TOKEN", "")
CONSOLE_URL = os.environ.get("VOIDZ_CONSOLE_URL", "")
CONSOLE_HEARTBEAT_TOKEN = os.environ.get("VOIDZ_WORKER_HEARTBEAT_TOKEN", "")
DATA_ROOT = Path(os.environ.get("VOIDZ_WORKER_DATA", "/var/lib/voidz/instances"))
NODE_ID = os.environ.get("VOIDZ_NODE_ID", "local")
NODE_REGION = os.environ.get("VOIDZ_NODE_REGION", "local")
PUBLIC_BASE = os.environ.get("VOIDZ_PUBLIC_BASE", "")
HEARTBEAT_INTERVAL = float(os.environ.get("VOIDZ_WORKER_HEARTBEAT_SECONDS", "15"))

if not WORKER_TOKEN:
    raise RuntimeError("VOIDZ_WORKER_TOKEN must be set (shared secret with the Console)")

driver: BaseDriver
app = FastAPI(title="Voidz Worker", docs_url=False, redoc_url=False)


def require_worker_token(request: Request) -> None:
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    if not token or not secrets.compare_digest(token, WORKER_TOKEN):
        raise HTTPException(status_code=401, detail="unauthorized")


async def probe_core(port: int, token: str, timeout: float = 3.0) -> dict | None:
    """Health-probe a running Core. Returns its health payload or None."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"http://127.0.0.1:{port}/health")
            if resp.status_code != 200:
                return None
            return resp.json()
    except (httpx.HTTPError, OSError):
        return None


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Voidz Worker", "version": worker_info()["version"], "node": NODE_ID}


@app.get("/ready")
async def ready():
    return {"ready": True}


# ---------------------------------------------------------------------------
# Instance lifecycle
# ---------------------------------------------------------------------------
@app.post("/worker/api/instances/{instance_id}/launch")
async def launch_instance(instance_id: str, request: Request, _=Depends(require_worker_token)):
    body = await request.json()
    if driver.is_known(instance_id):
        # Idempotent (re)launch: redeploys hit this path. Stop the old process
        # but KEEP its data dir so links and state survive.
        try:
            await driver.stop(instance_id)
        except DriverError:
            pass
        driver.handles.pop(instance_id, None)
    spec = LaunchSpec(
        instance_id=instance_id,
        deployment_id=str(body.get("deployment_id") or ""),
        core_version=str(body.get("core_version") or "latest"),
        api_token=body.get("core_api_token") or secrets.token_urlsafe(24),
        public_host=str(body.get("public_host") or ""),
        cpu_limit=float(body.get("cpu_limit") or 0.5),
        memory_mb=int(body.get("memory_mb") or 256),
        max_processes=int(body.get("max_processes") or 128),
    )
    try:
        handle = await driver.launch(spec)
    except DriverError as exc:
        raise HTTPException(status_code=502, detail=f"launch failed: {exc}")
    registry.save_instance(instance_id, {
        "deployment_id": spec.deployment_id,
        "core_version": spec.core_version,
        "api_token": spec.api_token,
        "public_host": spec.public_host,
        "cpu_limit": spec.cpu_limit,
        "memory_mb": spec.memory_mb,
        "max_processes": spec.max_processes,
        "port": handle.port,
    })
    return {
        "ok": True,
        "instance_id": instance_id,
        "port": handle.port,
        "driver": driver.name,
        "core_api_token": spec.api_token,
    }


@app.post("/worker/api/instances/{instance_id}/stop")
async def stop_instance(instance_id: str, _=Depends(require_worker_token)):
    try:
        await driver.stop(instance_id)
    except DriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True}


@app.post("/worker/api/instances/{instance_id}/restart")
async def restart_instance(instance_id: str, request: Request, _=Depends(require_worker_token)):
    """Stop the instance (if running) and launch it again with the supplied
    launch parameters. The Console passes the stored deployment spec."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    if driver.is_known(instance_id):
        try:
            await driver.stop(instance_id)
        except DriverError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    spec = LaunchSpec(
        instance_id=instance_id,
        deployment_id=str(body.get("deployment_id") or ""),
        core_version=str(body.get("core_version") or "latest"),
        api_token=body.get("core_api_token") or secrets.token_urlsafe(24),
        public_host=str(body.get("public_host") or ""),
        cpu_limit=float(body.get("cpu_limit") or 0.5),
        memory_mb=int(body.get("memory_mb") or 256),
        max_processes=int(body.get("max_processes") or 128),
    )
    try:
        handle = await driver.launch(spec)
    except DriverError as exc:
        raise HTTPException(status_code=502, detail=f"restart failed: {exc}")
    registry.save_instance(instance_id, {
        "deployment_id": spec.deployment_id,
        "core_version": spec.core_version,
        "api_token": spec.api_token,
        "public_host": spec.public_host,
        "cpu_limit": spec.cpu_limit,
        "memory_mb": spec.memory_mb,
        "max_processes": spec.max_processes,
        "port": handle.port,
    })
    return {"ok": True, "instance_id": instance_id, "port": handle.port, "driver": driver.name}


@app.post("/worker/api/instances/{instance_id}/remove")
async def remove_instance(instance_id: str, _=Depends(require_worker_token)):
    try:
        await driver.remove(instance_id)
    except DriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    registry.remove(instance_id)
    return {"ok": True}


@app.get("/worker/api/instances/{instance_id}/status")
async def instance_status(instance_id: str, _=Depends(require_worker_token)):
    try:
        status = await driver.status(instance_id)
    except DriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if status.get("running"):
        probe = await probe_core(status["port"], "")  # health endpoint needs no token
        status["core_health"] = probe
        status["healthy"] = probe is not None
    return status


@app.get("/worker/api/instances/{instance_id}/logs")
async def instance_logs(instance_id: str, tail: int = 200, _=Depends(require_worker_token)):
    return {"logs": await driver.logs(instance_id, tail=max(1, min(tail, 1000)))}


@app.api_route("/worker/api/instances/{instance_id}/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def instance_proxy(instance_id: str, path: str, request: Request, _=Depends(require_worker_token)):
    """Internal reverse proxy into an instance's Core (used by the Console for
    its management API calls and by the edge proxy for public traffic)."""
    return await _forward_http(instance_id, path, request)


@app.api_route("/pub/{token}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def direct_http_proxy(token: str, path: str, request: Request):
    """Public, token-authenticated direct entry into this worker's own
    instances — lets clients connect straight to this region instead of
    hairpinning through the console gateway. Only the client-facing
    transport paths are reachable here; the Core management API stays
    behind the bearer-token /proxy route above."""
    if not _is_public_client_path(path):
        raise HTTPException(status_code=404, detail="not found")
    instance_id = decode_direct_token(token, WORKER_TOKEN)
    if instance_id is None:
        raise HTTPException(status_code=404, detail="not found")
    return await _forward_http(instance_id, path, request)


async def _forward_http(instance_id: str, path: str, request: Request):
    try:
        status = await driver.status(instance_id)
    except DriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if not status.get("running"):
        raise HTTPException(status_code=502, detail="instance not running")
    port = status["port"]
    url = httpx.URL(path="/" + path, query=request.url.query.encode())
    origin_ip = _origin_client_ip(request.headers, request.client.host if request.client else None)
    headers = [(k, v) for (k, v) in request.headers.items()
               if k.lower() not in ("host", "content-length", "authorization",
                                    "x-forwarded-for", "x-real-ip")]
    # Set authoritatively rather than passing through whatever the client
    # sent: Core's per-link device cap keys off this IP, so a missing or
    # attacker-controlled value here silently disables that cap for every
    # customer (see _origin_client_ip).
    headers.append(("X-Forwarded-For", origin_ip))
    headers.append(("X-Real-Ip", origin_ip))
    # Translate auth: the worker token got us in; the Core expects its own
    # instance token (stored at launch time).
    handle = driver.handles.get(instance_id)
    if handle is not None and handle.meta.get("api_token"):
        headers.append(("Authorization", f"Bearer {handle.meta['api_token']}"))
    # Stream client transport traffic both directions: xHTTP downlinks are
    # long-lived streams that never "complete", and an xHTTP stream-up
    # *upload* stays open for the whole session — reading it to the end
    # first (await request.body()) would park the request here forever and
    # the client would just time out. Core's own management API
    # (core/api/*, used by the Console — short, complete JSON bodies) is
    # buffered instead: streaming a tiny body as chunked transfer-encoding
    # was leaving Core's connection closed before the response finished,
    # surfacing as httpx.RemoteProtocolError on every one of these calls.
    content = request.stream() if _is_public_client_path(path) else await request.body()
    client = httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{port}",
        timeout=httpx.Timeout(connect=10.0, read=None, write=None, pool=None),
    )
    try:
        up_req = client.build_request(
            request.method, url, headers=headers,
            content=content,
        )
        upstream = await client.send(up_req, stream=True)
        from starlette.background import BackgroundTask

        async def _cleanup():
            await upstream.aclose()
            await client.aclose()

        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers={k: v for k, v in upstream.headers.items()
                     if k.lower() not in ("content-length", "transfer-encoding", "connection")},
            background=BackgroundTask(_cleanup),
        )
    except httpx.HTTPError:
        await client.aclose()
        raise HTTPException(status_code=502, detail="upstream unavailable")


@app.websocket("/worker/api/instances/{instance_id}/ws-proxy/{path:path}")
async def instance_ws_proxy(ws: WebSocket, instance_id: str, path: str):
    """WebSocket relay into an instance's Voidz Core (authenticated via the
    worker token passed as query param, since browsers cannot set headers
    on WebSocket connects)."""
    # Accept first so later rejections carry proper close codes instead of
    # Starlette's generic HTTP 403 rejection.
    await ws.accept()
    token = ws.query_params.get("token", "")
    if not token or not secrets.compare_digest(token, WORKER_TOKEN):
        await ws.close(code=1008, reason="unauthorized")
        return
    await _forward_ws(instance_id, path, ws)


@app.websocket("/pub/{token}/{path:path}")
async def direct_ws_proxy(ws: WebSocket, token: str, path: str):
    """Public, token-authenticated direct WebSocket entry into this worker's
    own instances — the actual VLESS/Trojan/Shadowsocks data path clients
    use once they have a direct-region config. Same path allowlist as the
    HTTP counterpart: nothing under Core's management API is reachable here."""
    await ws.accept()
    if not _is_public_client_path(path):
        await ws.close(code=1008, reason="not found")
        return
    instance_id = decode_direct_token(token, WORKER_TOKEN)
    if instance_id is None:
        await ws.close(code=1008, reason="not found")
        return
    await _forward_ws(instance_id, path, ws)


async def _forward_ws(instance_id: str, path: str, ws: WebSocket) -> None:
    import websockets as ws_lib

    try:
        status = await driver.status(instance_id)
    except DriverError:
        await ws.close(code=1014, reason="unknown instance")
        return
    if not status.get("running"):
        await ws.close(code=1014, reason="instance not running")
        return

    upstream_url = f"ws://127.0.0.1:{status['port']}/{path}"
    origin_ip = _origin_client_ip(ws.headers, ws.client.host if ws.client else None)
    headers = {"user-agent": ws.headers.get("user-agent", "")}
    # Set authoritatively — see _origin_client_ip: Core's per-link device cap
    # keys off this IP, so this must never be a passthrough of a possibly
    # absent or client-forged header.
    headers["x-forwarded-for"] = origin_ip
    headers["x-real-ip"] = origin_ip
    # Carry Core's own close code/reason back to the client. Without this every
    # rejection (bad credential, device limit, quota) reaches the client as a
    # plain 1000, which makes a refused connection indistinguishable from a
    # finished one.
    close_code, close_reason = 1000, ""
    try:
        async with ws_lib.connect(upstream_url, additional_headers=headers, max_size=None,
                                  ping_interval=20, ping_timeout=20) as upstream:
            async def c2u():
                try:
                    while True:
                        msg = await ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            return
                        data = msg.get("bytes")
                        if data is not None:
                            await upstream.send(data)
                        else:
                            text = msg.get("text")
                            if text is not None:
                                await upstream.send(text)
                except Exception:
                    return

            async def u2c():
                try:
                    async for message in upstream:
                        if isinstance(message, (bytes, bytearray)):
                            await ws.send_bytes(bytes(message))
                        else:
                            await ws.send_text(message)
                except Exception:
                    return

            done, pending = await asyncio.wait(
                {asyncio.create_task(c2u()), asyncio.create_task(u2c())},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            if upstream.close_code:
                close_code = upstream.close_code
                close_reason = upstream.close_reason or ""
    except Exception:
        try:
            await ws.close(code=1014, reason="upstream unavailable")
        except Exception:
            pass
        return
    finally:
        try:
            await ws.close(code=close_code, reason=close_reason)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Node metrics + heartbeat
# ---------------------------------------------------------------------------
def node_metrics() -> dict:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(DATA_ROOT if DATA_ROOT.exists() else "/"))
    return {
        "node_id": NODE_ID,
        "region": NODE_REGION,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(logical=True),
        "mem_used_mb": round(vm.used / (1024 * 1024)),
        "mem_total_mb": round(vm.total / (1024 * 1024)),
        "disk_used_gb": round(disk.used / (1024 ** 3), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
        "instances": len(driver.known_instances()),
        "capacity_instances": int(os.environ.get("VOIDZ_NODE_CAPACITY", "20")),
        "driver": driver.name,
        "ts": time.time(),
    }


@app.get("/worker/api/metrics")
async def metrics(_=Depends(require_worker_token)):
    return node_metrics()


async def heartbeat_loop() -> None:
    if not CONSOLE_URL:
        log.info("heartbeat disabled (VOIDZ_CONSOLE_URL not set)")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                resp = await client.post(
                    f"{CONSOLE_URL}/api/internal/heartbeat",
                    json=node_metrics(),
                    headers={"Authorization": f"Bearer {CONSOLE_HEARTBEAT_TOKEN or WORKER_TOKEN}"},
                )
                if resp.status_code != 200:
                    log.warning("heartbeat rejected: %s", resp.status_code)
            except (httpx.HTTPError, OSError) as exc:
                log.warning("heartbeat failed: %s", type(exc).__name__)
            await asyncio.sleep(HEARTBEAT_INTERVAL)


@app.on_event("startup")
async def _startup() -> None:
    global driver
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    driver, _name = select_driver(DATA_ROOT)
    log.info("Voidz Worker %s on node=%s region=%s driver=%s", worker_info()["version"], NODE_ID, NODE_REGION, driver.name)
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(_relaunch_known_instances())


async def _relaunch_known_instances() -> None:
    """Pod restarts kill managed Core processes; relaunch everything the
    registry knows about with identical credentials."""
    for iid, rec in registry.load().items():
        if driver.is_known(iid):
            continue
        try:
            spec = LaunchSpec(
                instance_id=iid,
                deployment_id=str(rec.get("deployment_id") or ""),
                core_version=str(rec.get("core_version") or "latest"),
                api_token=str(rec.get("api_token") or secrets.token_urlsafe(24)),
                public_host=str(rec.get("public_host") or ""),
                cpu_limit=float(rec.get("cpu_limit") or 0.5),
                memory_mb=int(rec.get("memory_mb") or 256),
                max_processes=int(rec.get("max_processes") or 128),
                port=int(rec.get("port") or 0) or None,
            )
            await driver.launch(spec)
            log.info("relaunched instance %s after restart", iid[:12])
        except Exception as exc:
            log.warning("relaunch failed for %s: %s", iid[:12], exc)
