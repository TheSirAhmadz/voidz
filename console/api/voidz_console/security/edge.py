"""Real client IP resolution when a Cloudflare Worker sits in front of this
service, hiding the Railway domain from clients.

Mirrors worker/voidz_worker/main.py's _origin_client_ip — see that
docstring for the full rationale. Short version: X-Voidz-Real-IP is only
trusted alongside a matching X-Voidz-Edge-Secret, since that header isn't
one Railway's own edge touches — without the secret check, anyone hitting
this service's raw Railway domain directly (bypassing the Cloudflare
Worker) could set X-Voidz-Real-IP to whatever they want.
"""
from __future__ import annotations

import os
import secrets

EDGE_SECRET = os.environ.get("VOIDZ_EDGE_SECRET", "")


def real_client_ip(headers, direct_host: str | None) -> str:
    if EDGE_SECRET and secrets.compare_digest(headers.get("x-voidz-edge-secret", ""), EDGE_SECRET):
        real_ip = headers.get("x-voidz-real-ip")
        if real_ip:
            return real_ip.strip()
    fwd = headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return direct_host or "unknown"
