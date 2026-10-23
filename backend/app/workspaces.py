"""Operational workspaces authorized on the server, never by UI navigation."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from . import db
from .auth import Principal, optional_principal
from .config import settings
from .crypto import decrypt, encrypt
from .db import audit, many, one, staff_role, transaction

router = APIRouter()
CAPABILITIES = {
    "admin": [
        "organization.read",
        "calendar.read",
        "attendance.write",
        "reports.read",
        "team.manage",
    ],
    "scheduler": ["organization.read", "calendar.read", "attendance.write", "reports.read"],
    "reception": ["organization.read", "calendar.read", "attendance.write", "reports.read"],
    "clinician": ["organization.read", "calendar.read", "attendance.write", "reports.read"],
    "finance": ["organization.read", "reports.read"],
    "privacy": [],
}
SCOPE_SQL = """(%s OR (%s AND EXISTS (
    SELECT 1 FROM healthsync.membership_branches mb
    WHERE mb.tenant_id=r.tenant_id AND mb.branch_id=r.branch_id AND mb.auth_user_id=%s
  )) OR (%s AND EXISTS (
    SELECT 1 FROM healthsync.clinician_resources cr
    WHERE cr.tenant_id=r.tenant_id AND cr.resource_id=r.id AND cr.auth_user_id=%s
  )))"""


def scope_params(role, principal):
    return (
        role == "admin",
        role in ("scheduler", "reception", "finance"),
        principal.subject,
        role == "clinician",
        principal.subject,
    )


def require_user(principal):
    if principal is None:
        raise HTTPException(401, "Inicia sesión para acceder a tu espacio")


async def require_capability(conn, principal, capability):
    require_user(principal)
    role = await staff_role(conn, principal)
    if capability not in CAPABILITIES.get(role, []):
        raise HTTPException(403, "Tu perfil no tiene acceso a esta función")
    return role


async def workspace_audit(conn, principal, action):
    await conn.execute(
        """INSERT INTO healthsync.workspace_events
      (tenant_id,actor_id,action,request_id,ip_ciphertext,key_id)
      VALUES (healthsync.current_tenant(),%s,%s,current_setting('app.request_id')::uuid,
        decode(current_setting('app.ip_ciphertext'),'hex'),current_setting('app.ip_key_id'))
    """,
        (principal.subject, action),
    )


@router.get("/v1/{tenant_id}/session")
async def session(
    tenant_id: UUID, request: Request, principal: Principal | None = Depends(optional_principal)
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        role = await staff_role(conn, principal)
        operator = await one(conn, "SELECT role FROM platform.operators") if principal else None
        return {
            "authenticated": principal is not None,
            "role": role,
            "capabilities": CAPABILITIES.get(role, []),
            "platform_role": operator["role"] if operator else None,
        }


@router.get("/v1/{tenant_id}/organization")
async def organization(
    tenant_id: UUID, request: Request, principal: Principal | None = Depends(optional_principal)
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        role = await require_capability(conn, principal, "organization.read")
        branches = await many(
            conn,
            """SELECT DISTINCT b.id,b.name,b.timezone,bl.organization_unit_id
          FROM healthsync.branches b
          LEFT JOIN healthsync.branch_locations bl ON (bl.tenant_id,bl.branch_id)=(b.tenant_id,b.id)
          WHERE %s OR EXISTS (SELECT 1 FROM healthsync.membership_branches mb
            WHERE mb.tenant_id=b.tenant_id AND mb.branch_id=b.id AND mb.auth_user_id=%s AND %s)
          OR EXISTS (SELECT 1 FROM healthsync.resources r JOIN healthsync.clinician_resources cr
            ON (cr.tenant_id,cr.resource_id)=(r.tenant_id,r.id)
            WHERE r.tenant_id=b.tenant_id AND r.branch_id=b.id AND cr.auth_user_id=%s AND %s)
          ORDER BY b.name
        """,
            (
                role == "admin",
                principal.subject,
                role in ("scheduler", "reception", "finance"),
                principal.subject,
                role == "clinician",
            ),
        )
        units = await many(
            conn,
            """WITH RECURSIVE visible_units AS (
          SELECT u.* FROM healthsync.organization_units u WHERE %s OR u.id=ANY(%s::uuid[])
          UNION SELECT u.* FROM healthsync.organization_units u JOIN visible_units v
            ON (u.tenant_id,u.id)=(v.tenant_id,v.parent_id)
          ) SELECT * FROM visible_units ORDER BY name
        """,
            (
                role == "admin",
                [b["organization_unit_id"] for b in branches if b["organization_unit_id"]],
            ),
        )
        await workspace_audit(conn, principal, "organization.read")
        return {"branches": branches, "units": units}


@router.get("/v1/{tenant_id}/staff/appointments")
async def calendar(
    tenant_id: UUID,
    day: date,
    request: Request,
    branch_id: UUID | None = None,
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(50, ge=1, le=100),
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        role = await require_capability(conn, principal, "calendar.read")
        rows = await many(
            conn,
            """SELECT a.id,a.patient_id,a.starts_at,a.ends_at,a.status,a.version,
            s.name AS service_name,r.public_name,b.name AS branch,b.timezone,
            p.pii_ciphertext,p.pii_key_id,ar.checked_in_at
          FROM healthsync.appointments a
          JOIN healthsync.patients p ON (p.tenant_id,p.id)=(a.tenant_id,a.patient_id)
          JOIN healthsync.resources r ON (r.tenant_id,r.id)=(a.tenant_id,a.resource_id)
          JOIN healthsync.services s ON (s.tenant_id,s.id)=(a.tenant_id,a.service_id)
          JOIN healthsync.branches b ON (b.tenant_id,b.id)=(r.tenant_id,r.branch_id)
          LEFT JOIN healthsync.attendance_records ar ON (ar.tenant_id,ar.appointment_id)=(a.tenant_id,a.id)
          WHERE p.deleted_at IS NULL AND (a.starts_at AT TIME ZONE b.timezone)::date=%s
            AND (%s::uuid IS NULL OR b.id=%s::uuid) AND """
            + SCOPE_SQL
            + """
          ORDER BY a.starts_at,a.id LIMIT %s OFFSET %s
        """,
            (day, branch_id, branch_id, *scope_params(role, principal), limit + 1, offset),
        )
        for row in rows:
            await audit(conn, row["patient_id"], "READ_STAFF_CALENDAR", "appointments", row["id"])
        items = rows[:limit]
        for row in items:
            pii = decrypt(
                bytes(row.pop("pii_ciphertext")),
                row.pop("pii_key_id"),
                f"patient:{tenant_id}:{row['patient_id']}",
            )
            row["patient_name"] = pii["name"]
        return {"items": items, "has_more": len(rows) > limit}


@router.get("/v1/{tenant_id}/staff/summary")
async def summary(
    tenant_id: UUID,
    day: date,
    request: Request,
    branch_id: UUID | None = None,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        role = await require_capability(conn, principal, "reports.read")
        rows = await many(
            conn,
            """SELECT a.status,count(*)::integer AS count
          FROM healthsync.appointments a
          JOIN healthsync.resources r ON (r.tenant_id,r.id)=(a.tenant_id,a.resource_id)
          JOIN healthsync.branches b ON (b.tenant_id,b.id)=(r.tenant_id,r.branch_id)
          WHERE (a.starts_at AT TIME ZONE b.timezone)::date=%s
            AND (%s::uuid IS NULL OR b.id=%s::uuid) AND """
            + SCOPE_SQL
            + """ GROUP BY a.status
        """,
            (day, branch_id, branch_id, *scope_params(role, principal)),
        )
        await workspace_audit(conn, principal, "reports.daily_summary.read")
        return {
            "day": day,
            "counts": {r["status"]: r["count"] for r in rows},
            "measure": "appointments_not_unique_people",
        }


class AttendanceAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["check_in", "complete", "no_show"]
    expected_version: int = Field(ge=1)


@router.post("/v1/{tenant_id}/staff/appointments/{appointment_id}/attendance")
async def attendance(
    tenant_id: UUID,
    appointment_id: UUID,
    payload: AttendanceAction,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _tenant):
        role = await require_capability(conn, principal, "attendance.write")
        if payload.action == "complete" and role not in ("admin", "clinician"):
            raise HTTPException(
                403, "Solo el profesional o administrador puede cerrar una atención"
            )
        appt = await one(
            conn,
            """SELECT a.* FROM healthsync.appointments a
          JOIN healthsync.resources r ON (r.tenant_id,r.id)=(a.tenant_id,a.resource_id)
          JOIN healthsync.patients p ON (p.tenant_id,p.id)=(a.tenant_id,a.patient_id)
          WHERE a.id=%s AND p.deleted_at IS NULL AND """
            + SCOPE_SQL
            + """ FOR UPDATE OF a
        """,
            (appointment_id, *scope_params(role, principal)),
        )
        if not appt:
            raise HTTPException(404, "Cita no disponible")
        await audit(conn, appt["patient_id"], "READ_ATTENDANCE", "appointments", appt["id"])
        if appt["version"] != payload.expected_version or appt["status"] not in (
            "booked",
            "confirmed",
        ):
            raise HTTPException(409, "La cita cambió o ya está cerrada; actualiza la agenda")
        now = datetime.now(UTC)
        if payload.action == "check_in" and not now - timedelta(days=1) <= appt[
            "starts_at"
        ] <= now + timedelta(hours=1):
            raise HTTPException(409, "La recepción se habilita desde una hora antes de la cita")
        if payload.action == "complete" and appt["starts_at"] > now:
            raise HTTPException(409, "La cita todavía no comienza")
        if payload.action == "no_show" and appt["starts_at"] + timedelta(minutes=10) > now:
            raise HTTPException(409, "Espera al menos 10 minutos desde la hora programada")
        existing = await one(
            conn,
            "SELECT * FROM healthsync.attendance_records WHERE appointment_id=%s",
            (appointment_id,),
        )
        if payload.action == "check_in" and existing and existing["checked_in_at"]:
            return {
                "status": appt["status"],
                "version": appt["version"],
                "checked_in_at": existing["checked_in_at"],
            }
        outcome = (
            None
            if payload.action == "check_in"
            else ("completed" if payload.action == "complete" else "no_show")
        )
        await conn.execute(
            """INSERT INTO healthsync.attendance_records
          (tenant_id,appointment_id,patient_id,checked_in_at,completed_at,outcome,recorded_by)
          VALUES (%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT (tenant_id,appointment_id) DO UPDATE SET
            checked_in_at=coalesce(healthsync.attendance_records.checked_in_at,EXCLUDED.checked_in_at),
            completed_at=EXCLUDED.completed_at,outcome=EXCLUDED.outcome,recorded_by=EXCLUDED.recorded_by
        """,
            (
                tenant_id,
                appointment_id,
                appt["patient_id"],
                now if payload.action == "check_in" else None,
                now if outcome == "completed" else None,
                outcome,
                principal.subject,
            ),
        )
        if outcome:
            await conn.execute(
                "UPDATE healthsync.appointments SET status=%s,version=version+1 WHERE id=%s",
                (outcome, appointment_id),
            )
            await conn.execute(
                """UPDATE healthsync.outbox SET cancelled_at=clock_timestamp()
              WHERE appointment_id=%s AND delivered_at IS NULL AND cancelled_at IS NULL""",
                (appointment_id,),
            )
        return {
            "status": outcome or appt["status"],
            "version": appt["version"] + (1 if outcome else 0),
        }


@router.get("/v1/platform/tenants")
async def platform_directory(
    request: Request, principal: Principal | None = Depends(optional_principal)
):
    require_user(principal)
    from .auth import verify_staff_session

    await verify_staff_session(principal)
    async with db.pool.connection() as conn, conn.transaction():
        await conn.execute("SELECT set_config('app.actor_id',%s,true)", (str(principal.subject),))
        await conn.execute("SELECT set_config('app.tenant_id','',true)")
        if not await one(conn, "SELECT 1 FROM platform.operators"):
            raise HTTPException(403, "Se requiere un administrador del servicio SaaS")
        await conn.execute(
            """INSERT INTO platform.operator_events
          (actor_id,action,request_id,ip_ciphertext,key_id) VALUES (%s,%s,%s,%s,%s)""",
            (
                principal.subject,
                "tenant_directory.read",
                uuid4(),
                encrypt(
                    {"ip": request.client.host if request.client else "unknown"},
                    "ip:00000000-0000-4000-8000-000000000001",
                ),
                settings().pii_key_id,
            ),
        )
        return {
            "tenants": await many(conn, "SELECT * FROM platform.tenant_directory ORDER BY name"),
            "scope": "organization_metadata_only",
        }
