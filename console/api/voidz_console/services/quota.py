"""Multi-region Plan/Customer provisioning and pooled-quota enforcement.

A Plan groups several already-deployed Instances (typically one per
region/worker). A Customer is a single credential (uuid, and an ss
password/cipher when shadowsocks is included) provisioned as a Core Link
on every instance in the plan.

Each region's Core only knows its own local traffic — there is no way for
one Core process to know what a customer used in another region's Core.
So a customer's *pooled* quota (shared across every region in the plan) is
enforced centrally, here: `reconcile_loop` periodically sums `used_bytes`
for a customer's uuid across every regional Core and disables the link
everywhere once the pool is exhausted or the plan has expired. Per-region
Core links are always created with `limit_bytes=0` (locally unlimited) —
the pool total is the only cap that matters.
"""
from __future__ import annotations

import asyncio
import secrets
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from ..logging import get
from . import workers as worker_svc

log = get("runtime", "voidz.console.quota")

RECONCILE_INTERVAL = 20.0
DEVICE_CHECK_INTERVAL = 2.0

# A proxy client has no session: every tunneled TCP flow is its own
# connection, so a connected device can briefly have zero open ones between
# flows. An IP keeps its device slot for this long after its last connection
# closes, so those gaps don't hand the slot to another device mid-use.
DEVICE_LINGER_SECONDS = 8.0

# Per customer: IP -> {"first": ts, "last": ts} (epoch seconds) for every IP
# currently holding, or lingering in, a device slot. In memory only; a
# restart just rebuilds it from live connections on the next tick.
_device_presence: dict[str, dict[str, dict[str, float]]] = {}

