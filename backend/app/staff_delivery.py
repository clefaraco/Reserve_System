"""Explicitly enabled Resend adapter. A provider 2xx is acceptance, never delivery."""

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request

from .config import settings
from .crypto import decrypt
from .db import one, transaction

router = APIRouter()


async def process_one(tenant_id: UUID):
    cfg = settings()
    # Disabled by default. Merely installing/upgrading never sends external mail.
    if not cfg.staff_email_send_enabled:
        return False
    if not (cfg.resend_api_key and cfg.staff_email_from and cfg.staff_accept_url):
        raise RuntimeError("Staff email configuration incomplete")
    async with transaction(tenant_id, None, None, worker=True) as (conn, _):
        # Same tenant lock order as administration/acceptance. Do not send a revoked invite.
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('staff-access:'||healthsync.current_tenant()::text,0))"
        )
        row = await one(
            conn,
            """SELECT d.*,i.contact_id,i.expires_at,c.email_ciphertext,c.key_id AS contact_key
            FROM healthsync.staff_deliveries d JOIN healthsync.staff_invitations i
            ON (i.tenant_id,i.id)=(d.tenant_id,d.invitation_id) JOIN healthsync.staff_contacts c
            ON (c.tenant_id,c.id)=(i.tenant_id,i.contact_id)
            WHERE d.state='queued' AND d.attempts<5 AND d.due_at<=clock_timestamp()
            AND i.revoked_at IS NULL AND i.accepted_at IS NULL AND i.expires_at>clock_timestamp()
            ORDER BY d.due_at,d.id LIMIT 1 FOR UPDATE OF d SKIP LOCKED""",
        )
        if not row:
            return False
        email = decrypt(
            bytes(row["email_ciphertext"]),
            row["contact_key"],
            f"staff:{tenant_id}:{row['contact_id']}",
        )["email"]
        token = decrypt(
            bytes(row["token_ciphertext"]), row["key_id"], f"staff-delivery:{tenant_id}:{row['id']}"
        )["token"]
        # Fragment avoids URL query/referrer/access-log disclosure. The UI removes it immediately.
        link = cfg.staff_accept_url + "#team-invite=" + token
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {cfg.resend_api_key}",
                        "Idempotency-Key": str(row["id"]),
                    },
                    json={
                        "from": cfg.staff_email_from,
                        "to": [email],
                        "subject": "Invitación al equipo · Medical Appointment System",
                        "text": f"La clínica te invita a su equipo. Verifica tu correo y segundo factor. Invitación temporal de un solo uso: {link}",
                    },
                )
            if response.status_code in (200, 201):
                acknowledgment = response.json()
                if not isinstance(acknowledgment, dict):
                    raise ValueError("Invalid provider acknowledgment")
                provider_id = acknowledgment.get("id")
                if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 200:
                    raise ValueError("Invalid provider acknowledgment")
                await conn.execute(
                    """UPDATE healthsync.staff_deliveries SET state='accepted',provider_id=%s,
                    accepted_at=clock_timestamp(),attempts=attempts+1,error_code=NULL WHERE id=%s""",
                    (provider_id, row["id"]),
                )
            elif response.status_code == 429:
                await conn.execute(
                    """UPDATE healthsync.staff_deliveries SET attempts=attempts+1,
                    state=CASE WHEN attempts+1>=5 THEN 'failed' ELSE 'queued' END,
                    due_at=clock_timestamp()+interval '5 minutes',error_code='RATE_LIMITED' WHERE id=%s""",
                    (row["id"],),
                )
            else:
                await conn.execute(
                    "UPDATE healthsync.staff_deliveries SET state=%s,attempts=attempts+1,error_code='PROVIDER_REJECTED' WHERE id=%s",
                    ("unknown" if response.status_code >= 500 else "failed", row["id"]),
                )
        except (httpx.HTTPError, ValueError):
            # Outcome unknown: do not automatically charge/send via a second provider.
            # Administrator may revoke/reissue; previous token then becomes unusable.
            await conn.execute(
                "UPDATE healthsync.staff_deliveries SET state='unknown',attempts=attempts+1,error_code='ACK_UNKNOWN' WHERE id=%s",
                (row["id"],),
            )
        return True


def verify_webhook(raw: bytes, headers, secret: str):
    try:
        event_id = headers["svix-id"]
        timestamp = headers["svix-timestamp"]
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError()
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
        if len(key) < 16:
            raise ValueError()
        expected = base64.b64encode(
            hmac.digest(
                key, event_id.encode() + b"." + timestamp.encode() + b"." + raw, hashlib.sha256
            )
        ).decode()
        signatures = [v[3:] for v in headers["svix-signature"].split() if v.startswith("v1,")]
        if not any(hmac.compare_digest(expected, s) for s in signatures):
            raise ValueError()
        return json.loads(raw)
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, "Notificación no verificable") from None


@router.post("/v1/{tenant_id}/team-delivery-webhook")
async def delivery_webhook(tenant_id: UUID, request: Request):
    if not settings().resend_webhook_secret:
        raise HTTPException(503, "Seguimiento de entrega no configurado")
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > 32768:
            raise HTTPException(413, "Notificación demasiado grande")
    event = verify_webhook(raw, request.headers, settings().resend_webhook_secret)
    if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
        raise HTTPException(422, "Notificación inválida")
    kind = event.get("type")
    if kind not in ("email.delivered", "email.bounced", "email.failed"):
        return {"state": "ignored"}
    provider_id = event.get("data", {}).get("email_id")
    if not isinstance(provider_id, str):
        raise HTTPException(422, "Referencia inválida")
    async with transaction(tenant_id, request, None, worker=True) as (conn, _):
        row = await one(
            conn,
            "SELECT id,state FROM healthsync.staff_deliveries WHERE provider_id=%s FOR UPDATE",
            (provider_id,),
        )
        if row and row["state"] in ("accepted", "unknown"):
            await conn.execute(
                """UPDATE healthsync.staff_deliveries SET state=%s,delivered_at=%s,error_code=%s WHERE id=%s""",
                (
                    "delivered" if kind == "email.delivered" else "failed",
                    datetime.now(UTC) if kind == "email.delivered" else None,
                    None if kind == "email.delivered" else "DELIVERY_FAILED",
                    row["id"],
                ),
            )
    return {"state": "recorded"}


async def run_once(tenant_id):
    from . import db

    await db.open_pool()
    try:
        await process_one(tenant_id)
    finally:
        await db.pool.close()


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", type=UUID, required=True)
    args = parser.parse_args()
    asyncio.run(run_once(args.tenant))
