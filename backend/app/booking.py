import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from .auth import Principal
from .config import settings
from .crypto import email_index, encrypt, keyed_hash
from .db import audit, many, one
from .models import Booking


async def documents(conn):
    return await many(
        conn,
        """
        SELECT DISTINCT ON (kind) id,kind,version,body,locale
        FROM healthsync.legal_documents WHERE active
        ORDER BY kind,published_at DESC,id DESC
    """,
    )


async def service(conn, service_id: UUID, resource_id: UUID, *, lock=False):
    if lock:
        # Serialize resource schedule operations without granting catalog UPDATE to the API.
        await conn.execute(
            """
            SELECT pg_advisory_xact_lock(hashtextextended(
                'resource:' || healthsync.current_tenant()::text || ':' || %s::text,0))
        """,
            (str(resource_id),),
        )
    row = await one(
        conn,
        """
        SELECT s.id,s.name,s.duration_minutes,s.buffer_minutes,b.timezone,r.public_name
        FROM healthsync.resource_services rs
        JOIN healthsync.resources r ON (r.tenant_id,r.id)=(rs.tenant_id,rs.resource_id)
        JOIN healthsync.services s ON (s.tenant_id,s.id)=(rs.tenant_id,rs.service_id)
        JOIN healthsync.branches b ON (b.tenant_id,b.id)=(s.tenant_id,s.branch_id)
        JOIN healthsync.specialties sp ON (sp.tenant_id,sp.id)=(s.tenant_id,s.specialty_id)
        JOIN healthsync.tenant_modules m ON (m.tenant_id,m.code)=(sp.tenant_id,sp.module_code)
        WHERE s.id=%s AND r.id=%s AND s.active AND r.active AND m.enabled
    """,
        (service_id, resource_id),
    )
    if not row:
        raise HTTPException(404, "Servicio o profesional no disponible")
    return row


async def validate_slot(conn, resource_id, starts_at, svc, *, excluding=None):
    start = starts_at.astimezone(UTC)
    now = datetime.now(UTC)
    if start < now + timedelta(minutes=5) or start > now + timedelta(days=180):
        raise HTTPException(422, "Selecciona una hora entre 5 minutos y 180 días desde ahora")
    if start.second or start.microsecond or start.minute % 15:
        raise HTTPException(422, "Selecciona un horario de la agenda")
    end = start + timedelta(minutes=svc["duration_minutes"])
    occupied = end + timedelta(minutes=svc["buffer_minutes"])
    local = start.astimezone(ZoneInfo(svc["timezone"]))
    local_end = occupied.astimezone(ZoneInfo(svc["timezone"]))
    rules = await many(
        conn,
        """
        SELECT opens_at,closes_at FROM healthsync.availability_rules
        WHERE resource_id=%s AND iso_weekday=%s
    """,
        (resource_id, local.isoweekday()),
    )
    if local.date() != local_end.date() or not any(
        r["opens_at"] <= local.time() and local_end.time() <= r["closes_at"] for r in rules
    ):
        raise HTTPException(409, "Fuera del horario de atención, incluido el tiempo de preparación")
    blocked = await one(
        conn,
        """
        SELECT 1 FROM healthsync.resource_blocks WHERE resource_id=%s
          AND starts_at < %s AND ends_at > %s LIMIT 1
    """,
        (resource_id, occupied, start),
    )
    busy = await one(
        conn,
        """
        SELECT 1 FROM healthsync.appointments WHERE resource_id=%s
          AND status <> 'cancelled' AND starts_at < %s AND occupied_until > %s
          AND (%s::uuid IS NULL OR id<>%s::uuid) LIMIT 1
    """,
        (resource_id, occupied, start, excluding, excluding),
    )
    if blocked or busy:
        raise HTTPException(409, "Ese horario acaba de ocuparse; selecciona otro")
    # GiST is the final arbiter under concurrency; availability is only a snapshot.
    return start, end, occupied


async def enqueue(conn, tenant_id, appointment, *, event: str, whatsapp: bool):
    channels = ["email", "whatsapp"] if whatsapp else ["email"]
    now = datetime.now(UTC)
    events = [(event, now)]
    if appointment["status"] in ("booked", "confirmed"):
        events += [
            ("reminder_24h", appointment["starts_at"] - timedelta(hours=24)),
            ("reminder_2h", appointment["starts_at"] - timedelta(hours=2)),
        ]
    for kind, due in events:
        if due < now and kind.startswith("reminder"):
            continue
        for channel in channels:
            await conn.execute(
                """
                INSERT INTO healthsync.outbox
                  (tenant_id,patient_id,appointment_id,appointment_version,kind,channel,due_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
            """,
                (
                    tenant_id,
                    appointment["patient_id"],
                    appointment["id"],
                    appointment["version"],
                    kind,
                    channel,
                    due,
                ),
            )


