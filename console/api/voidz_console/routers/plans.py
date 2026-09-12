"""Plans & Customers — multi-region grouping and pooled-quota reselling.

A Plan groups several already-deployed, running Instances (normally one
per worker/region) under one product. A Customer is a single credential
sold under a Plan: one combined data cap and one expiry, shared across
every region in the plan, enforced by services/quota.py.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from ..db import get_pool
from ..services import quota as quota_svc
from .instances import PROTOCOLS, _console_origin, _record_activity, current_user

router = APIRouter(prefix="/api", tags=["plans"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _plan_out(row) -> dict:
    d = dict(row)
    d["id"] = str(d["id"])
    d["created_at"] = d["created_at"].isoformat()
    d["protocols"] = [p for p in (d.get("protocols") or "").split(",") if p]
    return d


def _customer_out(row) -> dict:
    d = dict(row)
    d["id"] = str(d["id"])
    d["plan_id"] = str(d["plan_id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("last_synced_at"):
        d["last_synced_at"] = d["last_synced_at"].isoformat()
    d["expires_at"] = d["expires_at"].isoformat() if d.get("expires_at") else None
    d.pop("ss_password", None)
    d.pop("cred_uuid", None)
    return d


async def owned_plan(pool, user_id: str, plan_id: str):
    row = await pool.fetchrow(
        "SELECT * FROM plans WHERE id = $1 AND user_id = $2", plan_id, user_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="plan not found")
    return row


def _sub_url(request: Request, sub_token: str) -> str:
    return f"{_console_origin(request)}/sub/{sub_token}"


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
@router.get("/plans")
async def list_plans(request: Request, user: asyncpg.Record = Depends(current_user)):
    pool = get_pool(request)
    rows = await pool.fetch(
        "SELECT p.*, "
        "(SELECT COUNT(*) FROM plan_instances pi WHERE pi.plan_id = p.id) AS instance_count, "
        "(SELECT COUNT(*) FROM customers c WHERE c.plan_id = p.id AND c.active = TRUE) AS customer_count "
        "FROM plans p WHERE p.user_id = $1 ORDER BY p.created_at DESC",
        user["id"],
    )
    return {"plans": [_plan_out(r) for r in rows]}


@router.post("/plans", status_code=201)
async def create_plan(request: Request, user: asyncpg.Record = Depends(current_user)):
    pool = get_pool(request)
    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not (2 <= len(name) <= 60):
        raise HTTPException(status_code=400, detail="name must be 2-60 characters")
    protocols = [p for p in (body.get("protocols") or []) if p in PROTOCOLS]
    if not protocols:
        raise HTTPException(status_code=400, detail="pick at least one protocol")
    instance_ids = body.get("instance_ids") or []
    if not isinstance(instance_ids, list) or not (1 <= len(instance_ids) <= 12):
        raise HTTPException(status_code=400, detail="pick 1-12 instances")
    region_labels = body.get("region_labels") or {}

    valid_rows = []
    for iid in instance_ids:
        row = await pool.fetchrow(
            "SELECT id, region FROM instances WHERE id = $1 AND user_id = $2 AND status = 'running'",
            iid, user["id"],
        )
        if row is None:
            raise HTTPException(status_code=400, detail=f"instance {iid} not found or not running")
        valid_rows.append(row)

    plan_id = secrets.token_hex(16)
    now = _utcnow()
    await pool.execute(
        "INSERT INTO plans (id, user_id, name, protocols, created_at) VALUES ($1, $2, $3, $4, $5)",
        plan_id, user["id"], name, ",".join(protocols), now,
    )
    for pos, row in enumerate(valid_rows):
        iid_str = str(row["id"])
        region_label = str(region_labels.get(iid_str) or row["region"] or f"Region {pos + 1}")
        await pool.execute(
            "INSERT INTO plan_instances (id, plan_id, instance_id, region_label, position) "
            "VALUES ($1, $2, $3, $4, $5)",
            secrets.token_hex(16), plan_id, iid_str, region_label, pos,
        )
    await _record_activity(pool, user["id"], None, "plan", f"Plan '{name}' created")
    return await get_plan(plan_id, request, user)


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, request: Request, user: asyncpg.Record = Depends(current_user)):
    pool = get_pool(request)
    plan = await owned_plan(pool, user["id"], plan_id)
    pi_rows = await pool.fetch(
        "SELECT pi.instance_id, pi.region_label, i.name AS instance_name, i.status "
        "FROM plan_instances pi JOIN instances i ON i.id = pi.instance_id "
        "WHERE pi.plan_id = $1 ORDER BY pi.position",
        plan_id,
    )
    cust_rows = await pool.fetch(
        "SELECT * FROM customers WHERE plan_id = $1 ORDER BY created_at DESC", plan_id
    )
    out = _plan_out(plan)
    out["instances"] = [
        {"instance_id": str(r["instance_id"]), "region_label": r["region_label"],
         "instance_name": r["instance_name"], "status": r["status"]}
        for r in pi_rows
    ]
    out["customers"] = [_customer_out(r) for r in cust_rows]
    return out


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, request: Request, user: asyncpg.Record = Depends(current_user)):
    pool = get_pool(request)
    plan = await owned_plan(pool, user["id"], plan_id)
    cust_rows = await pool.fetch("SELECT cred_uuid FROM customers WHERE plan_id = $1", plan_id)
    for c in cust_rows:
        await quota_svc.delete_customer_links(pool, plan_id, c["cred_uuid"])
    await pool.execute("DELETE FROM plans WHERE id = $1", plan_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@router.post("/plans/{plan_id}/customers", status_code=201)
async def create_customer_route(plan_id: str, request: Request,
                                user: asyncpg.Record = Depends(current_user)):
    pool = get_pool(request)
    plan = await owned_plan(pool, user["id"], plan_id)
    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not (1 <= len(name) <= 60):
        raise HTTPException(status_code=400, detail="name must be 1-60 characters")
    try:
        limit_gb = float(body.get("limit_gb") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid quota")
    if not (0 <= limit_gb <= 100000):
        raise HTTPException(status_code=400, detail="invalid quota")
    days = body.get("days")
    try:
        days = int(days) if days else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid duration")
    if days is not None and not (1 <= days <= 3650):
        raise HTTPException(status_code=400, detail="duration must be 1-3650 days")
    note = str(body.get("note") or "")[:300]
    try:
        max_devices = int(body.get("max_devices") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid max_devices")
    if not (0 <= max_devices <= 50):
        raise HTTPException(status_code=400, detail="max_devices must be 0-50")

    result = await quota_svc.create_customer(pool, plan, name, limit_gb, days, note, max_devices)
    await _record_activity(pool, user["id"], None, "customer",
                           f"Customer '{name}' added to plan '{plan['name']}'")
    result["sub_url"] = _sub_url(request, result["sub_token"])
    result["name"] = name
    return result


@router.patch("/plans/{plan_id}/customers/{customer_id}")
async def update_customer(plan_id: str, customer_id: str, request: Request,
                          user: asyncpg.Record = Depends(current_user)):
    pool = get_pool(request)
    await owned_plan(pool, user["id"], plan_id)
    cust = await pool.fetchrow(
        "SELECT * FROM customers WHERE id = $1 AND plan_id = $2", customer_id, plan_id
    )
    if cust is None:
        raise HTTPException(status_code=404, detail="customer not found")
    body = await request.json()

    if "name" in body:
        name = str(body["name"]).strip()[:60]
        if name:
            await pool.execute("UPDATE customers SET name = $2 WHERE id = $1", customer_id, name)

    if "extend_days" in body:
        try:
            days = int(body["extend_days"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="invalid extend_days")
        now = _utcnow()
        base = cust["expires_at"] if (cust["expires_at"] and cust["expires_at"] > now) else now
        new_expiry = base + timedelta(days=days)
        await pool.execute("UPDATE customers SET expires_at = $2 WHERE id = $1", customer_id, new_expiry)
        await quota_svc.patch_customer_links(pool, plan_id, cust["cred_uuid"],
                                             {"expires_at": new_expiry.isoformat()})

    if "limit_gb" in body:
        try:
            limit_bytes = int(float(body["limit_gb"]) * (1024 ** 3)) if body["limit_gb"] else 0
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="invalid limit_gb")
        await pool.execute("UPDATE customers SET limit_bytes = $2 WHERE id = $1", customer_id, limit_bytes)

    if "max_devices" in body:
        try:
            max_devices = int(body["max_devices"] or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="invalid max_devices")
        if not (0 <= max_devices <= 50):
            raise HTTPException(status_code=400, detail="max_devices must be 0-50")
        await pool.execute("UPDATE customers SET max_devices = $2 WHERE id = $1", customer_id, max_devices)
        await quota_svc.patch_customer_links(pool, plan_id, cust["cred_uuid"],
                                             {"max_devices": max_devices})

    if body.get("reset_usage"):
        await pool.execute("UPDATE customers SET used_bytes_cached = 0 WHERE id = $1", customer_id)
        await quota_svc.patch_customer_links(pool, plan_id, cust["cred_uuid"], {"reset_usage": True})

    if "active" in body:
        active = bool(body["active"])
        await pool.execute("UPDATE customers SET active = $2 WHERE id = $1", customer_id, active)
        await quota_svc.set_customer_active(pool, plan_id, cust["cred_uuid"], active)

    row = await pool.fetchrow("SELECT * FROM customers WHERE id = $1", customer_id)
    return _customer_out(row)


@router.delete("/plans/{plan_id}/customers/{customer_id}")
async def delete_customer(plan_id: str, customer_id: str, request: Request,
                          user: asyncpg.Record = Depends(current_user)):
    pool = get_pool(request)
    plan = await owned_plan(pool, user["id"], plan_id)
    cust = await pool.fetchrow(
        "SELECT cred_uuid, name FROM customers WHERE id = $1 AND plan_id = $2", customer_id, plan_id
    )
    if cust is None:
        raise HTTPException(status_code=404, detail="customer not found")
    await quota_svc.delete_customer_links(pool, plan_id, cust["cred_uuid"])
    await pool.execute("DELETE FROM customers WHERE id = $1", customer_id)
    await _record_activity(pool, user["id"], None, "customer", f"Customer '{cust['name']}' revoked")
    return {"ok": True}
