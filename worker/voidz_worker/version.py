"""Voidz Worker runtime info."""
from __future__ import annotations

import os

APP_NAME = "Voidz Worker"


def version() -> str:
    return os.environ.get("VOIDZ_WORKER_VERSION", "1.0.0")


def info() -> dict:
    return {
        "name": APP_NAME,
        "version": version(),
        "build": os.environ.get("VOIDZ_WORKER_BUILD", "dev"),
        "node": os.environ.get("VOIDZ_NODE_ID", "local"),
    }
