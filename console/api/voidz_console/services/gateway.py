"""Instance endpoint gateway.

On platforms that expose a single public HTTP endpoint per deployment
(e.g. Lucity's workload domain with Gateway API HTTPRoutes), every Voidz
instance is reached through the Console's public URL under a private
endpoint token:

    https://<console-host>/i/<endpoint-token>/<core-path>

The gateway authenticates by endpoint token (un guessable, rotatable),
strips the prefix, and proxies HTTP and WebSocket traffic to the instance's
Voidz Core through the Worker. On self-hosted deployments with wildcard DNS
the same instances can additionally be exposed as real hostnames via the
bundled Caddy — both modes share this proxy path.

WebSocket proxying is implemented frame-by-frame (client ⇄ gateway ⇄ core)
because the standard HTTP client stack cannot pass an Upgrade through.
"""
from __future__ import annotations

import asyncio
import httpx
import websockets
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..db import get_pool
from ..logging import get

log = get("network", "voidz.console.gateway")

_LOGO_B64 = "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"

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
    "authorization",  # replaced with the worker token below
}

# Client-facing transport paths Core actually exposes (core/voidz_core/app.py):
# ws/{uuid} (VLESS), trojan-ws, ss-ws, xhttp packet-up/stream-up/downlink.
# The endpoint token only proves "this is a legitimate subscriber of this
# instance" — it must never be enough to reach Core's own management API
# (core/api/*), which would let any subscriber list/edit/delete every
# customer's credentials on that instance. Only the worker-token-authed
# internal proxy (called by the Console itself, e.g. services/quota.py) may
# reach those paths.
def _is_public_client_path(path: str) -> bool:
    return (path in ("trojan-ws", "ss-ws")
            or path.startswith(("ws/", "xhttp-siz10/", "txhttp-siz10/")))


def _public_host() -> str | None:
    """The console's own public domain when VOIDZ_PUBLIC_URL is set (e.g. a
    Cloudflare Worker fronting Railway to hide it from clients). Without
    this, the sub page's displayed/import host falls back to whatever Host
    header the request happened to arrive with — which, once a proxying
    edge sits in front of this service and doesn't forward the original
    Host, silently reverts to the hidden origin domain."""
    import os

    url = os.environ.get("VOIDZ_PUBLIC_URL", "").strip()
    if not url:
        return None
    return url.split("://", 1)[-1].split(":")[0].split("/")[0] or None


def _page(title: str, body: str, status: int = 200, icon: str | None = None,
          tone: str | None = None) -> "HTMLResponse":
    from fastapi.responses import HTMLResponse

    from .sub_page import render_notice

    return HTMLResponse(render_notice(title, body, status, _LOGO_B64, icon_name=icon, tone=tone),
                        status_code=status)


def _sub_html_page(title: str, configs: list, host: str, sub_path: str,
                   qr_path: str = "", info: dict | None = None) -> str:
    from .sub_page import render_subscription_page

    return render_subscription_page(title=title, configs=configs, host=host, sub_path=sub_path,
                                    logo_b64=_LOGO_B64, qr_endpoint=qr_path, info=info)

def _singbox_outbound(url: str) -> dict:
    """vless:// / trojan:// URI -> sing-box outbound. Shadowsocks links pass
    through parsed minimally; unsupported schemes are skipped by caller."""
    import base64 as _b64u
    from urllib.parse import urlparse, parse_qs, unquote

    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    tag = unquote(u.fragment) or "voidz"
    common = {"tag": tag}
    if u.scheme in ("vless", "trojan"):
        inner = {
            "server": u.hostname or "",
            "server_port": u.port or 443,
            "uuid": u.username or "" if u.scheme == "vless" else None,
            "password": u.username or "" if u.scheme == "trojan" else None,
            "tls": {
                "enabled": q.get("security") == "tls",
                "server_name": q.get("sni") or u.hostname or "",
                "utls": {"enabled": True, "fingerprint": q.get("fp", "chrome")} if q.get("fp") else None,
            },
            "transport": {
                "type": "ws",
                "path": q.get("path", "/"),
                "headers": {"Host": q.get("host") or u.hostname or ""},
            } if q.get("type") == "ws" else None,
        }
        common["type"] = u.scheme
        out = {k: v for k, v in inner.items() if v is not None}
        tls = out.get("tls") or {}
        if tls.get("utls") is None:
            tls.pop("utls", None)
        if out.get("transport") is None:
            out.pop("transport", None)
        out.update(common)
        return out
    if u.scheme == "ss":
        userinfo = u.username or ""
        pad = "=" * (-len(userinfo) % 4)
        try:
            method, password = _b64u.b64decode(userinfo + pad).decode().split(":", 1)
        except Exception:
            method, password = "aes-256-gcm", ""
        return {"type": "shadowsocks", "tag": tag, "server": u.hostname or "",
                "server_port": u.port or 443, "method": method, "password": password}
    return {"type": u.scheme, "tag": tag}


