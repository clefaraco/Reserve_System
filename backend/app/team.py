"""Tenant personnel. All permissions are read live, all writes serialize per tenant."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .auth import Principal, optional_principal, verify_staff_session
from .config import settings
from .crypto import decrypt, email_index, encrypt
from .db import many, one, staff_role, transaction

router = APIRouter()
Role = Literal["admin", "scheduler", "reception", "clinician", "finance", "privacy"]
PERMISSIONS = {
    "admin": "Gestiona equipo y toda la clínica; no administra el SaaS.",
    "scheduler": "Agenda y cambios solo de sucursales asignadas.",
    "reception": "Recepción y agenda de sucursales asignadas; no cierre clínico.",
    "clinician": "Agendas asignadas; resultados requieren además relación asistencial.",
    "finance": "Resumen agregado de sucursales asignadas; sin nombres ni PDFs.",
    "privacy": "Procedimientos de privacidad autorizados; sin agenda general.",
}


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role
    branches: list[UUID] = Field(default_factory=list, max_length=100)
    resources: list[UUID] = Field(default_factory=list, max_length=100)


class Invitation(Scope):
    email: EmailStr


class InviteChange(Scope):
    expected_version: int = Field(ge=1)


class MemberChange(Scope):
    expected_version: int = Field(ge=1)
    active: bool


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class Acceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=40, max_length=100, repr=False)


async def serialize(conn):
    # Acquire BEFORE loading actor, target or count. Every protected change rechecks
    # current authorization after the lock, avoiding stale grants during a wait.
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended('staff-access:'||healthsync.current_tenant()::text,0))"
    )


async def admin(conn, principal, *, writing=False):
    if writing:
        await serialize(conn)
    if await staff_role(conn, principal) != "admin":
        raise HTTPException(403, "Solo administración de esta clínica puede gestionar el equipo")


async def validate_scope(conn, scope):
    if len(set(scope.branches)) != len(scope.branches) or len(set(scope.resources)) != len(
        scope.resources
    ):
        raise HTTPException(422, "No repitas sucursales o agendas")
    if scope.role in ("admin", "privacy") and (scope.branches or scope.resources):
        raise HTTPException(422, "Este perfil no utiliza asignación de sucursales ni agendas")
    if scope.role == "clinician" and (scope.branches or not scope.resources):
        raise HTTPException(422, "El perfil médico requiere agendas, sin sucursales adicionales")
    if scope.role in ("scheduler", "reception", "finance") and (
        scope.resources or not scope.branches
    ):
        raise HTTPException(422, "Asigna al menos una sucursal y ninguna agenda individual")
    branches = await many(
        conn, "SELECT id FROM healthsync.branches WHERE id=ANY(%s)", (scope.branches,)
    )
    resources = await many(
        conn, "SELECT id FROM healthsync.resources WHERE id=ANY(%s) AND active", (scope.resources,)
    )
    if len(branches) != len(scope.branches) or len(resources) != len(scope.resources):
        raise HTTPException(422, "Sucursales o agendas no disponibles para esta clínica")


async def revoke_pending(conn, contact):
    await conn.execute(
        """UPDATE healthsync.staff_invitations SET revoked_at=clock_timestamp(),version=version+1
        WHERE contact_id=%s AND accepted_at IS NULL AND revoked_at IS NULL""",
        (contact,),
    )
    await conn.execute(
        """UPDATE healthsync.staff_deliveries d SET state='superseded'
        FROM healthsync.staff_invitations i WHERE (i.tenant_id,i.id)=(d.tenant_id,d.invitation_id)
        AND i.contact_id=%s AND i.revoked_at IS NOT NULL AND d.state='queued' """,
        (contact,),
    )


async def issue(conn, tenant_id, payload, *, contact_id=None, replace_existing=False):
    await validate_scope(conn, payload)
    if contact_id is None:
        contact = await one(
            conn,
            "SELECT id FROM healthsync.staff_contacts WHERE email_hmac=%s",
            (email_index(tenant_id, str(payload.email)),),
        )
        if contact:
            contact_id = contact["id"]
        else:
            contact_id = uuid4()
            await conn.execute(
                """INSERT INTO healthsync.staff_contacts
                (tenant_id,id,email_hmac,email_ciphertext,key_id) VALUES (%s,%s,%s,%s,%s)""",
                (
                    tenant_id,
                    contact_id,
                    email_index(tenant_id, str(payload.email)),
                    encrypt(
                        {"email": str(payload.email).strip().lower()},
                        f"staff:{tenant_id}:{contact_id}",
                    ),
                    settings().pii_key_id,
                ),
            )
    if await one(conn, "SELECT 1 FROM healthsync.memberships WHERE contact_id=%s", (contact_id,)):
        raise HTTPException(409, "Esta persona ya tiene membresía; modifica o reactiva su acceso")
    if not replace_existing and await one(
        conn,
        """SELECT 1 FROM healthsync.staff_invitations
            WHERE contact_id=%s AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at>clock_timestamp()""",
        (contact_id,),
    ):
        raise HTTPException(
            409, "Ya existe una invitación pendiente; actualízala o reenvíala desde Equipo"
        )
    await revoke_pending(conn, contact_id)
    token = secrets.token_urlsafe(32)
    invite_id, delivery_id = uuid4(), uuid4()
    await conn.execute(
        """INSERT INTO healthsync.staff_invitations
        (tenant_id,id,contact_id,role,token_hash) VALUES (%s,%s,%s,%s,%s)""",
        (tenant_id, invite_id, contact_id, payload.role, hashlib.sha256(token.encode()).digest()),
    )
    for branch in payload.branches:
        await conn.execute(
            "INSERT INTO healthsync.invitation_branches VALUES (%s,%s,%s)",
            (tenant_id, invite_id, branch),
        )
    for resource in payload.resources:
        await conn.execute(
            "INSERT INTO healthsync.invitation_resources VALUES (%s,%s,%s)",
            (tenant_id, invite_id, resource),
        )
    await conn.execute(
        """INSERT INTO healthsync.staff_deliveries
        (tenant_id,id,invitation_id,token_ciphertext,key_id) VALUES (%s,%s,%s,%s,%s)""",
        (
            tenant_id,
            delivery_id,
            invite_id,
            encrypt({"token": token}, f"staff-delivery:{tenant_id}:{delivery_id}"),
            settings().pii_key_id,
        ),
    )
    return {"id": invite_id, "state": "pending", "delivery_state": "queued", "version": 1}


async def scopes(conn, table, column, key, value):
    # Table/column/key are internal constants only.
    return [
        r[column]
        for r in await many(
            conn,
            f"SELECT {column} FROM healthsync.{table} WHERE {key}=%s ORDER BY {column}",
            (value,),
        )
    ]


async def directory(
    tenant_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(20, ge=1, le=50),
    search: str = Query("", max_length=100),
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _):
        await admin(conn, principal)
        # Search uses exact normalized email HMAC; no decrypted directory scan.
        rows = await many(
            conn,
            """SELECT m.auth_user_id AS id,m.role,m.active,m.version,c.id AS contact_id,
            c.email_ciphertext,c.key_id,'member' AS kind,NULL::timestamptz AS expires_at,
            NULL::text AS delivery_state,CASE WHEN m.active THEN 'active' ELSE 'inactive' END AS state
          FROM healthsync.memberships m LEFT JOIN healthsync.staff_contacts c ON (c.tenant_id,c.id)=(m.tenant_id,m.contact_id)
          WHERE (%s='' OR c.email_hmac=%s)
          UNION ALL
          SELECT i.id,i.role,false,i.version,c.id,c.email_ciphertext,c.key_id,'invitation',i.expires_at,d.state,
            CASE WHEN i.accepted_at IS NOT NULL THEN 'accepted' WHEN i.revoked_at IS NOT NULL THEN 'revoked'
              WHEN i.expires_at<=clock_timestamp() THEN 'expired' ELSE 'pending' END
          FROM healthsync.staff_invitations i JOIN healthsync.staff_contacts c ON (c.tenant_id,c.id)=(i.tenant_id,i.contact_id)
          JOIN healthsync.staff_deliveries d ON (d.tenant_id,d.invitation_id)=(i.tenant_id,i.id)
          WHERE (%s='' OR c.email_hmac=%s)
          ORDER BY kind,id LIMIT %s OFFSET %s""",
            (
                search,
                email_index(tenant_id, search),
                search,
                email_index(tenant_id, search),
                limit + 1,
                offset,
            ),
        )
        for r in rows[:limit]:
            r["email"] = (
                decrypt(
                    bytes(r.pop("email_ciphertext")),
                    r.pop("key_id"),
                    f"staff:{tenant_id}:{r['contact_id']}",
                )["email"]
                if r["email_ciphertext"]
                else "Contacto pendiente de vinculación"
            )
            # Legacy rows have no contact. Never expose encryption fields.
            r.pop("email_ciphertext", None)
            r.pop("key_id", None)
            r.pop("contact_id", None)
            member = r["kind"] == "member"
            r["branches"] = await scopes(
                conn,
                "membership_branches" if member else "invitation_branches",
                "branch_id",
                "auth_user_id" if member else "invitation_id",
                r["id"],
            )
            r["resources"] = await scopes(
                conn,
                "clinician_resources" if member else "invitation_resources",
                "resource_id",
                "auth_user_id" if member else "invitation_id",
                r["id"],
            )
        await read_audit(conn, principal)
        return {"items": rows[:limit], "has_more": len(rows) > limit, "permissions": PERMISSIONS}


async def read_audit(conn, principal):
    from .workspaces import workspace_audit

    await workspace_audit(conn, principal, "team.directory.read")


@router.get("/v1/{tenant_id}/team/options")
async def options(
    tenant_id: UUID, request: Request, principal: Principal | None = Depends(optional_principal)
):
    async with transaction(tenant_id, request, principal) as (conn, _):
        await admin(conn, principal)
        return {
            "branches": await many(conn, "SELECT id,name FROM healthsync.branches ORDER BY name"),
            "resources": await many(
                conn,
                "SELECT id,public_name AS name,branch_id FROM healthsync.resources WHERE active ORDER BY public_name",
            ),
            "permissions": PERMISSIONS,
        }


@router.post("/v1/{tenant_id}/team/invitations", status_code=201)
async def invite(
    tenant_id: UUID,
    payload: Invitation,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _):
        await admin(conn, principal, writing=True)
        return await issue(conn, tenant_id, payload)


@router.post("/v1/{tenant_id}/team/invitations/{invitation_id}/{action}")
async def invitation_action(
    tenant_id: UUID,
    invitation_id: UUID,
    action: Literal["revoke", "resend"],
    payload: Version,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _):
        await admin(conn, principal, writing=True)
        row = await one(
            conn,
            "SELECT * FROM healthsync.staff_invitations WHERE id=%s FOR UPDATE",
            (invitation_id,),
        )
        if not row:
            raise HTTPException(404, "Invitación no disponible")
        if row["version"] != payload.expected_version or row["accepted_at"] or row["revoked_at"]:
            raise HTTPException(409, "La invitación cambió; actualiza Equipo")
        if action == "revoke":
            await revoke_pending(conn, row["contact_id"])
            return {"state": "revoked"}
        scope = Scope(
            role=row["role"],
            branches=await scopes(
                conn, "invitation_branches", "branch_id", "invitation_id", invitation_id
            ),
            resources=await scopes(
                conn, "invitation_resources", "resource_id", "invitation_id", invitation_id
            ),
        )
        return await issue(
            conn, tenant_id, scope, contact_id=row["contact_id"], replace_existing=True
        )


@router.patch("/v1/{tenant_id}/team/members/{user_id}")
async def change_member(
    tenant_id: UUID,
    user_id: UUID,
    payload: MemberChange,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _):
        await admin(conn, principal, writing=True)
        await validate_scope(conn, payload)
        row = await one(
            conn,
            "SELECT * FROM healthsync.memberships WHERE auth_user_id=%s FOR UPDATE",
            (user_id,),
        )
        if not row:
            raise HTTPException(404, "Acceso no disponible")
        if row["version"] != payload.expected_version:
            raise HTTPException(409, "Los permisos cambiaron; recarga antes de guardar")
        if (
            row["active"]
            and row["role"] == "admin"
            and (not payload.active or payload.role != "admin")
        ):
            count = await one(
                conn,
                "SELECT count(*) AS n FROM healthsync.memberships WHERE active AND role='admin'",
            )
            if count["n"] <= 1:
                raise HTTPException(409, "Debe permanecer al menos un administrador activo")
        await conn.execute(
            "UPDATE healthsync.memberships SET role=%s,active=%s,version=version+1 WHERE auth_user_id=%s",
            (payload.role, payload.active, user_id),
        )
        await conn.execute(
            "DELETE FROM healthsync.membership_branches WHERE auth_user_id=%s", (user_id,)
        )
        await conn.execute(
            "DELETE FROM healthsync.clinician_resources WHERE auth_user_id=%s", (user_id,)
        )
        for branch in payload.branches:
            await conn.execute(
                "INSERT INTO healthsync.membership_branches VALUES (%s,%s,%s)",
                (tenant_id, user_id, branch),
            )
        for resource in payload.resources:
            await conn.execute(
                "INSERT INTO healthsync.clinician_resources VALUES (%s,%s,%s)",
                (tenant_id, user_id, resource),
            )
        if row["contact_id"]:
            await revoke_pending(conn, row["contact_id"])
        return {"version": row["version"] + 1, "active": payload.active}


@router.post("/v1/{tenant_id}/team/accept")
async def accept(
    tenant_id: UUID,
    payload: Acceptance,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    if not principal:
        raise HTTPException(401, "Inicia sesión con el correo destinatario y segundo factor")
    email = await verify_staff_session(principal)
    async with transaction(tenant_id, request, principal) as (conn, _):
        await serialize(conn)
        row = await one(
            conn,
            """SELECT i.*,c.email_hmac FROM healthsync.staff_invitations i JOIN healthsync.staff_contacts c
            ON (c.tenant_id,c.id)=(i.tenant_id,i.contact_id) WHERE token_hash=%s FOR UPDATE OF i""",
            (hashlib.sha256(payload.token.encode()).digest(),),
        )
        if (
            not row
            or row["accepted_at"]
            or row["revoked_at"]
            or row["expires_at"] <= datetime.now(UTC)
        ):
            raise HTTPException(409, "Invitación no disponible; solicita una nueva a la clínica")
        if not hmac.compare_digest(bytes(row["email_hmac"]), email_index(tenant_id, email)):
            raise HTTPException(403, "La invitación pertenece a otra identidad verificada")
        if await one(
            conn,
            "SELECT 1 FROM healthsync.memberships WHERE auth_user_id=%s OR contact_id=%s",
            (principal.subject, row["contact_id"]),
        ):
            raise HTTPException(409, "Ya existe un acceso; administración debe revisarlo")
        branches = await scopes(
            conn, "invitation_branches", "branch_id", "invitation_id", row["id"]
        )
        resources = await scopes(
            conn, "invitation_resources", "resource_id", "invitation_id", row["id"]
        )
        await validate_scope(conn, Scope(role=row["role"], branches=branches, resources=resources))
        await conn.execute(
            "INSERT INTO healthsync.memberships(tenant_id,auth_user_id,role,active,contact_id) VALUES (%s,%s,%s,true,%s)",
            (tenant_id, principal.subject, row["role"], row["contact_id"]),
        )
        for branch in branches:
            await conn.execute(
                "INSERT INTO healthsync.membership_branches VALUES (%s,%s,%s)",
                (tenant_id, principal.subject, branch),
            )
        for resource in resources:
            await conn.execute(
                "INSERT INTO healthsync.clinician_resources VALUES (%s,%s,%s)",
                (tenant_id, principal.subject, resource),
            )
        await conn.execute(
            "UPDATE healthsync.staff_invitations SET accepted_at=clock_timestamp(),accepted_by=%s,version=version+1 WHERE id=%s",
            (principal.subject, row["id"]),
        )
        # Pending email must never be sent after acceptance.
        await conn.execute(
            "UPDATE healthsync.staff_deliveries SET state='superseded' WHERE invitation_id=%s AND state='queued'",
            (row["id"],),
        )
        return {"state": "active", "role": row["role"]}


async def bootstrap(conn, tenant_id, principal, email):
    """CLI only. No public route. Operator owner + verified MFA + zero existing staff."""
    await verify_staff_session(principal)
    await serialize(conn)
    operator = await one(conn, "SELECT 1 FROM platform.operators WHERE role='owner'")
    if not operator or await one(conn, "SELECT 1 FROM healthsync.memberships LIMIT 1"):
        raise HTTPException(403, "Bootstrap requiere operador propietario y clínica sin personal")
    result = await issue(
        conn, tenant_id, Invitation(email=email, role="admin"), replace_existing=True
    )
    from .workspaces import workspace_audit

    await workspace_audit(conn, principal, "team.bootstrap")
    return result


class DirectorySearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


@router.get("/v1/{tenant_id}/team")
async def team(
    tenant_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(20, ge=1, le=50),
    principal: Principal | None = Depends(optional_principal),
):
    return await directory(tenant_id, request, offset, limit, "", principal)


@router.post("/v1/{tenant_id}/team/search")
async def search_team(
    tenant_id: UUID,
    payload: DirectorySearch,
    request: Request,
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(20, ge=1, le=50),
    principal: Principal | None = Depends(optional_principal),
):
    # Private search value stays out of access-log URLs.
    return await directory(tenant_id, request, offset, limit, str(payload.email), principal)


@router.patch("/v1/{tenant_id}/team/invitations/{invitation_id}")
async def change_invitation(
    tenant_id: UUID,
    invitation_id: UUID,
    payload: InviteChange,
    request: Request,
    principal: Principal | None = Depends(optional_principal),
):
    async with transaction(tenant_id, request, principal) as (conn, _):
        await admin(conn, principal, writing=True)
        row = await one(
            conn,
            "SELECT * FROM healthsync.staff_invitations WHERE id=%s FOR UPDATE",
            (invitation_id,),
        )
        if not row:
            raise HTTPException(404, "Invitación no disponible")
        if row["version"] != payload.expected_version or row["accepted_at"] or row["revoked_at"]:
            raise HTTPException(409, "La invitación cambió; actualiza Equipo")
        return await issue(
            conn, tenant_id, payload, contact_id=row["contact_id"], replace_existing=True
        )
