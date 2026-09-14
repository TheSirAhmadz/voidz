"""Voidz Console API entrypoint."""
from __future__ import annotations

import os

import uvicorn

from .logging import setup_logging


def main() -> int:
    setup_logging()
    uvicorn.run(
        "voidz_console.main:app",
        host=os.environ.get("VOIDZ_CONSOLE_HOST", "0.0.0.0"),
        port=int(os.environ.get("VOIDZ_CONSOLE_PORT", os.environ.get("PORT", "8080"))),
        log_level=os.environ.get("VOIDZ_LOG_LEVEL", "info"),
        # The hairpin gateway (instance_ws_gateway) is a client-facing hop
        # too — see worker/voidz_worker/__main__.py for why this matters.
        ws="auto",
        ws_ping_interval=5.0,
        ws_ping_timeout=5.0,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