# Last allowed_ips tuple actually confirmed pushed to Core, keyed by
# (customer_id, instance_id), so a tick only PATCHes a region when its lock
# actually changed. A single console process, so plain in-memory state is
# fine, but a restart empties this dict — and an *empty* desired lock is not
# a safe default for "nothing to do": Core's link may still be carrying a
# lock from before the restart (or from before a fix to this logic), and if
# the freshly computed lock also happens to be empty, comparing against a
# default of `()` would wrongly conclude they already match and never issue
# the PATCH that clears it. `_UNSET` forces at least one reconciling push
# per (customer, instance) after every restart, no matter what it computes to.
_UNSET = object()
_device_allowed_ips: dict[tuple[str, str], tuple[str, ...]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _instance_worker(pool, instance_id: str) -> str | None:
    """Worker URL for a running, endpoint-provisioned instance, else None."""
    row = await pool.fetchrow(
        "SELECT i.status, "
        "(SELECT dep.node_id FROM deployments dep WHERE dep.instance_id = i.id "
        " ORDER BY dep.started_at DESC LIMIT 1) AS node_id "
        "FROM instances i WHERE i.id = $1",
        instance_id,
    )
    if row is None or row["status"] != "running":
        return None
    return worker_svc.worker_url_for(row["node_id"] or "local")


async def _plan_instances(pool, plan_id: str):
    return await pool.fetch(
        "SELECT instance_id, region_label FROM plan_instances WHERE plan_id = $1 ORDER BY position",
        plan_id,
    )


async def _plan_protocols(pool, plan_id: str) -> list[str]:
    protocols = await pool.fetchval("SELECT protocols FROM plans WHERE id = $1", plan_id)
    return [p for p in (protocols or "").split(",") if p]


def _link_uuid(cred_uuid: str, protocol: str) -> str:
    """Core's link store is keyed by uuid alone, so a multi-protocol customer
    needs one distinct uuid per protocol — derived deterministically from the
    customer's cred_uuid so every region/function can recompute it without
    extra storage."""
    return str(uuid_mod.uuid5(uuid_mod.NAMESPACE_URL, f"voidz-link:{cred_uuid}:{protocol}"))


async def create_customer(pool, plan, name: str, limit_gb: float, days: int | None,
                          note: str = "", max_devices: int = 0) -> dict:
    """Provision a new customer across every instance in the plan and
    record it. Returns {id, sub_token, cred_uuid}."""
    protocols = [p for p in (plan["protocols"] or "").split(",") if p]
    cred_uuid = str(uuid_mod.uuid4())
    ss_cipher = ss_password = None
    if "shadowsocks" in protocols:
        ss_cipher = "chacha20-ietf-poly1305"
        ss_password = secrets.token_urlsafe(16)
    limit_bytes = int(float(limit_gb) * (1024 ** 3)) if limit_gb else 0
    now = _utcnow()
    expires_at = (now + timedelta(days=int(days))) if days else None
    max_devices = max(0, int(max_devices or 0))
    cid = secrets.token_hex(16)
    sub_token = secrets.token_urlsafe(24)
    await pool.execute(
        "INSERT INTO customers (id, plan_id, name, sub_token, cred_uuid, ss_cipher, ss_password, "
        "limit_bytes, used_bytes_cached, expires_at, active, note, created_at, max_devices) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 0, $9, TRUE, $10, $11, $12)",
        cid, plan["id"], name, sub_token, cred_uuid, ss_cipher, ss_password,
        limit_bytes, expires_at, note, now, max_devices,
    )
    await provision_customer_links(pool, plan, {
        "cred_uuid": cred_uuid, "name": name, "active": True,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "ss_cipher": ss_cipher, "ss_password": ss_password,
        "max_devices": max_devices,
    })
    return {"id": cid, "sub_token": sub_token, "cred_uuid": cred_uuid}


async def provision_customer_links(pool, plan, customer: dict) -> None:
    """Create (or refresh) a customer's Core link on every instance in the plan."""
    protocols = [p for p in (plan["protocols"] or "").split(",") if p]
    for pi in await _plan_instances(pool, plan["id"]):
        worker_url = await _instance_worker(pool, pi["instance_id"])
        if not worker_url:
            log.warning("skip provisioning %s: instance %s not running",
                       customer["name"], pi["instance_id"])
            continue
        for proto in protocols:
            body = {
                "uuid": _link_uuid(customer["cred_uuid"], proto),
                "protocol": proto,
                "label": f"{customer['name']} · {pi['region_label'] or 'region'}",
                "active": bool(customer.get("active", True)),
                "limit_bytes": 0,
                "expires_at": customer.get("expires_at"),
                "max_devices": int(customer.get("max_devices") or 0),
                "allowed_ips": [],
            }
            if proto == "shadowsocks":
                body["ss_cipher"] = customer.get("ss_cipher")
                body["ss_password"] = customer.get("ss_password")
            try:
                await worker_svc.worker_call(
                    worker_url, "POST",
                    f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/links",
                    body,
                )
            except worker_svc.WorkerError as exc:
                log.warning("provision failed for %s @ %s: %s",
                           customer["name"], pi["region_label"], exc)


async def set_customer_active(pool, plan_id: str, cred_uuid: str, active: bool) -> bool:
    """Push active/inactive to every region. Returns True only if every
    region in the plan actually got the update — callers that must not
    leave a stale, still-enabled link behind (see `_pending_disable` below)
    check this instead of assuming a fire-and-forget push landed everywhere."""
    protocols = await _plan_protocols(pool, plan_id)
    ok = True
    for pi in await _plan_instances(pool, plan_id):
        worker_url = await _instance_worker(pool, pi["instance_id"])
        if not worker_url:
            ok = False
            continue
        for proto in protocols:
            try:
                await worker_svc.worker_call(
                    worker_url, "PATCH",
                    f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/links/{_link_uuid(cred_uuid, proto)}",
                    {"active": active},
                )
            except worker_svc.WorkerError as exc:
                log.warning("set_active(%s) failed on %s/%s: %s", active, pi["instance_id"], proto, exc)
                ok = False
    return ok


async def _push_allowed_ips(pool, instance_id: str, cred_uuid: str, protocols: list[str],
                             allowed_ips: list[str]) -> bool:
    """Push the device lock to one region's Core links. Empty list clears the
    lock. A non-empty lock also makes Core disconnect any live connection
    from an IP outside it. Returns False if any link didn't take it."""
    worker_url = await _instance_worker(pool, instance_id)
    if not worker_url:
        return False
    ok = True
    for proto in protocols:
        try:
            await worker_svc.worker_call(
                worker_url, "PATCH",
                f"/worker/api/instances/{instance_id}/proxy/core/api/links/{_link_uuid(cred_uuid, proto)}",
                {"allowed_ips": allowed_ips},
            )
        except worker_svc.WorkerError as exc:
            ok = False
            log.warning("push allowed_ips failed on %s/%s: %s", instance_id, proto, exc)
    return ok


async def patch_customer_links(pool, plan_id: str, cred_uuid: str, patch: dict) -> None:
    """Apply an arbitrary patch (expires_at, reset_usage, ...) to every region."""
    protocols = await _plan_protocols(pool, plan_id)
    for pi in await _plan_instances(pool, plan_id):
        worker_url = await _instance_worker(pool, pi["instance_id"])
        if not worker_url:
            continue
        for proto in protocols:
            try:
                await worker_svc.worker_call(
                    worker_url, "PATCH",
                    f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/links/{_link_uuid(cred_uuid, proto)}",
                    patch,
                )
            except worker_svc.WorkerError as exc:
                log.warning("patch failed on %s/%s: %s", pi["instance_id"], proto, exc)


async def delete_customer_links(pool, plan_id: str, cred_uuid: str) -> None:
    protocols = await _plan_protocols(pool, plan_id)
    for pi in await _plan_instances(pool, plan_id):
        worker_url = await _instance_worker(pool, pi["instance_id"])
        if not worker_url:
            continue
        for proto in protocols:
            try:
                await worker_svc.worker_call(
                    worker_url, "DELETE",
                    f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/links/{_link_uuid(cred_uuid, proto)}",
                )
            except worker_svc.WorkerError as exc:
                log.warning("delete link failed on %s/%s: %s", pi["instance_id"], proto, exc)


async def _sum_usage(pool, plan_id: str, cred_uuid: str) -> int:
    protocols = await _plan_protocols(pool, plan_id)
    wanted = {_link_uuid(cred_uuid, proto) for proto in protocols}
    total = 0
    for pi in await _plan_instances(pool, plan_id):
        worker_url = await _instance_worker(pool, pi["instance_id"])
        if not worker_url:
            continue
        try:
            data = await worker_svc.worker_call(
                worker_url, "GET",
                f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/links",
            )
        except worker_svc.WorkerError:
            continue
        for link in data.get("links", []):
            if link.get("uuid") in wanted:
                total += int(link.get("used_bytes") or 0)
    return total


def _parse_ts(value) -> float | None:
    try:
        ts = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.timestamp()


async def _live_ips_by_region(pool, plan_id: str, cred_uuid: str,
                              protocols: list[str]) -> dict[str, dict[str, float | None]]:
    """For every region that answered: client IP -> earliest start time of
    its live connections on this customer's links. Regions that couldn't be
    reached are absent, so the caller can tell "no connections" apart from
    "don't know"."""
    wanted = ",".join(_link_uuid(cred_uuid, proto) for proto in protocols)
    out: dict[str, dict[str, float | None]] = {}
    for pi in await _plan_instances(pool, plan_id):
        instance_id = pi["instance_id"]
        worker_url = await _instance_worker(pool, instance_id)
        if not worker_url:
            continue
        try:
            data = await worker_svc.worker_call(
                worker_url, "GET",
                f"/worker/api/instances/{instance_id}/proxy/core/api/connections?uuids={wanted}",
            )
        except worker_svc.WorkerError:
            continue
        ips: dict[str, float | None] = {}
        for conn in data.get("connections", []):
            ip = conn.get("ip")
            if not ip:
                continue
            ts = _parse_ts(conn.get("first_connected_at"))
            prev = ips.get(ip)
            if ip not in ips or (ts is not None and (prev is None or ts < prev)):
                ips[ip] = ts
        out[instance_id] = ips
    return out


def _update_presence(customer_id: str, by_region: dict[str, dict[str, float | None]],
                     now: float) -> list[str]:
    """Fold this tick's live IPs into the customer's presence record and
    return the IPs currently holding a slot, earliest arrival first."""
    presence = _device_presence.setdefault(customer_id, {})
    live: dict[str, float] = {}
    for ips in by_region.values():
        for ip, ts in ips.items():
            start = ts if ts is not None else now
            live[ip] = min(live.get(ip, start), start)
    for ip, start in live.items():
        rec = presence.get(ip)
        if rec is None:
            presence[ip] = {"first": start, "last": now}
        else:
            rec["last"] = now
    for ip in [ip for ip, rec in presence.items()
               if ip not in live and now - rec["last"] > DEVICE_LINGER_SECONDS]:
        del presence[ip]
    return sorted(presence, key=lambda ip: presence[ip]["first"])


async def enforce_device_limits(pool) -> None:
    """Fast-ticking pass enforcing each customer's device cap, where a device
    is a client IP and the cap is pooled across every region in the plan.

    The first `max_devices` IPs to connect hold the slots until they've been
    gone for DEVICE_LINGER_SECONDS. As soon as every slot is taken, those IPs
    are pushed as an allow-list to every region's links: any other IP is
    refused at connect time, and Core disconnects any of its connections
    that were already open. Once a holder leaves, the lock lifts and the next
    device to connect takes the slot.

    Two properties matter here. The lock applies at the cap, not only above
    it: waiting for "more devices than allowed" meant that the moment the
    extra device was refused, the count fell back to the cap, the lock
    lifted, and the extra device got straight back in — forever. And pooling
    by IP means one device that pings or uses several regions at once is
    still one device.
    """
    rows = await pool.fetch(
        "SELECT id, plan_id, cred_uuid, name, max_devices FROM customers "
        "WHERE active = TRUE AND max_devices > 0"
    )
    seen_keys = set()
    seen_customers = set()
    now = _utcnow().timestamp()
    for c in rows:
        protocols = await _plan_protocols(pool, c["plan_id"])
        if not protocols:
            continue
        seen_customers.add(c["id"])
        try:
            by_region = await _live_ips_by_region(pool, c["plan_id"], c["cred_uuid"], protocols)
        except Exception as exc:
            log.warning("device check failed for customer %s: %s", c["id"], exc)
            continue
        holders = _update_presence(c["id"], by_region, now)
        cap = c["max_devices"]
        desired: tuple[str, ...] = tuple(sorted(holders[:cap])) if len(holders) >= cap else ()
        for pi in await _plan_instances(pool, c["plan_id"]):
            instance_id = pi["instance_id"]
            key = (c["id"], instance_id)
            seen_keys.add(key)
            # Re-push an unchanged lock too when an outside IP is live in this
            # region: it slipped in before the lock reached this region, and
            # the push is what makes Core disconnect it.
            intruder = bool(desired) and any(ip not in desired
                                             for ip in by_region.get(instance_id, {}))
            if _device_allowed_ips.get(key, _UNSET) == desired and not intruder:
                continue
            if await _push_allowed_ips(pool, instance_id, c["cred_uuid"], protocols, list(desired)):
                _device_allowed_ips[key] = desired
            else:
                _device_allowed_ips.pop(key, None)
            log.info("customer %s (%s) region %s -> allowed_ips=%s (%d holding, cap %d%s)",
                     c["name"], c["id"], pi["region_label"] or instance_id,
                     list(desired) or "(open)", len(holders), cap,
                     ", disconnecting other IPs" if intruder else "")
    # Drop bookkeeping for customers/regions that went away in the meantime
    # so these dicts don't grow forever.
    for key in list(_device_allowed_ips):
        if key not in seen_keys:
            del _device_allowed_ips[key]
    for cid in list(_device_presence):
        if cid not in seen_customers:
            del _device_presence[cid]


def forget_pending_disable(customer_id: str) -> None:
    """Drop a customer from the disable-retry set — call this whenever an
    admin explicitly re-enables them, so a stale retry from a past
    expiry/over-quota disable can't undo that re-enable on the next tick."""
    _pending_disable.discard(customer_id)


def forget_device_lock(customer_id: str) -> None:
    """Drop cached device-lock state for a customer so the next tick
    recomputes it from scratch (e.g. after an admin changes max_devices)."""
    for key in [k for k in _device_allowed_ips if k[0] == customer_id]:
        del _device_allowed_ips[key]
    _device_presence.pop(customer_id, None)


async def device_enforce_loop() -> None:
    """Background task: enforce per-customer device caps every tick.
    Started from the app lifespan; runs until cancelled on shutdown."""
    from ..db import get_pool

    while True:
        await asyncio.sleep(DEVICE_CHECK_INTERVAL)
        try:
            pool = get_pool(None)
        except RuntimeError:
            continue  # DB not ready yet on the very first tick
        try:
            await enforce_device_limits(pool)
        except Exception as exc:  # a bad tick must never kill the loop
            log.warning("device enforce tick failed: %s", exc)


# Customers whose DB row says active=FALSE (expired/over quota) but whose
# last disable push didn't confirm success on every region — e.g. a region
# was mid-redeploy at that exact tick. Retried every reconcile tick until
# every region confirms, so a customer can never keep using a region
# indefinitely just because it happened to be unreachable the one moment
# they crossed their limit.
_pending_disable: set[str] = set()


async def reconcile_once(pool) -> None:
    """One pass: refresh cached usage for every active customer, disable
    anyone who is now over quota or past expiry. Never raises."""
    rows = await pool.fetch(
        "SELECT id, plan_id, cred_uuid, name, limit_bytes, expires_at FROM customers "
        "WHERE active = TRUE"
    )
    now = _utcnow()
    for c in rows:
        try:
            used = await _sum_usage(pool, c["plan_id"], c["cred_uuid"])
        except Exception as exc:
            log.warning("usage sync failed for customer %s: %s", c["id"], exc)
            continue
        await pool.execute(
            "UPDATE customers SET used_bytes_cached = $2, last_synced_at = $3 WHERE id = $1",
            c["id"], used, now,
        )
        expired = c["expires_at"] is not None and c["expires_at"] < now
        over_quota = bool(c["limit_bytes"]) and used >= c["limit_bytes"]
        if expired or over_quota:
            await pool.execute("UPDATE customers SET active = FALSE WHERE id = $1", c["id"])
            ok = await set_customer_active(pool, c["plan_id"], c["cred_uuid"], False)
            if ok:
                _pending_disable.discard(c["id"])
            else:
                _pending_disable.add(c["id"])
                log.warning("customer %s (%s) disable did not confirm on every region; will retry",
                           c["name"], c["id"])
            log.info("customer %s (%s) disabled: %s", c["name"], c["id"],
                     "expired" if expired else "over quota")

    for pending_id in list(_pending_disable):
        c = await pool.fetchrow(
            "SELECT id, plan_id, cred_uuid, name FROM customers WHERE id = $1", pending_id
        )
        if c is None:
            _pending_disable.discard(pending_id)  # customer was deleted/revoked
            continue
        try:
            ok = await set_customer_active(pool, c["plan_id"], c["cred_uuid"], False)
        except Exception as exc:
            log.warning("retry disable failed for customer %s: %s", pending_id, exc)
            continue
        if ok:
            _pending_disable.discard(pending_id)
            log.info("customer %s (%s) disable confirmed on retry", c["name"], pending_id)


async def reconcile_loop() -> None:
    """Background task: re-sync usage / enforce pooled quotas every tick.
    Started from the app lifespan; runs until cancelled on shutdown."""
    from ..db import get_pool

    while True:
        await asyncio.sleep(RECONCILE_INTERVAL)
        try:
            pool = get_pool(None)
        except RuntimeError:
            continue  # DB not ready yet on the very first tick
        try:
            await reconcile_once(pool)
        except Exception as exc:  # a bad tick must never kill the loop
            log.warning("reconcile tick failed: %s", exc)