def _clash_proxy(url: str) -> dict | None:
    """vless/trojan URI -> Clash Meta proxy map (vless needs Meta)."""
    from urllib.parse import urlparse, parse_qs, unquote

    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    name = unquote(u.fragment) or "voidz"
    if u.scheme == "vless":
        return {"name": name, "type": "vless", "server": u.hostname or "",
                "port": u.port or 443, "uuid": u.username or "",
                "udp": True, "tls": q.get("security") == "tls",
                "servername": q.get("sni") or u.hostname or "",
                "client-fingerprint": q.get("fp", "chrome"),
                "network": "ws", "ws-opts": {"path": q.get("path", "/"),
                "headers": {"Host": q.get("host") or u.hostname or ""}}}
    if u.scheme == "trojan":
        return {"name": name, "type": "trojan", "server": u.hostname or "",
                "port": u.port or 443, "password": u.username or "",
                "udp": True, "sni": q.get("sni") or u.hostname or "",
                "client-fingerprint": q.get("fp", "chrome"),
                "network": "ws", "ws-opts": {"path": q.get("path", "/"),
                "headers": {"Host": q.get("host") or u.hostname or ""}}}
    if u.scheme == "ss":
        import base64 as _b64u

        pad = "=" * (-len(u.username or "") % 4)
        try:
            method, password = _b64u.b64decode((u.username or "") + pad).decode().split(":", 1)
        except Exception:
            return None
        return {"name": name, "type": "ss", "server": u.hostname or "",
                "port": u.port or 443, "cipher": method, "password": password}
    return None


def _clash_quote(s: str) -> str:
    return '"' + s.replace('"', '\\"') + '"'


def _clash_inline(p: dict) -> str:
    import json as _json

    return _json.dumps(p, ensure_ascii=False)


router = APIRouter(include_in_schema=False)


async def _resolve_endpoint(request: Request, token: str) -> dict | None:
    """endpoint token -> {instance_id, worker_url, status}"""
    pool = get_pool(request)
    from ..config import settings as _s
    from ..security.token_codec import decode_token

    log.info("resolve enter: token[:20]=%s", token[:20])
    instance_id = decode_token(token, _s.secret_key)
    log.info("resolve: token[:16]=%s decoded=%s", token[:16], instance_id)
    if instance_id is not None:
        row = await pool.fetchrow(
            """
            SELECT i.id, i.status,
                   (SELECT d.domain FROM domains d WHERE d.instance_id = i.id
                     AND d.is_active = TRUE AND d.kind = 'path'
                     ORDER BY d.created_at DESC LIMIT 1) AS endpoint_token,
                   (SELECT dep.node_id FROM deployments dep WHERE dep.instance_id = i.id
                     ORDER BY dep.started_at DESC LIMIT 1) AS node_id
            FROM instances i WHERE i.id = $1
            """,
            instance_id,
        )
    else:
        row = await pool.fetchrow(
            """
            SELECT i.id, i.status,
                   (SELECT d.domain FROM domains d WHERE d.instance_id = i.id
                     AND d.is_active = TRUE AND d.kind = 'path'
                     ORDER BY d.created_at DESC LIMIT 1) AS endpoint_token,
                   (SELECT dep.node_id FROM deployments dep WHERE dep.instance_id = i.id
                     ORDER BY dep.started_at DESC LIMIT 1) AS node_id
            FROM instances i
            WHERE i.id IN (SELECT instance_id FROM domains
                            WHERE kind = 'path' AND domain = $1 AND is_active = TRUE)
            """,
            token,
        )
    if row is not None and row["endpoint_token"] is None:
        row = None
    if row is None or row["status"] != "running":
        log.info("resolve MISS: decoded=%s row=%s status=%s", instance_id,
                 row is not None, row["status"] if row else None)
        return None
    from ..services.workers import worker_url_for

    return {
        "instance_id": str(row["id"]),
        "node_id": row["node_id"] or "local",
        "worker_url": worker_url_for(row["node_id"] or "local"),
        "upstream": f"/worker/api/instances/{row['id']}/proxy",
    }


