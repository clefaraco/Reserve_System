import base64
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import boto3
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from psycopg.errors import ExclusionViolation, LockNotAvailable, UniqueViolation
from starlette.concurrency import run_in_threadpool

from . import db
from .auth import Principal, optional_principal, verified_email
from .booking import create_booking, documents, enqueue, service, validate_slot
from .config import settings
from .crypto import decrypt, email_index
from .db import audit, many, one, staff_role, transaction
from .models import Booking, ChangeAppointment, PrivacyRequest
from .workspaces import router as workspace_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.open_pool()
    try:
        yield
    finally:
        if db.pool:
            await db.pool.close()


app = FastAPI(title="Medical Appointment System · Tresuryx SpA", version="0.2.0", lifespan=lifespan)
app.include_router(workspace_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        }
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # FastAPI's default includes rejected input (possibly PII) in errors.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in error.errors()
            ]
        },
    )


@app.exception_handler(ExclusionViolation)
async def overlap(request, error):
    return JSONResponse(
        status_code=409, content={"detail": "Horario ocupado; vuelve a consultar disponibilidad"}
    )


@app.exception_handler(LockNotAvailable)
async def lock_timeout(request, error):
    return JSONResponse(
        status_code=409, content={"detail": "Agenda ocupada; reintenta con la misma clave"}
    )


@app.exception_handler(UniqueViolation)
async def duplicate(request, error):
    return JSONResponse(status_code=409, content={"detail": "Ya existe una solicitud equivalente"})


def require_login(principal):
    if principal is None:
        raise HTTPException(401, "Inicia sesión para gestionar tus datos")


async def owned_patient(conn, patient_id, principal):
    require_login(principal)
    patient = await one(
        conn,
        """
        SELECT * FROM healthsync.patients
        WHERE id=%s AND auth_user_id=%s AND deleted_at IS NULL
    """,
        (patient_id, principal.subject),
    )
    if not patient:
        raise HTTPException(404, "Paciente no encontrado")
    await audit(conn, patient["id"], "READ", "patients", patient["id"])
    return patient


@app.get("/health")
async def health():
    # Do not report readiness merely because the process has a PID.
    async with db.pool.connection() as conn:
        await conn.execute("SELECT 1 FROM healthsync.tenants LIMIT 0")
    return {"status": "ok"}


@app.get("/v1/{tenant_id}/catalog")
async def catalog(tenant_id: UUID, request: Request):
    async with transaction(tenant_id, request, None) as (conn, tenant):
        rows = await many(
            conn,
            """
            SELECT s.id AS service_id,s.name AS service_name,s.duration_minutes,s.buffer_minutes,
                   r.id AS resource_id,r.public_name,b.name AS branch,b.timezone,sp.name AS specialty
            FROM healthsync.resource_services rs
            JOIN healthsync.services s ON (s.tenant_id,s.id)=(rs.tenant_id,rs.service_id)
            JOIN healthsync.resources r ON (r.tenant_id,r.id)=(rs.tenant_id,rs.resource_id)
            JOIN healthsync.branches b ON (b.tenant_id,b.id)=(s.tenant_id,s.branch_id)
            JOIN healthsync.specialties sp ON (sp.tenant_id,sp.id)=(s.tenant_id,s.specialty_id)
            JOIN healthsync.tenant_modules m ON (m.tenant_id,m.code)=(sp.tenant_id,sp.module_code)
            WHERE s.active AND r.active AND m.enabled ORDER BY s.name,r.public_name
        """,
        )
        return {
            "tenant": tenant["name"],
            "services": rows,
            "documents": await documents(conn),
            "account_available": settings().auth_enabled,
            "cancel_cutoff_minutes": tenant["cancel_cutoff_minutes"],
            "reschedule_cutoff_minutes": tenant["reschedule_cutoff_minutes"],
        }


