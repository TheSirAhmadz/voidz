"""Entrypoint: ``python -m voidz_core [--config file] [--port N] ...``"""
from __future__ import annotations

import contextlib
import sys

import uvicorn

from .app import Core
from .config import build_config
from .logging import get, setup_logging


def main(argv: list[str] | None = None) -> int:
    try:
        cfg, _ns = build_config(argv)
    except (ValueError, FileNotFoundError) as exc:
        print(f"voidz-core: configuration error: {exc}", file=sys.stderr)
        return 2

    setup_logging(cfg.log_level, cfg.log_json)
    log = get("runtime", "voidz.core")

    core = Core(cfg)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        await core.store.load(core.links, core.stats)
        from .version import info

        log.info(
            "Voidz Core %s (build=%s commit=%s) listening on %s:%d",
            info()["version"], info()["build"], info()["commit"], cfg.host, cfg.port,
        )
        yield
        await core.store.save(core.links, core.stats)
        log.info("Voidz Core shut down cleanly")

    core.app.router.lifespan_context = lifespan

    uvicorn.run(
        core.app,
        host=cfg.host,
        port=cfg.port,
        log_level=cfg.log_level,
        workers=1,
        loop="auto",
        ws="auto",
        # A client that vanishes without a clean close (killed app, dead
        # network, phone switching off wifi) leaves its connection looking
        # "established" — and its device slot held — until the server
        # notices the peer is gone. Uvicorn's own defaults (20s between
        # pings, 20s to wait for a pong) make that up to ~40s; tightened
        # here so a dead device's slot frees up within a few seconds
        # instead of the customer having to wait around a minute for
        # another device to be let in.
        ws_ping_interval=5.0,
        ws_ping_timeout=5.0,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