@router.get("/i/{token}")
async def instance_status_page(token: str, request: Request):
    """Browser-friendly view of a proxy endpoint (the path itself is for
    proxy clients, not people)."""
    target = await _resolve_endpoint(request, token)
    if target is None:
        return _page(
            "Endpoint not found",
            "This endpoint doesn't exist or its instance was removed. "
            "If you recently redeployed Voidz without a persistent volume, "
            "create a new instance in the panel and copy its fresh config "
            "from the <b>Config</b> tab.",
            status=404,
        )
    return _page(
        "This endpoint is live",
        "This address is the private transport path for your proxy client. "
        "There is no web page here. Open the Voidz panel, choose your "
        "instance, open the <b>Config</b> tab and copy the "
        "<code>vless://</code> link into your client (v2rayNG, NekoBox, "
        "Streisand, …).",
    )


@router.post("/i/{token}/api/qr")
async def instance_qr_public(token: str, request: Request):
    """QR (SVG) for the subscription page — authorized by the endpoint token."""
    import io

    import qrcode
    import qrcode.image.svg
    from fastapi.responses import Response as _Response

    target = await _resolve_endpoint(request, token)
    if target is None:
        raise HTTPException(status_code=404, detail="unknown endpoint")
    body = await request.json()
    text = str(body.get("text") or "")[:4096]
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return _Response(content=buf.getvalue(), media_type="image/svg+xml")


