"""Per-tenant transactional outbox dispatcher. Delivery is at-least-once."""

import argparse
import asyncio
from uuid import UUID

import httpx

from . import db
from .config import settings
from .crypto import decrypt
from .db import audit, one, transaction


async def dispatch_one(tenant_id: UUID) -> bool:
    async with transaction(tenant_id, None, None, worker=True) as (conn, _tenant):
        candidate = await one(
            conn,
            """
            SELECT id,patient_id,appointment_id FROM healthsync.outbox WHERE due_at<=clock_timestamp()
              AND delivered_at IS NULL AND cancelled_at IS NULL AND attempts<10
            ORDER BY due_at LIMIT 1
        """,
        )
        if not candidate:
            return False
        # Consistent lock order: appointment -> patient -> event. A concurrent change
        # commits before delivery, or waits until that version's delivery completes.
        appt = None
        if candidate["appointment_id"]:
            appt = await one(
                conn,
                "SELECT version FROM healthsync.appointments WHERE id=%s FOR UPDATE SKIP LOCKED",
                (candidate["appointment_id"],),
            )
            if not appt:
                return False
        patient = await one(
            conn,
            "SELECT * FROM healthsync.patients WHERE id=%s FOR UPDATE SKIP LOCKED",
            (candidate["patient_id"],),
        )
        if not patient:
            return False
        event = await one(
            conn,
            """
            SELECT * FROM healthsync.outbox WHERE id=%s AND due_at<=clock_timestamp()
              AND delivered_at IS NULL AND cancelled_at IS NULL AND attempts<10
            FOR UPDATE SKIP LOCKED
        """,
            (candidate["id"],),
        )
        if not event:
            return False
        await audit(conn, patient["id"], "READ_NOTIFICATION", "outbox", event["id"])
        if patient["deleted_at"]:
            await conn.execute(
                "UPDATE healthsync.outbox SET cancelled_at=clock_timestamp() WHERE id=%s",
                (event["id"],),
            )
            return True
        if appt and appt["version"] != event["appointment_version"]:
            await conn.execute(
                "UPDATE healthsync.outbox SET cancelled_at=clock_timestamp() WHERE id=%s",
                (event["id"],),
            )
            return True
        if event["kind"] == "account_magic_link":
            enrollment = await one(
                conn,
                """
                SELECT id FROM healthsync.account_enrollments WHERE patient_id=%s
                  AND claimed_at IS NULL AND expires_at>clock_timestamp() LIMIT 1
            """,
                (patient["id"],),
            )
            if not enrollment:
                await conn.execute(
                    "UPDATE healthsync.outbox SET cancelled_at=clock_timestamp() WHERE id=%s",
                    (event["id"],),
                )
                return True
        if event["channel"] == "whatsapp":
            consent = await one(
                conn,
                """
                SELECT c.id FROM healthsync.consents c JOIN healthsync.legal_documents d
                  ON (d.tenant_id,d.id)=(c.tenant_id,c.document_id)
                WHERE c.patient_id=%s AND d.kind='whatsapp' AND c.withdrawn_at IS NULL LIMIT 1
            """,
                (patient["id"],),
            )
            if not consent:
                await conn.execute(
                    "UPDATE healthsync.outbox SET cancelled_at=clock_timestamp() WHERE id=%s",
                    (event["id"],),
                )
                return True
        pii = decrypt(
            bytes(patient["pii_ciphertext"]),
            patient["pii_key_id"],
            f"patient:{tenant_id}:{patient['id']}",
        )
        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                if event["kind"] == "account_magic_link":
                    if not settings().auth_enabled:
                        raise RuntimeError("provider_not_configured")
                    response = await client.post(
                        f"{settings().supabase_url}/auth/v1/otp",
                        headers={"apikey": settings().supabase_publishable_key},
                        json={"email": pii["email"], "create_user": True},
                    )
                else:
                    if (
                        not settings().notification_webhook_url
                        or not settings().notification_webhook_token
                    ):
                        raise RuntimeError("provider_not_configured")
                    # No service name, result, diagnosis, or date of birth leaves the app.
                    response = await client.post(
                        settings().notification_webhook_url,
                        headers={
                            "Authorization": f"Bearer {settings().notification_webhook_token}",
                            "Idempotency-Key": str(event["id"]),
                        },
                        json={
                            "event_id": str(event["id"]),
                            "channel": event["channel"],
                            "destination": pii["email"]
                            if event["channel"] == "email"
                            else pii["phone"],
                            "template": event["kind"],
                            "message": "Tienes una actualización de agenda. Ingresa al portal seguro.",
                        },
                    )
                response.raise_for_status()
        except (httpx.HTTPError, RuntimeError):
            # Never store response bodies, URLs, tokens, or contact addresses in logs.
            await conn.execute(
                """
                UPDATE healthsync.outbox SET attempts=attempts+1,last_error_code='delivery_unavailable',
                  due_at=clock_timestamp()+interval '5 minutes' WHERE id=%s
            """,
                (event["id"],),
            )
        else:
            await conn.execute(
                """
                UPDATE healthsync.outbox SET delivered_at=clock_timestamp(),attempts=attempts+1,
                  last_error_code=NULL WHERE id=%s
            """,
                (event["id"],),
            )
        return True


async def run(tenant_id, once):
    await db.open_pool()
    try:
        while True:
            handled = await dispatch_one(tenant_id)
            if once:
                return
            if not handled:
                await asyncio.sleep(2)
    finally:
        await db.pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True, type=UUID)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.tenant, args.once))
