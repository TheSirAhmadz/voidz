"""HMAC-authenticated direct-worker endpoint token.

Lets a client connect straight to a worker's own public domain instead of
hairpinning through the console gateway for every packet. The token is
unforgeable proof — over the shared VOIDZ_WORKER_TOKEN secret, already
identical across every worker — that the console minted it for a specific
instance; the worker verifies it locally, no DB or network round-trip
needed. This file is duplicated verbatim in console/api/voidz_console/security/
— it must stay byte-for-byte identical between the two, since one encodes
and the other decodes.
"""
from __future__ import annotations

import hashlib
import hmac

_TAG_LEN = 24  # hex chars (96-bit tag) — plenty against forgery, keeps URLs short


def encode(instance_id: str, worker_token: str) -> str:
    tag = hmac.new(worker_token.encode(), instance_id.encode(), hashlib.sha256).hexdigest()[:_TAG_LEN]
    return f"{instance_id}{tag}"


def decode(token: str, worker_token: str) -> str | None:
    if len(token) <= _TAG_LEN:
        return None
    instance_id, tag = token[:-_TAG_LEN], token[-_TAG_LEN:]
    expected = hmac.new(worker_token.encode(), instance_id.encode(), hashlib.sha256).hexdigest()[:_TAG_LEN]
    if not hmac.compare_digest(tag, expected):
        return None
    return instance_id