@router.get("/i/{token}/sub")
async def instance_subscription(token: str, request: Request):
    """Subscription: ALL protocols of this instance. Auth = endpoint token.
    Formats via ?fmt=: singbox | clash | (default) base64 v2ray list.
    Content host: ?host=, panel-announced host, or request host."""
    import base64 as _b64

    import httpx as _httpx

    from ..config import settings as _settings

    fmt = (request.query_params.get("fmt") or "").strip().lower()

    target = await _resolve_endpoint(request, token)
    if target is None:
        return _page(
            "Endpoint not found",
            "This subscription doesn't exist or its instance was removed. "
            "Create a new instance in the Voidz panel and copy its "
            "subscription URL from the Config tab.",
            status=404,
        )
    pool = get_pool(request)
    inst = await pool.fetchrow(
        "SELECT name, public_host, status FROM instances WHERE id = $1", target["instance_id"]
    )
    if inst is None or inst["status"] != "running":
        return _page("Instance not running",
                     "The subscription will work once the instance is running.", status=503)
    host = (request.query_params.get("host")
            or inst["public_host"]
            or _public_host()
            or (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
            or request.headers.get("host") or "").split(":")[0]
    if not host:
        return _page("Missing host", "Append ?host=<your-domain> to this URL.", status=400)

    from ..security import direct_token
    from ..services.workers import worker_public_base

    direct_base = worker_public_base(target["node_id"])
    if direct_base:
        share_host = direct_base.split("://", 1)[-1].split(":")[0]
        share_prefix = f"/pub/{direct_token.encode(target['instance_id'], _settings.worker_token)}"
    else:
        share_host, share_prefix = host, f"/i/{token}"
    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{target['worker_url'].rstrip('/')}{target['upstream']}/core/api/share",
                json={"host": share_host, "path_prefix": share_prefix, "uuids": []},
                headers={"Authorization": f"Bearer {_settings.worker_token}",
                         "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            configs = [c for c in resp.json().get("links", []) if c.get("share_url")]
            links = [c["share_url"] for c in configs]
    except Exception as exc:
        return _page("Unavailable", f"Could not read the instance configs: {str(exc)[:160]}",
                     status=502)
    title = f"Voidz \u00b7 {inst['name']}"
    from fastapi.responses import Response as _Response

    # ── Browser detection: HTML page for people, raw payload for clients ──
    # DEFAULT IS RAW: proxy clients (v2rayN, v2rayNG, Happ, …) may send
    # browser-like or empty User-Agents, so UA guessing alone would feed them
    # the HTML page and break imports. HTML is served only when the request
    # looks like a real web browser: Mozilla-style UA *and* "Accept:
    # text/html" (browsers always send both; proxy clients never do).
    # Explicit ?fmt= always forces raw data.
    ua = (request.headers.get("user-agent") or "").lower()
    accept = (request.headers.get("accept") or "").lower()
    looks_like_browser = "mozilla" in ua and "text/html" in accept

    if looks_like_browser and not fmt:
        from fastapi.responses import HTMLResponse

        return HTMLResponse(_sub_html_page(title, configs, host, f"/i/{token}/sub",
                                           qr_path=f"/i/{token}/api/qr"))

    def _headers(extra: dict | None = None) -> dict:
        h = {
            "profile-title": "base64:" + _b64.b64encode(title.encode()).decode(),
            "subscription-userinfo": "upload=0; download=0; total=0; expire=0",
            "profile-update-interval": "24",
            "profile-web-page-url": f"{request.url.scheme}://{request.headers.get('host', host)}",
        }
        if extra:
            h.update(extra)
        return h

    # Format negotiation:
    #   ?fmt=singbox  -> sing-box JSON (Outbounds)
    #   ?fmt=clash    -> Clash YAML (proxies)
    #   default       -> base64 v2ray list (v2rayNG, NekoBox, Streisand)
    if fmt in ("singbox", "sing-box", "sb"):
        import json as _json

        outbounds = [_singbox_outbound(u) for u in links]
        payload = _json.dumps({"outbounds": outbounds}, ensure_ascii=False, indent=2)
        return _Response(content=payload, media_type="application/json",
                         headers=_headers({"subscription-userinfo": "upload=0; download=0; total=0; expire=0"}))

    if fmt in ("clash", "clash-meta", "yaml"):
        proxies = [_clash_proxy(u) for u in links]
        proxies = [p for p in proxies if p]
        names = [p["name"] for p in proxies]
        payload = (
            "port: 7890\nsocks-port: 7891\nallow-lan: false\nmode: rule\nlog-level: warning\n"
            "proxies:\n"
            + "\n".join("  - " + _clash_inline(p) for p in proxies)
            + "\nproxy-groups:\n  - name: Voidz\n    type: select\n    proxies:\n"
            + "".join(f"      - {_clash_quote(n)}\n" for n in names)
            + "rules:\n  - MATCH,Voidz\n"
        )
        return _Response(content=payload, media_type="text/yaml", headers=_headers())

    body = _b64.b64encode("\n".join(links).encode()).decode()
    return _Response(content=body, media_type="text/plain", headers=_headers())


@router.post("/sub/{sub_token}/qr")
async def plan_subscription_qr(sub_token: str, request: Request):
    """QR (SVG) for the subscription page, generated on demand so the page
    itself doesn't ship one per config. Authorized by an active sub token."""
    from fastapi.responses import Response as _Response

    from .sub_page import qr_svg

    pool = get_pool(request)
    active = await pool.fetchval(
        "SELECT active FROM customers WHERE sub_token = $1", sub_token
    )
    if not active:
        raise HTTPException(status_code=404, detail="unknown subscription")
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="json body required")
    text = str(body.get("text") or "") if isinstance(body, dict) else ""
    if not text or len(text) > 4096:
        raise HTTPException(status_code=400, detail="text required (max 4096 chars)")
    return _Response(content=qr_svg(text), media_type="image/svg+xml",
                     headers={"Cache-Control": "private, max-age=3600"})


@router.get("/sub/{sub_token}")
async def plan_subscription(sub_token: str, request: Request):
    """Multi-region subscription: one config per region in the customer's
    plan, sharing one pooled quota/expiry enforced by services/quota.py.
    Same UA-sniffing / ?fmt= negotiation as /i/{token}/sub."""
    import base64 as _b64
    from datetime import datetime, timezone

    from ..services import workers as worker_svc
    from ..services.workers import worker_url_for

    fmt = (request.query_params.get("fmt") or "").strip().lower()
    pool = get_pool(request)
    cust = await pool.fetchrow(
        "SELECT c.*, p.name AS plan_name FROM customers c JOIN plans p ON p.id = c.plan_id "
        "WHERE c.sub_token = $1",
        sub_token,
    )
    if cust is None or not cust["active"]:
        return _page(
            "Endpoint not found",
            "This subscription doesn't exist or has been revoked. Contact "
            "whoever gave you this link for a new one.",
            status=404,
        )
    now = datetime.now(timezone.utc)
    if cust["expires_at"] and cust["expires_at"] < now:
        return _page("Subscription expired",
                     "This subscription's time has run out. Contact whoever "
                     "gave you this link to renew it.", status=403, icon="clock")
    if cust["limit_bytes"] and cust["used_bytes_cached"] >= cust["limit_bytes"]:
        return _page("Data limit reached",
                     "This subscription has used all of its allotted data. "
                     "Contact whoever gave you this link to top it up.", status=403, icon="data")

    pi_rows = await pool.fetch(
        "SELECT pi.instance_id, pi.region_label, i.status, "
        "(SELECT dep.node_id FROM deployments dep WHERE dep.instance_id = i.id "
        " ORDER BY dep.started_at DESC LIMIT 1) AS node_id, "
        "(SELECT d.domain FROM domains d WHERE d.instance_id = i.id "
        " AND d.kind = 'path' AND d.is_active = TRUE ORDER BY d.created_at DESC LIMIT 1) AS endpoint_token "
        "FROM plan_instances pi JOIN instances i ON i.id = pi.instance_id "
        "WHERE pi.plan_id = $1 ORDER BY pi.position",
        cust["plan_id"],
    )
    host = (request.query_params.get("host")
            or _public_host()
            or (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
            or request.headers.get("host") or "").split(":")[0]
    if not host:
        return _page("Missing host", "Append ?host=<your-domain> to this URL.", status=400)

    from ..services.quota import _link_uuid

    plan_protocols_str = await pool.fetchval("SELECT protocols FROM plans WHERE id = $1", cust["plan_id"])
    plan_protocols = [p for p in (plan_protocols_str or "").split(",") if p]
    wanted_uuids = [_link_uuid(cust["cred_uuid"], proto) for proto in plan_protocols]

    from ..config import settings as _settings
    from ..security import direct_token
    from ..services.workers import worker_public_base

    configs = []
    for pi in pi_rows:
        if pi["status"] != "running" or not pi["endpoint_token"]:
            continue
        node_id = pi["node_id"] or "local"
        worker_url = worker_url_for(node_id)
        # Direct-region path: when this instance's worker has its own public
        # domain, point the client straight at it instead of hairpinning
        # through this console — every region otherwise shares this one
        # entry point, which makes them all measure identical latency no
        # matter which region a config claims to be.
        direct_base = worker_public_base(node_id)
        if direct_base:
            share_host = direct_base.split("://", 1)[-1].split(":")[0]
            share_prefix = f"/pub/{direct_token.encode(pi['instance_id'], _settings.worker_token)}"
        else:
            share_host, share_prefix = host, f"/i/{pi['endpoint_token']}"
        try:
            data = await worker_svc.worker_call(
                worker_url, "POST",
                f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/share",
                {"host": share_host, "path_prefix": share_prefix,
                 "uuids": wanted_uuids},
            )
        except worker_svc.WorkerError:
            continue
        for c in data.get("links", []):
            if c.get("share_url"):
                c["region"] = pi["region_label"]
                configs.append(c)

    if not configs:
        return _page("No locations available right now",
                     "None of this subscription's locations are currently "
                     "reachable. Try again shortly.", status=503)

    links = [c["share_url"] for c in configs]
    title = f"Voidz · {cust['name']}"

    ua = (request.headers.get("user-agent") or "").lower()
    accept = (request.headers.get("accept") or "").lower()
    looks_like_browser = "mozilla" in ua and "text/html" in accept
    if looks_like_browser and not fmt:
        from fastapi.responses import HTMLResponse

        device_ips: set[str] = set()
        wanted_str = ",".join(wanted_uuids)
        for pi in pi_rows:
            if pi["status"] != "running":
                continue
            worker_url = worker_url_for(pi["node_id"] or "local")
            try:
                conn_data = await worker_svc.worker_call(
                    worker_url, "GET",
                    f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/connections?uuids={wanted_str}",
                )
            except worker_svc.WorkerError:
                continue
            for conn in conn_data.get("connections", []):
                if conn.get("ip"):
                    device_ips.add(conn["ip"])

        limit_bytes = int(cust["limit_bytes"] or 0)
        used_bytes = int(cust["used_bytes_cached"] or 0)

        no_expiry = cust["expires_at"] is None
        hours_left = hours_total = None
        if not no_expiry:
            hours_left = max(0.0, (cust["expires_at"] - now).total_seconds() / 3600)
            hours_total = max(0.01, (cust["expires_at"] - cust["created_at"]).total_seconds() / 3600)
        info = {
            "used_gb": used_bytes / (1024 ** 3),
            "total_gb": (limit_bytes / (1024 ** 3)) if limit_bytes else None,
            "pct": (used_bytes / limit_bytes * 100) if limit_bytes else 0,
            "hours_left": hours_left,
            "hours_total": hours_total,
            "no_expiry": no_expiry,
            "online_count": len(device_ips),
            "max_devices": int(cust["max_devices"] or 0),
            "expires_at": cust["expires_at"],
            "plan_name": cust["plan_name"],
        }
        return HTMLResponse(_sub_html_page(title, configs, host, f"/sub/{sub_token}",
                                           qr_path=f"/sub/{sub_token}/qr", info=info))

    def _headers(extra: dict | None = None) -> dict:
        expire_ts = int(cust["expires_at"].timestamp()) if cust["expires_at"] else 0
        h = {
            "profile-title": "base64:" + _b64.b64encode(title.encode()).decode(),
            "subscription-userinfo": (
                f"upload=0; download={int(cust['used_bytes_cached'])}; "
                f"total={int(cust['limit_bytes'])}; expire={expire_ts}"
            ),
            "profile-update-interval": "6",
            "profile-web-page-url": f"{request.url.scheme}://{request.headers.get('host', host)}",
        }
        if extra:
            h.update(extra)
        return h

    from fastapi.responses import Response as _Response

    if fmt in ("singbox", "sing-box", "sb"):
        import json as _json

        outbounds = [_singbox_outbound(u) for u in links]
        payload = _json.dumps({"outbounds": outbounds}, ensure_ascii=False, indent=2)
        return _Response(content=payload, media_type="application/json", headers=_headers())

    if fmt in ("clash", "clash-meta", "yaml"):
        proxies = [_clash_proxy(u) for u in links]
        proxies = [p for p in proxies if p]
        names = [p["name"] for p in proxies]
        payload = (
            "port: 7890\nsocks-port: 7891\nallow-lan: false\nmode: rule\nlog-level: warning\n"
            "proxies:\n"
            + "\n".join("  - " + _clash_inline(p) for p in proxies)
            + "\nproxy-groups:\n  - name: Voidz\n    type: select\n    proxies:\n"
            + "".join(f"      - {_clash_quote(n)}\n" for n in names)
            + "rules:\n  - MATCH,Voidz\n"
        )
        return _Response(content=payload, media_type="text/yaml", headers=_headers())

    body = _b64.b64encode("\n".join(links).encode()).decode()
    return _Response(content=body, media_type="text/plain", headers=_headers())


@router.api_route("/i/{token}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def instance_http_gateway(token: str, path: str, request: Request):
    if not _is_public_client_path(path):
        return _page("Not found", "This path isn't a valid proxy endpoint.", status=404)
    target = await _resolve_endpoint(request, token)
    if target is None:
        return _page(
            "Endpoint not found",
            "This endpoint doesn't exist or its instance is not running. "
            "Check the panel: if the instance is Running, copy the fresh "
            "config from its <b>Config</b> tab.",
            status=404,
        )

    worker_url = target["worker_url"].rstrip("/")
    url = f"{worker_url}{target['upstream']}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"
    headers = [(k, v) for k, v in request.headers.items()
              if k.lower() not in HOP_BY_HOP
              and k.lower() not in ("x-forwarded-for", "x-real-ip", "x-voidz-real-ip", "x-voidz-edge-secret")]
    # Set authoritatively rather than passing through whatever the client
    # sent: Core's per-link device cap keys off this IP. See security/edge.py
    # for why X-Voidz-Real-IP (when this console itself sits behind a
    # Cloudflare Worker) is trusted ahead of request.client.
    from ..security.edge import real_client_ip

    origin_ip = real_client_ip(request.headers, request.client.host if request.client else None)
    headers.append(("X-Forwarded-For", origin_ip))
    headers.append(("X-Real-Ip", origin_ip))
    headers.append(("X-Voidz-Endpoint", token))
    from ..config import settings as _cfg

    headers.append(("Authorization", f"Bearer {_cfg.worker_token}"))

    client = httpx.AsyncClient(timeout=None)
    try:
        # Stream both ways. An xHTTP stream-up upload never ends while the
        # session lives, so buffering the request body here would hang it;
        # xHTTP downlinks are equally open-ended in the other direction.
        upstream_req = client.build_request(
            request.method, url, headers=headers, content=request.stream(),
        )
        upstream_resp = await client.send(upstream_req, stream=True)
        return StreamingResponse(
            upstream_resp.aiter_raw(),
            status_code=upstream_resp.status_code,
            headers={k: v for k, v in upstream_resp.headers.items()
                     if k.lower() not in HOP_BY_HOP},
            background=_close_client(client, upstream_resp),
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="instance upstream unavailable")


def _close_client(client: httpx.AsyncClient, resp):
    from starlette.background import BackgroundTask

    async def _cleanup() -> None:
        await resp.aclose()
        await client.aclose()

    return BackgroundTask(_cleanup)


@router.websocket("/i/{token}/{path:path}")
async def instance_ws_gateway(ws: WebSocket, token: str, path: str):
    """Frame-level WebSocket relay into the instance's Voidz Core.

    Accept the client up front (so failures produce proper close codes, not
    Starlette's HTTP 403 rejection), then open the upstream through the
    worker's ws-proxy and pump frames in both directions.
    """
    await ws.accept()
    if not _is_public_client_path(path):
        await ws.close(code=1008, reason="not found")
        return
    try:
        target = await _resolve_endpoint(ws, token)
    except Exception as _exc:
        import traceback as _tb

        log.error("WS resolve failed: %s | %s", _exc, _tb.format_exc()[-400:])
        target = None
    if target is None:
        await ws.close(code=1008, reason="unknown or inactive instance endpoint")
        return

    # Build the upstream ws URL through the worker's websocket proxy
    # (separate route from the HTTP /proxy path).
    worker_ws = target["worker_url"].replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    from ..config import settings as _settings

    upstream_url = (
        f"{worker_ws}/worker/api/instances/{target['instance_id']}/ws-proxy/{path}"
        f"?token={_settings.worker_token}"
    )

    # Set the origin client IP authoritatively rather than passing through
    # whatever the client sent: Core's per-link device cap keys off this
    # value, so a missing or client-forged one silently disables that cap.
    # See security/edge.py for why X-Voidz-Real-IP (when this console
    # itself sits behind a Cloudflare Worker) is trusted ahead of ws.client.
    from ..security.edge import real_client_ip

    origin_ip = real_client_ip(ws.headers, ws.client.host if ws.client else None)
    client_headers = {
        "x-forwarded-for": origin_ip,
        "x-real-ip": origin_ip,
        "user-agent": ws.headers.get("user-agent", ""),
        "x-voidz-endpoint": token,
    }

    try:
        async with websockets.connect(
            upstream_url,
            additional_headers=client_headers,  # type: ignore[arg-type]
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as upstream:
            async def client_to_upstream() -> None:
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
                except (WebSocketDisconnect, Exception):
                    return

            async def upstream_to_client() -> None:
                try:
                    async for message in upstream:
                        if isinstance(message, (bytes, bytearray)):
                            await ws.send_bytes(bytes(message))
                        else:
                            await ws.send_text(message)
                except Exception:
                    return

            done, pending = await asyncio.wait(
                {
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                },
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except (websockets.exceptions.WebSocketException, OSError) as exc:
        log.info("gateway ws upstream failed: %s", type(exc).__name__)
        await ws.close(code=1014, reason="upstream unavailable")
        return
    finally:
        try:
            await ws.close()
        except Exception:
            pass
