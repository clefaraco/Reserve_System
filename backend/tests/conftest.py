"""Integration tests use a new, disposable PostgreSQL database per test session."""

import os
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
import pytest_asyncio
from dotenv import dotenv_values
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def test_database():
    values = dotenv_values(ROOT / ".env")
    owner = {
        "host": "127.0.0.1",
        "port": 54322,
        "user": "postgres",
        "password": values["POSTGRES_PASSWORD"],
    }
    name = "healthsync_test_" + uuid4().hex
    with psycopg.connect(**owner, dbname="postgres", autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    with psycopg.connect(**owner, dbname=name) as conn:
        conn.execute((ROOT / "database/001_schema.sql").read_text(encoding="utf-8"))
        conn.execute(
            (ROOT / "database/003_organization_and_workspaces.sql").read_text(encoding="utf-8")
        )
        conn.execute((ROOT / "database/004_platform_access_audit.sql").read_text(encoding="utf-8"))
        conn.execute((ROOT / "database/005_team_access.sql").read_text(encoding="utf-8"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = psycopg.conninfo.make_conninfo(
        host="127.0.0.1",
        port=54322,
        dbname=name,
        user="healthsync_app",
        password=values["APP_DB_PASSWORD"],
    )
    from app.config import settings

    settings.cache_clear()
    yield dict(**owner, dbname=name)
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    settings.cache_clear()
    with psycopg.connect(**owner, dbname="postgres", autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def world(test_database):
    tenant, other, branch, specialty, resource, service = [uuid4() for _ in range(6)]
    with psycopg.connect(**test_database, row_factory=dict_row) as conn:
        conn.execute(
            "INSERT INTO healthsync.tenants (tenant_id,name,country) VALUES (%s,'Test Clinic','CL'),(%s,'Other Clinic','BR')",
            (tenant, other),
        )
        conn.execute(
            "INSERT INTO healthsync.tenant_modules VALUES (%s,'medical',true),(%s,'vault',false)",
            (tenant, tenant),
        )
        conn.execute(
            "INSERT INTO healthsync.branches VALUES (%s,%s,'Branch','UTC')", (tenant, branch)
        )
        conn.execute(
            "INSERT INTO healthsync.specialties VALUES (%s,%s,%s,'medical','Medicine')",
            (tenant, specialty, branch),
        )
        conn.execute(
            "INSERT INTO healthsync.resources VALUES (%s,%s,%s,%s,'Dr Test',true)",
            (tenant, resource, branch, specialty),
        )
        conn.execute(
            "INSERT INTO healthsync.services VALUES (%s,%s,%s,%s,'Consultation',30,15,true)",
            (tenant, service, branch, specialty),
        )
        conn.execute(
            "INSERT INTO healthsync.resource_services VALUES (%s,%s,%s,%s,%s)",
            (tenant, resource, service, branch, specialty),
        )
        conn.execute(
            "INSERT INTO healthsync.availability_rules (tenant_id,resource_id,iso_weekday,opens_at,closes_at) SELECT %s,%s,d,'08:00','20:00' FROM generate_series(1,7) d",
            (tenant, resource),
        )
        docs = []
        for kind in ("terms", "sensitive_data", "whatsapp"):
            row = conn.execute(
                "INSERT INTO healthsync.legal_documents (tenant_id,kind,version,body,body_sha256) VALUES (%s,%s,'1','Test terms',sha256('Test terms'::bytea)) RETURNING id,kind",
                (tenant, kind),
            ).fetchone()
            docs.append(row)
    return {
        "tenant": tenant,
        "other": other,
        "resource": resource,
        "service": service,
        "docs": docs,
        "owner": test_database,
        "base": f"/v1/{tenant}",
    }


@pytest_asyncio.fixture
async def client(test_database):
    from app.main import app

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def login(monkeypatch):
    from app.auth import Principal, optional_principal
    from app.main import app

    async def verified(principal):
        return f"{principal.subject}@example.test"

    monkeypatch.setattr("app.auth.verified_email", verified)

    def set_user(subject=None):
        subject = subject or uuid4()
        app.dependency_overrides[optional_principal] = lambda: Principal(
            subject, "test-only-token", "aal2"
        )
        return subject

    return set_user
