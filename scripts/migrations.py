"""Incremental local migrations; checksum changes fail closed instead of resetting data."""

import hashlib
from pathlib import Path


def apply_incremental(conn, root: Path):
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('medical-migrations',0))")
    conn.execute("CREATE SCHEMA IF NOT EXISTS migration_meta")
    conn.execute("REVOKE ALL ON SCHEMA migration_meta FROM PUBLIC")
    conn.execute("""CREATE TABLE IF NOT EXISTS migration_meta.versions (
        tenant_id uuid NOT NULL DEFAULT '00000000-0000-4000-8000-000000000001',
        version text NOT NULL, checksum bytea NOT NULL,
        applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY (tenant_id,version))""")
    conn.execute("REVOKE ALL ON migration_meta.versions FROM PUBLIC")
    conn.execute("ALTER TABLE migration_meta.versions ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE migration_meta.versions FORCE ROW LEVEL SECURITY")
    for path in sorted((root / "database").glob("*.sql")):
        if path.name[:3] < "003":
            continue
        content = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode()).digest()
        row = conn.execute(
            "SELECT checksum FROM migration_meta.versions WHERE version=%s", (path.name,)
        ).fetchone()
        if row:
            if bytes(row[0]) != checksum:
                raise RuntimeError(
                    f"Applied migration changed: {path.name}; add a new migration instead."
                )
            continue
        # Existing SQL files include BEGIN/COMMIT. Execute their body inside the
        # caller's transaction so the schema and version record commit together.
        statements = content.strip().removesuffix("COMMIT;")
        begin = statements.find("BEGIN;")
        if begin < 0:
            raise RuntimeError("Migration requires an explicit transaction wrapper")
        conn.execute(statements[:begin] + statements[begin + 6 :])
        conn.execute(
            "INSERT INTO migration_meta.versions (version,checksum) VALUES (%s,%s)",
            (path.name, checksum),
        )
        print(f"Applied migration: {path.name}")
