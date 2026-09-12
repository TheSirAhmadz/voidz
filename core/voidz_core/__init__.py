"""Voidz Core — the multi-protocol proxy runtime.

Voidz Core is the server runtime that Voidz instances run. It relays
VLESS / Trojan / Shadowsocks traffic over WebSocket and xHTTP transports,
exposes health/metrics APIs, and is managed remotely by the Voidz Console
through a Voidz Worker.

A library-style package with explicit state boundaries.
"""
