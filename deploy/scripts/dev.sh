#!/usr/bin/env bash
# Voidz — local development launcher.
# Starts PostgreSQL check, Console API, Worker, and (optionally) a Core instance.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Defaults (override via env)
export VOIDZ_DATABASE_URL="${VOIDZ_DATABASE_URL:-postgresql://admin:voidz@127.0.0.1:5432/voidz}"
export VOIDZ_SECRET_KEY="${VOIDZ_SECRET_KEY:-dev-secret-key-0123456789abcdef0123456789abcdef}"
export VOIDZ_WORKER_TOKEN="${VOIDZ_WORKER_TOKEN:-dev-worker-token-0123456789abcdef}"
export VOIDZ_GITHUB_CLIENT_ID="${VOIDZ_GITHUB_CLIENT_ID:-}"
export VOIDZ_GITHUB_CLIENT_SECRET="${VOIDZ_GITHUB_CLIENT_SECRET:-}"
export VOIDZ_PUBLIC_URL="${VOIDZ_PUBLIC_URL:-http://127.0.0.1:8080}"
export VOIDZ_LOCAL_WORKER_URL="${VOIDZ_LOCAL_WORKER_URL:-http://127.0.0.1:9100}"
export VOIDZ_WORKER_DATA="${VOIDZ_WORKER_DATA:-/tmp/voidz-dev/instances}"
export PYTHONUNBUFFERED=1

say() { printf '\033[1;36mvoidz-dev\033[0m %s\n' "$1"; }

cleanup() {
  say "shutting down…"
  [ -n "${CONSOLE_PID:-}" ] && kill "$CONSOLE_PID" 2>/dev/null || true
  [ -n "${WORKER_PID:-}" ] && kill "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT

say "starting Console API on :8080"
(cd "$ROOT/console/api" && . .venv/bin/activate && python -m voidz_console) &
CONSOLE_PID=$!

say "starting Worker on :9100 (process driver, dev isolation)"
(cd "$ROOT/worker" && . .venv/bin/activate && \
  PYTHONPATH="$ROOT/core" VOIDZ_WORKER_DRIVER="${VOIDZ_WORKER_DRIVER:-process}" \
  python -m voidz_worker) &
WORKER_PID=$!

say "console  → http://127.0.0.1:8080"
say "worker   → http://127.0.0.1:9100"
say "press Ctrl+C to stop"
wait
