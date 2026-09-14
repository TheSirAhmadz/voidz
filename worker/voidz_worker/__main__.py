"""Voidz Worker entrypoint."""
from __future__ import annotations

import os

import uvicorn

from .logging import setup_logging


def main() -> int:
    setup_logging(os.environ.get("VOIDZ_LOG_LEVEL", "info"))
    uvicorn.run(
        "voidz_worker.main:app",
        host=os.environ.get("VOIDZ_WORKER_HOST", "0.0.0.0"),
        port=int(os.environ.get("VOIDZ_WORKER_PORT", "9100")),
        log_level=os.environ.get("VOIDZ_LOG_LEVEL", "info"),
        workers=1,
        # This is the hop real clients connect to directly (/pub/...). A
        # client that vanishes without a clean close (dead network, app
        # killed, phone dropping wifi) otherwise sits registered — holding
        # its device slot — until uvicorn's default keepalive notices,
        # which can take up to ~40s. Tightened so a dead device's slot
        # frees up within a few seconds instead.
        ws="websockets",
        ws_ping_interval=5.0,
        ws_ping_timeout=5.0,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
