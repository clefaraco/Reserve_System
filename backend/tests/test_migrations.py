import importlib.util
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql


def test_incremental_migrations_preserve_bookings_repeat_and_reject_tampering(
    test_database, tmp_path
):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "medical_migrations", root / "scripts/migrations.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    name = "healthsync_migration_test_" + uuid4().hex
    owner = {**test_database, "dbname": "postgres"}
    with psycopg.connect(**owner, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        with psycopg.connect(**{**owner, "dbname": name}) as conn:
            conn.execute((root / "database/001_schema.sql").read_text(encoding="utf-8"))
            conn.execute((root / "database/002_demo.sql").read_text(encoding="utf-8"))
            tenant = "10000000-0000-4000-8000-000000000001"
            for key, value in {
                "app.tenant_id": tenant,
                "app.request_id": str(uuid4()),
                "app.actor_type": "guest",
            }.items():
                conn.execute("SELECT set_config(%s,%s,true)", (key, value))
            patient = uuid4()
            appointment = uuid4()
            conn.execute(
                "INSERT INTO healthsync.patients (tenant_id,id,pii_ciphertext,pii_key_id) VALUES (%s,%s,'test'::bytea,'test')",
                (tenant, patient),
            )
            conn.execute(
                """INSERT INTO healthsync.appointments
              (tenant_id,id,patient_id,resource_id,service_id,starts_at,ends_at,occupied_until,duration_minutes,buffer_minutes)
              VALUES (%s,%s,%s,'40000000-0000-4000-8000-000000000001','50000000-0000-4000-8000-000000000001',
                '2030-05-01 10:00+00','2030-05-01 10:30+00','2030-05-01 10:45+00',30,15)""",
                (tenant, appointment, patient),
            )
            conn.commit()
            original_audit = conn.execute(
                "SELECT count(*) FROM healthsync.audit_events"
            ).fetchone()[0]
            module.apply_incremental(conn, root)
            conn.commit()
            module.apply_incremental(conn, root)
            conn.commit()
            assert (
                conn.execute("SELECT id FROM healthsync.appointments").fetchone()[0] == appointment
            )
            assert conn.execute("SELECT id FROM healthsync.patients").fetchone()[0] == patient
            assert (
                conn.execute("SELECT count(*) FROM healthsync.audit_events").fetchone()[0]
                == original_audit
            )
            assert conn.execute("SELECT count(*) FROM migration_meta.versions").fetchone()[0] == 2
            # A changed applied migration is rejected instead of silently replayed.
            (tmp_path / "database").mkdir()
            target = tmp_path / "database/003_organization_and_workspaces.sql"
            target.write_text(
                (root / "database/003_organization_and_workspaces.sql").read_text(encoding="utf-8")
                + "\n-- altered",
                encoding="utf-8",
            )
            with pytest.raises(RuntimeError, match="Applied migration changed"):
                module.apply_incremental(conn, tmp_path)
            conn.rollback()
    finally:
        with psycopg.connect(**owner, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