async def create_booking(
    conn, tenant_id: UUID, payload: Booking, key: UUID, principal: Principal | None
):
    if key.version != 4:
        raise HTTPException(422, "Idempotency-Key debe ser un UUID v4 aleatorio")
    canonical = payload.model_dump(mode="json") | {
        "actor": str(principal.subject) if principal else None
    }
    digest = keyed_hash(json.dumps(canonical, sort_keys=True), f"booking:{tenant_id}")
    # Serializes retries, not different bookings. Tenant is part of both the key and lock.
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{tenant_id}:{key}",)
    )
    previous = await one(
        conn, "SELECT * FROM healthsync.booking_commands WHERE idempotency_key=%s", (key,)
    )
    if previous:
        if bytes(previous["request_hmac"]) != digest:
            raise HTTPException(409, "La clave de reintento ya se usó con otros datos")
        appt = await one(
            conn, "SELECT * FROM healthsync.appointments WHERE id=%s", (previous["appointment_id"],)
        )
        await audit(conn, appt["patient_id"], "READ_IDEMPOTENT_BOOKING", "appointments", appt["id"])
        return result(appt, payload.create_account, principal)
    if payload.create_account and principal is None and not settings().auth_enabled:
        raise HTTPException(503, "Magic Link aún no configurado; puedes reservar sin crear cuenta")
    if payload.whatsapp and not payload.patient.phone:
        raise HTTPException(422, "Indica teléfono internacional para activar WhatsApp")
    if not payload.whatsapp and payload.patient.phone:
        raise HTTPException(422, "No recopilamos teléfono si no activas WhatsApp")
    docs = await documents(conn)
    required = {
        d["id"]
        for d in docs
        if d["kind"] in ("terms", "sensitive_data")
        or (payload.whatsapp and d["kind"] == "whatsapp")
    }
    expected_kinds = {"terms", "sensitive_data"} | ({"whatsapp"} if payload.whatsapp else set())
    if {d["kind"] for d in docs if d["id"] in required} != expected_kinds:
        raise HTTPException(503, "La clínica debe publicar sus documentos legales")
    if set(payload.consent_document_ids) != required or len(payload.consent_document_ids) != len(
        required
    ):
        raise HTTPException(409, "Los documentos cambiaron; vuelve a leerlos y aceptar")
    svc = await service(conn, payload.service_id, payload.resource_id, lock=True)
    start, end, occupied = await validate_slot(conn, payload.resource_id, payload.starts_at, svc)
    patient_id = uuid4()
    pii = payload.patient.model_dump(mode="json", exclude_none=True)
    await conn.execute(
        """
        INSERT INTO healthsync.patients
          (tenant_id,id,auth_user_id,pii_ciphertext,pii_key_id,email_hmac)
        VALUES (%s,%s,%s,%s,%s,%s)
    """,
        (
            tenant_id,
            patient_id,
            principal.subject if principal else None,
            encrypt(pii, f"patient:{tenant_id}:{patient_id}"),
            settings().pii_key_id,
            email_index(tenant_id, str(payload.patient.email)),
        ),
    )
    for doc_id in required:
        await conn.execute(
            "INSERT INTO healthsync.consents (tenant_id,patient_id,document_id) VALUES (%s,%s,%s)",
            (tenant_id, patient_id, doc_id),
        )
    appt = await one(
        conn,
        """
        INSERT INTO healthsync.appointments
          (tenant_id,patient_id,resource_id,service_id,starts_at,ends_at,occupied_until,duration_minutes,buffer_minutes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
    """,
        (
            tenant_id,
            patient_id,
            payload.resource_id,
            payload.service_id,
            start,
            end,
            occupied,
            svc["duration_minutes"],
            svc["buffer_minutes"],
        ),
    )
    await conn.execute(
        """
        INSERT INTO healthsync.booking_commands (tenant_id,idempotency_key,request_hmac,appointment_id)
        VALUES (%s,%s,%s,%s)
    """,
        (tenant_id, key, digest, appt["id"]),
    )
    if payload.create_account and principal is None:
        await conn.execute(
            "INSERT INTO healthsync.account_enrollments (tenant_id,patient_id) VALUES (%s,%s)",
            (tenant_id, patient_id),
        )
        await conn.execute(
            """
            INSERT INTO healthsync.outbox (tenant_id,patient_id,kind,channel,due_at)
            VALUES (%s,%s,'account_magic_link','email',clock_timestamp())
        """,
            (tenant_id, patient_id),
        )
    await enqueue(conn, tenant_id, appt, event="booking_created", whatsapp=payload.whatsapp)
    return result(appt, payload.create_account, principal)


def result(appt, create_account, principal):
    return {
        "id": appt["id"],
        "status": appt["status"],
        "starts_at": appt["starts_at"],
        "ends_at": appt["ends_at"],
        "version": appt["version"],
        "account": "authenticated"
        if principal
        else ("queued" if create_account else "not_requested"),
    }
