from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .auth import Principal
from .config import settings
from .crypto import encrypt

pool: AsyncConnectionPool | None = None
read_events: ContextVar[list | None] = ContextVar("read_events", default=None)


async def open_pool():
    global pool
    pool = AsyncConnectionPool(
        settings().database_url,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await pool.open(wait=True)
    async with pool.connection() as conn:
        role = await one(
            conn, "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        owner = await one(
            conn,
            "SELECT bool_or(pg_has_role(current_user,tableowner,'USAGE')) AS owns "
            "FROM pg_tables WHERE schemaname='healthsync'",
        )
        if role["rolsuper"] or role["rolbypassrls"] or not owner or owner["owns"]:
            raise RuntimeError("API must use a non-owner, NOBYPASSRLS healthsync_app role")


async def one(conn, sql: str, params=()):
    return await (await conn.execute(sql, params)).fetchone()


async def many(conn, sql: str, params=()):
    return await (await conn.execute(sql, params)).fetchall()


@asynccontextmanager
async def transaction(
    tenant_id: UUID, request: Request | None, principal: Principal | None, *, worker=False
):
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    request_id = uuid4()  # Never accept a caller-supplied actor or request context.
    # Ignore X-Forwarded-For here. Uvicorn must trust only a configured reverse proxy.
    ip = request.client.host if request and request.client else "worker"
    cipher = encrypt({"ip": ip}, f"ip:{tenant_id}")
    context = {
        "app.tenant_id": str(tenant_id),
        "app.actor_id": str(principal.subject) if principal else "",
        "app.actor_type": "worker" if worker else ("user" if principal else "guest"),
        "app.request_id": str(request_id),
        "app.ip_ciphertext": cipher.hex(),
        "app.ip_key_id": settings().pii_key_id,
    }
    pending = []
    marker = read_events.set(pending)

    async def initialize(conn):
        for key, value in context.items():
            await conn.execute("SELECT set_config(%s,%s,true)", (key, value))
        await conn.execute("SET LOCAL statement_timeout = '10s'")
        await conn.execute("SET LOCAL lock_timeout = '5s'")

    async with pool.connection() as conn:
        try:
            async with conn.transaction():
                await initialize(conn)
                tenant = await one(conn, "SELECT * FROM healthsync.tenants WHERE active")
                if not tenant:
                    raise HTTPException(404, "Clínica no disponible")
                yield conn, tenant
        except Exception:
            # Persist authorized reads even if a later validation rolls back mutations.
            # Mutation triggers themselves stay atomic with the data they describe.
            if pending:
                async with conn.transaction():
                    await initialize(conn)
                    for event in pending:
                        await conn.execute("SELECT healthsync.append_audit(%s,%s,%s,%s)", event)
            raise
        finally:
            read_events.reset(marker)


async def staff_role(conn, principal: Principal | None) -> str | None:
    if principal is None:
        return None
    row = await one(
        conn,
        "SELECT role FROM healthsync.memberships WHERE auth_user_id=%s AND active",
        (principal.subject,),
    )
    return row["role"] if row else None


async def audit(conn, patient_id, action: str, entity: str, entity_id):
    pending = read_events.get()
    if pending is not None:
        pending.append((patient_id, action, entity, entity_id))
    await conn.execute(
        "SELECT healthsync.append_audit(%s,%s,%s,%s)", (patient_id, action, entity, entity_id)
    )
