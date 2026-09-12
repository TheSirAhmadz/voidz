# Voidz

A self-hosted control plane for running your own multi-protocol proxy fleet —
spin up an isolated VLESS/Trojan/Shadowsocks/xHTTP instance from a web UI,
get a share link and a QR code, done. No shell access, no YAML, no Docker
knowledge required on your end.

Everything you see — deploys, health checks, live logs, connection counts —
reflects what is actually running. There is no demo mode and nothing is
faked for the screenshot.

## Why this exists

Most proxy panels are either a single binary you SSH into and hand-edit, or
a heavyweight admin dashboard bolted onto someone else's VPN business. Voidz
is neither: it's a small, three-part system you can fork, read end to end in
an afternoon, and put behind your own domain — built for people who want to
hand a friend a working config in under a minute, not run a hosting company.

## Capabilities

- **Four transports, one engine** — VLESS (WS + xHTTP), Trojan (WS + xHTTP)
  and Shadowsocks AEAD, all sharing one hardened relay core.
- **Real isolation** — every instance is its own process (or container, in
  production), with its own CPU/memory limits, its own credentials, and its
  own endpoint token. One tenant cannot see or touch another's traffic.
- **A console that doesn't lie to you** — the dashboard polls live state:
  deploy progress, per-instance connection lists, resource meters, and a
  searchable/downloadable log terminal.
- **Zero-config by default** — boots on embedded SQLite with a generated
  admin account; attach Postgres and OAuth only when you're ready to.
- **Bring your own infra** — a pluggable worker layer means "where instances
  actually run" is a driver, not a hardcoded assumption.

## How a deploy actually happens

1. You click **Create Instance**, name it, and pick a protocol.
2. The console asks a worker node to launch it and hands back a deployment id.
3. The worker starts the Core process/container and reports back through each
   real stage — `preparing → building → starting → health_check → running`.
4. You get back a per-instance endpoint (and, on capable platforms, a real
   hostname) with automatic TLS. Copy the link, scan the QR, connect.

Nothing here is simulated — a failed health check shows up as **failed**,
with the actual error in the deploy log, not a spinner that eventually times out.

## Getting it running

### Option A — one host, zero setup

Point any platform that runs a Python process at a public port (Railway,
Render, Koyeb, a bare VPS, …) at this repo's root with:

```
start command: python main.py
port:          8080
```

First boot creates an embedded SQLite database and an `admin`/`admin`
account automatically — change the password from **Admin → System** right
after logging in. Handing it a `DATABASE_URL` later migrates it to Postgres;
adding GitHub OAuth credentials turns on social login. See
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the full walkthrough, including
a wildcard-domain self-hosted setup with the bundled Caddy edge.

### Option B — local development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
createdb voidz
VOIDZ_DATABASE_URL=postgresql://admin:voidz@127.0.0.1:5432/voidz \
VOIDZ_GITHUB_CLIENT_ID=... VOIDZ_GITHUB_CLIENT_SECRET=... \
.venv/bin/python main.py
```

Then open `http://127.0.0.1:8080`. To run the console, worker and core as
separate processes with separate virtualenvs instead, use
`deploy/scripts/dev.sh`.

## What's inside

| Component | Lives in | Responsible for |
|---|---|---|
| **Core** | `core/voidz_core` | The actual relay: protocol parsing, the shared quota/session engine, and the management API a worker uses to control one instance. |
| **Console** | `console/api/voidz_console` | Everything user-facing — auth, the deploy pipeline, the admin panel, and the gateway that routes public traffic to the right instance. |
| **Worker** | `worker/voidz_worker` | The thing that actually launches Core processes/containers on a given node and reports their health back. |
| **Deploy tooling** | `deploy/` | Dockerfiles, a docker-compose stack for running all three as separate services, and an optional Caddy edge for wildcard-domain self-hosting. |

## Hardening notes

The relay engine was audited and hardened before anything else was built on
top of it:

- Session identity is now `(link, session_id)`, closing a hijack path where
  one link's xHTTP stream could attach to another link's session.
- Every buffer that used to grow unbounded (packet-up sequence buffers,
  request bodies, per-link/global session counts) now has an explicit cap.
- All four transports run through one adaptive quota gate instead of four
  slightly-different copies of the same logic.
- Logs are redacted at the source — credentials, tokens and UUID keys never
  reach a log line, in memory or on disk.

Full threat model and reporting instructions: [docs/SECURITY.md](docs/SECURITY.md).

## Documentation

| Doc | Covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component boundaries, request flow, data model |
| [docs/API.md](docs/API.md) | Console, Core and Worker HTTP APIs |
| [docs/SECURITY.md](docs/SECURITY.md) | Threat model, security decisions, reporting a vulnerability |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Single-host quick start, Docker self-hosting, wildcard domains |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Prerequisites and manual setup |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Running the test suite, code layout conventions |

## License

MIT — see [LICENSE](LICENSE) for the full text.