@app.get("/v1/{tenant_id}/availability")
async def availability(
    tenant_id: UUID, service_id: UUID, resource_id: UUID, day: date, request: Request
):
    async with transaction(tenant_id, request, None) as (conn, _tenant):
        svc = await service(conn, service_id, resource_id)
        tz = ZoneInfo(svc["timezone"])
        # Iterate real UTC instants; avoids inventing nonexistent local times on DST transitions.
        start = datetime.combine(day, time(), tzinfo=tz).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time(), tzinfo=tz).astimezone(UTC)
        slots = []
        while start < end:
            try:
                await validate_slot(conn, resource_id, start, svc)
                slots.append(start)
            except HTTPException as error:
                if error.status_code not in (409, 422):
                    raise
            start += timedelta(minutes=15)
        return {"timezone": svc["timezone"], "slots": slots}


@app.post("/v1/{tenant_id}/bookings", status_code=201)
async def book(
    tenant_id: UUID,
    payload: Booking,
    request: Request,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        return await create_booking(conn, tenant_id, payload, idempotency_key, principal)


@app.post("/v1/{tenant_id}/account/claim")
async def claim_account(
    tenant_id: UUID, request: Request, principal: Principal | None = Depends(optional_principal)
):
    require_login(principal)
    email = await verified_email(principal)
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        # Explicit opt-in AND verified email AND an unexpired pending enrollment are all required.
        patients = await many(
            conn,
            """
            SELECT p.id FROM healthsync.patients p
            WHERE p.email_hmac=%s AND p.auth_user_id IS NULL AND p.deleted_at IS NULL
              AND EXISTS (SELECT 1 FROM healthsync.account_enrollments e
                WHERE (e.tenant_id,e.patient_id)=(p.tenant_id,p.id)
                  AND e.claimed_at IS NULL AND e.expires_at>clock_timestamp())
            FOR UPDATE OF p
        """,
            (email_index(tenant_id, email),),
        )
        for patient in patients:
            await audit(conn, patient["id"], "READ_ACCOUNT_CLAIM", "patients", patient["id"])
            await conn.execute(
                "UPDATE healthsync.patients SET auth_user_id=%s WHERE id=%s",
                (principal.subject, patient["id"]),
            )
            await conn.execute(
                """
                UPDATE healthsync.account_enrollments SET claimed_at=clock_timestamp()
                WHERE patient_id=%s AND claimed_at IS NULL
            """,
                (patient["id"],),
            )
        return {"linked_profiles": len(patients)}


@app.get("/v1/{tenant_id}/appointments")
async def my_appointments(
    tenant_id: UUID, request: Request, principal: Principal | None = Depends(optional_principal)
):
    require_login(principal)
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        rows = await many(
            conn,
            """
            SELECT a.id,a.patient_id,a.starts_at,a.ends_at,a.status,a.version,
                   s.name AS service_name,r.public_name,b.timezone
            FROM healthsync.appointments a
            JOIN healthsync.patients p ON (p.tenant_id,p.id)=(a.tenant_id,a.patient_id)
            JOIN healthsync.services s ON (s.tenant_id,s.id)=(a.tenant_id,a.service_id)
            JOIN healthsync.resources r ON (r.tenant_id,r.id)=(a.tenant_id,a.resource_id)
            JOIN healthsync.branches b ON (b.tenant_id,b.id)=(s.tenant_id,s.branch_id)
            WHERE p.auth_user_id=%s AND p.deleted_at IS NULL ORDER BY a.starts_at
        """,
            (principal.subject,),
        )
        for row in rows:
            await audit(conn, row["patient_id"], "READ", "appointments", row["id"])
        return rows


@app.patch("/v1/{tenant_id}/appointments/{appointment_id}")
async def change_appointment(
    tenant_id: UUID,
    appointment_id: UUID,
    payload: ChangeAppointment,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    require_login(principal)
    async with transaction(tenant_id, request, principal) as (conn, tenant):
        role = await staff_role(conn, principal)
        appt = await one(
            conn,
            """
            SELECT a.* FROM healthsync.appointments a
            JOIN healthsync.patients p ON (p.tenant_id,p.id)=(a.tenant_id,a.patient_id)
            JOIN healthsync.resources r ON (r.tenant_id,r.id)=(a.tenant_id,a.resource_id)
            WHERE a.id=%s AND p.deleted_at IS NULL
              AND (p.auth_user_id=%s OR %s OR (%s AND EXISTS (
                SELECT 1 FROM healthsync.membership_branches mb WHERE mb.tenant_id=r.tenant_id
                  AND mb.branch_id=r.branch_id AND mb.auth_user_id=%s))) FOR UPDATE OF a
        """,
            (
                appointment_id,
                principal.subject,
                role == "admin",
                role in ("scheduler", "reception"),
                principal.subject,
            ),
        )
        if not appt:
            raise HTTPException(404, "Reserva no encontrada")
        await audit(conn, appt["patient_id"], "READ", "appointments", appt["id"])
        if appt["version"] != payload.expected_version:
            raise HTTPException(409, "La reserva cambió; actualiza la agenda")
        if appt["status"] not in ("booked", "confirmed"):
            raise HTTPException(409, "La reserva ya no admite cambios")
        now = datetime.now(UTC)
        if appt["starts_at"] <= now:
            raise HTTPException(409, "La hora ya comenzó")
        if payload.action == "confirm":
            if payload.starts_at is not None:
                raise HTTPException(422, "Confirmar no cambia el horario")
            if appt["status"] == "confirmed":
                return {"id": appt["id"], "status": "confirmed", "version": appt["version"]}
            await conn.execute(
                "UPDATE healthsync.appointments SET status='confirmed',version=version+1 WHERE id=%s",
                (appointment_id,),
            )
        else:
            cutoff = tenant[
                "cancel_cutoff_minutes"
                if payload.action == "cancel"
                else "reschedule_cutoff_minutes"
            ]
            if appt["starts_at"] - now < timedelta(minutes=cutoff):
                raise HTTPException(
                    409, f"Debes realizar este cambio con {cutoff} minutos de anticipación"
                )
            if payload.action == "cancel":
                if payload.starts_at is not None:
                    raise HTTPException(422, "Anular no requiere otra hora")
                await conn.execute(
                    "UPDATE healthsync.appointments SET status='cancelled',version=version+1 WHERE id=%s",
                    (appointment_id,),
                )
            else:
                if payload.starts_at is None:
                    raise HTTPException(422, "Indica la nueva fecha y hora")
                svc = await service(conn, appt["service_id"], appt["resource_id"], lock=True)
                # Keep the original duration/buffer contract, even if the catalog changed.
                svc.update(
                    duration_minutes=appt["duration_minutes"], buffer_minutes=appt["buffer_minutes"]
                )
                start, end, occupied = await validate_slot(
                    conn, appt["resource_id"], payload.starts_at, svc, excluding=appointment_id
                )
                await conn.execute(
                    """
                    UPDATE healthsync.appointments SET starts_at=%s,ends_at=%s,occupied_until=%s,
                      version=version+1 WHERE id=%s
                """,
                    (start, end, occupied, appointment_id),
                )
        updated = await one(
            conn, "SELECT * FROM healthsync.appointments WHERE id=%s", (appointment_id,)
        )
        await conn.execute(
            """
            UPDATE healthsync.outbox SET cancelled_at=clock_timestamp()
            WHERE appointment_id=%s AND delivered_at IS NULL AND cancelled_at IS NULL
        """,
            (appointment_id,),
        )
        whatsapp = await one(
            conn,
            """
            SELECT 1 FROM healthsync.consents c JOIN healthsync.legal_documents d
              ON (d.tenant_id,d.id)=(c.tenant_id,c.document_id)
            WHERE c.patient_id=%s AND d.kind='whatsapp' AND c.withdrawn_at IS NULL LIMIT 1
        """,
            (appt["patient_id"],),
        )
        await audit(
            conn, appt["patient_id"], "READ_NOTIFICATION_CONSENT", "patients", appt["patient_id"]
        )
        await enqueue(
            conn,
            tenant_id,
            updated,
            event="booking_cancelled" if payload.action == "cancel" else "booking_changed",
            whatsapp=bool(whatsapp),
        )
        return {
            "id": updated["id"],
            "status": updated["status"],
            "version": updated["version"],
            "starts_at": updated["starts_at"],
            "ends_at": updated["ends_at"],
        }


@app.get("/v1/{tenant_id}/privacy/export")
async def export_data(
    tenant_id: UUID, request: Request, principal: Principal | None = Depends(optional_principal)
):
    require_login(principal)
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        patients = await many(
            conn,
            "SELECT * FROM healthsync.patients WHERE auth_user_id=%s AND deleted_at IS NULL",
            (principal.subject,),
        )
        data = []
        for patient in patients:
            pid = patient["id"]
            await audit(conn, pid, "EXPORT", "patients", pid)
            pii = decrypt(
                bytes(patient["pii_ciphertext"]),
                patient["pii_key_id"],
                f"patient:{tenant_id}:{pid}",
            )
            appointments = await many(
                conn,
                """
                SELECT id,service_id,resource_id,starts_at,ends_at,status,version
                FROM healthsync.appointments WHERE patient_id=%s
            """,
                (pid,),
            )
            consents = await many(
                conn,
                """
                SELECT c.id,c.document_id,d.kind,d.version,c.accepted_at,c.withdrawn_at,d.body
                FROM healthsync.consents c JOIN healthsync.legal_documents d
                  ON (d.tenant_id,d.id)=(c.tenant_id,c.document_id) WHERE c.patient_id=%s
            """,
                (pid,),
            )
            results = await many(
                conn,
                """
                SELECT id,created_at,scan_status,deleted_at FROM healthsync.exam_results WHERE patient_id=%s
            """,
                (pid,),
            )
            requests = await many(
                conn,
                """
                SELECT id,kind,state,requested_at,completed_at FROM healthsync.privacy_requests WHERE patient_id=%s
            """,
                (pid,),
            )
            attendance = await many(
                conn,
                """SELECT id,appointment_id,checked_in_at,completed_at,outcome
                FROM healthsync.attendance_records WHERE patient_id=%s""",
                (pid,),
            )
            history = await many(
                conn,
                """SELECT id,appointment_id,occurred_at,previous_status,status,
                previous_starts_at,starts_at,version FROM healthsync.appointment_events WHERE patient_id=%s""",
                (pid,),
            )
            evidence = await many(
                conn,
                """
                SELECT a.id,a.action,a.entity_type,a.entity_id,a.occurred_at,a.actor_type,
                       c.ip_ciphertext,c.key_id
                FROM healthsync.audit_events a JOIN healthsync.privacy_contexts c
                  ON (c.tenant_id,c.id)=(a.tenant_id,a.privacy_context_id) WHERE a.patient_id=%s
            """,
                (pid,),
            )
            for e in evidence:
                cipher, key_id = e.pop("ip_ciphertext"), e.pop("key_id")
                e["network_evidence"] = (
                    decrypt(bytes(cipher), key_id, f"ip:{tenant_id}") if cipher else None
                )
            for entity, rows in (
                ("appointments", appointments),
                ("consents", consents),
                ("exam_results", results),
                ("privacy_requests", requests),
                ("attendance_records", attendance),
                ("appointment_events", history),
            ):
                for row in rows:
                    await audit(conn, pid, "EXPORT", entity, row["id"])
            await audit(conn, pid, "EXPORT_AUDIT", "patients", pid)
            data.append(
                {
                    "patient_id": pid,
                    "contact": pii,
                    "appointments": appointments,
                    "consents": consents,
                    "exam_results": results,
                    "privacy_requests": requests,
                    "attendance": attendance,
                    "appointment_history": history,
                    "access_history": evidence,
                }
            )
        return {"exported_at": datetime.now(UTC), "profiles": data}


@app.post("/v1/{tenant_id}/privacy/requests", status_code=202)
async def request_privacy(
    tenant_id: UUID,
    payload: PrivacyRequest,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        await owned_patient(conn, payload.patient_id, principal)
        row = await one(
            conn,
            """
            INSERT INTO healthsync.privacy_requests (tenant_id,patient_id,requested_by,kind)
            VALUES (%s,%s,%s,%s) RETURNING id,state
        """,
            (tenant_id, payload.patient_id, principal.subject, payload.kind),
        )
        return row


@app.post("/v1/{tenant_id}/privacy/requests/{request_id}/anonymize")
async def anonymize(
    tenant_id: UUID,
    request_id: UUID,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    require_login(principal)
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        if await staff_role(conn, principal) not in ("admin", "privacy"):
            raise HTTPException(403, "Se requiere un responsable de privacidad")
        item = await one(
            conn,
            """
            SELECT * FROM healthsync.privacy_requests
            WHERE id=%s AND kind='anonymize' AND state IN ('pending','approved') FOR UPDATE
        """,
            (request_id,),
        )
        if not item:
            raise HTTPException(404, "Solicitud no disponible")
        patient = await one(
            conn, "SELECT * FROM healthsync.patients WHERE id=%s FOR UPDATE", (item["patient_id"],)
        )
        await audit(conn, patient["id"], "READ_RETENTION_REVIEW", "patients", patient["id"])
        if (
            patient["legal_hold"]
            or patient["retention_until"] is None
            or patient["retention_until"] > datetime.now(UTC)
        ):
            raise HTTPException(
                409, "Conservación pendiente o bloqueo legal; requiere revisión documentada"
            )
        if await one(
            conn,
            "SELECT 1 FROM healthsync.exam_results WHERE patient_id=%s AND deleted_at IS NULL LIMIT 1",
            (patient["id"],),
        ):
            raise HTTPException(
                409, "Primero debe completarse la eliminación autorizada del almacenamiento"
            )
        if await one(
            conn,
            """
            SELECT 1 FROM healthsync.appointments WHERE patient_id=%s
              AND status IN ('booked','confirmed') AND starts_at>clock_timestamp() LIMIT 1
        """,
            (patient["id"],),
        ):
            raise HTTPException(409, "Primero resuelve las reservas futuras")
        await conn.execute(
            """
            UPDATE healthsync.patients SET pii_ciphertext=NULL,pii_key_id=NULL,email_hmac=NULL,
              auth_user_id=NULL,deleted_at=clock_timestamp(),anonymized_at=clock_timestamp() WHERE id=%s
        """,
            (patient["id"],),
        )
        await conn.execute(
            "UPDATE healthsync.outbox SET cancelled_at=clock_timestamp() WHERE patient_id=%s AND delivered_at IS NULL",
            (patient["id"],),
        )
        await conn.execute(
            "UPDATE healthsync.account_enrollments SET expires_at=clock_timestamp() WHERE patient_id=%s",
            (patient["id"],),
        )
        await conn.execute(
            "UPDATE healthsync.consents SET withdrawn_at=coalesce(withdrawn_at,clock_timestamp()) WHERE patient_id=%s",
            (patient["id"],),
        )
        await conn.execute(
            "UPDATE healthsync.care_relationships SET revoked_at=clock_timestamp() WHERE patient_id=%s AND revoked_at IS NULL",
            (patient["id"],),
        )
        await conn.execute(
            """
            UPDATE healthsync.privacy_requests SET state='completed',decided_by=%s,completed_at=clock_timestamp()
            WHERE id=%s
        """,
            (principal.subject, request_id),
        )
        # Last: erase IP ciphertexts, including the audit events emitted by this transaction.
        await conn.execute(
            "UPDATE healthsync.privacy_contexts SET ip_ciphertext=NULL,key_id=NULL WHERE patient_id=%s",
            (patient["id"],),
        )
        return {"state": "completed", "retained": "pseudonymous scheduling and audit evidence"}


async def authorized_result(conn, result_id, principal):
    require_login(principal)
    role = await staff_role(conn, principal)
    # A clinician additionally needs a current, explicitly granted care relationship.
    row = await one(
        conn,
        """
        SELECT e.* FROM healthsync.exam_results e
        JOIN healthsync.patients p ON (p.tenant_id,p.id)=(e.tenant_id,e.patient_id)
        JOIN healthsync.tenant_modules m ON m.tenant_id=e.tenant_id AND m.code='vault' AND m.enabled
        WHERE e.id=%s AND e.scan_status='clean' AND e.deleted_at IS NULL AND p.deleted_at IS NULL
          AND (p.auth_user_id=%s OR (%s AND EXISTS (
            SELECT 1 FROM healthsync.care_relationships c
            WHERE (c.tenant_id,c.patient_id)=(e.tenant_id,e.patient_id)
              AND c.clinician_id=%s AND c.revoked_at IS NULL
              AND c.valid_until>clock_timestamp())))
    """,
        (result_id, principal.subject, role == "clinician", principal.subject),
    )
    if not row:
        raise HTTPException(404, "Resultado no disponible")
    await audit(conn, row["patient_id"], "READ_RESULT_METADATA", "exam_results", row["id"])
    return row


@app.post("/v1/{tenant_id}/exam-results/{result_id}/access")
async def result_access(
    tenant_id: UUID,
    result_id: UUID,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        row = await authorized_result(conn, result_id, principal)
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(principal.subject),
                "tenant": str(tenant_id),
                "result": str(result_id),
                "purpose": "vault",
                "iat": now,
                "exp": now + timedelta(minutes=15),
            },
            base64.b64decode(settings().vault_signing_key_base64),
            algorithm="HS256",
        )
        await audit(conn, row["patient_id"], "ISSUE_RESULT_LINK", "exam_results", row["id"])
        return {
            "path": f"/v1/{tenant_id}/vault/{token}",
            "expires_in": 900,
            "authorization_required": True,
        }


def read_private_pdf(key: str, expected_size: int):
    if not settings().vault_bucket or not settings().vault_kms_key_id:
        raise HTTPException(503, "Vault no configurado")
    client = boto3.client("s3", region_name=settings().vault_region)
    response = client.get_object(Bucket=settings().vault_bucket, Key=key)
    stream = response["Body"]
    try:
        if (
            response.get("ServerSideEncryption") != "aws:kms"
            or response.get("SSEKMSKeyId") != settings().vault_kms_key_id
            or response.get("ContentLength") != expected_size
        ):
            raise HTTPException(503, "Objeto fuera de la política de seguridad")
        content = stream.read(20 * 1024 * 1024 + 1)
    finally:
        stream.close()
    if len(content) != expected_size or not content.startswith(b"%PDF-"):
        raise HTTPException(503, "Resultado inválido")
    return content


@app.get("/v1/{tenant_id}/vault/{token}")
async def open_result(
    tenant_id: UUID,
    token: str,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    require_login(principal)
    try:
        claims = jwt.decode(
            token,
            base64.b64decode(settings().vault_signing_key_base64),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "tenant", "result", "purpose"]},
        )
        if (
            claims["sub"] != str(principal.subject)
            or claims["tenant"] != str(tenant_id)
            or claims["purpose"] != "vault"
        ):
            raise ValueError()
        result_id = UUID(claims["result"])
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(403, "Enlace inválido o vencido") from None
    import hashlib

    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        row = await authorized_result(conn, result_id, principal)
        content = await run_in_threadpool(read_private_pdf, row["object_key"], row["byte_size"])
        if hashlib.sha256(content).digest() != bytes(row["content_sha256"]):
            raise HTTPException(503, "No se pudo verificar la integridad del resultado")
        await audit(conn, row["patient_id"], "READ_RESULT", "exam_results", row["id"])
    # The audit transaction commits BEFORE bytes leave the service. Every open traverses it.
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="resultado.pdf"',
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )
