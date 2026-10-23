"""Local development only. Generate ignored secrets and migrate a dedicated Docker DB."""

import base64
import os
import secrets
import subprocess
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / ".env"
if not path.exists():
    password = secrets.token_urlsafe(32)
    app_password = secrets.token_urlsafe(32)
    key = lambda: base64.b64encode(secrets.token_bytes(32)).decode()
    contents = (
        f"POSTGRES_PASSWORD={password}\nAPP_DB_PASSWORD={app_password}\n"
        f"DATABASE_URL=postgresql://healthsync_app:{app_password}@127.0.0.1:54322/healthsync\n"
        f"PII_KEY_BASE64={key()}\nEMAIL_HMAC_KEY_BASE64={key()}\nVAULT_SIGNING_KEY_BASE64={key()}\n"
        'PII_KEY_ID=local-v1\nCORS_ORIGINS=["http://localhost:5173"]\n'
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(contents)
    print("Generated .env with private development keys (not displayed).")
values = dotenv_values(path)
if not values.get("APP_DB_PASSWORD") or not values.get("POSTGRES_PASSWORD"):
    raise SystemExit("Existing .env preserved. Set POSTGRES_PASSWORD and APP_DB_PASSWORD securely.")
subprocess.run(["docker", "compose", "up", "-d", "--wait", "db"], cwd=ROOT, check=True)
with psycopg.connect(
    host="127.0.0.1",
    port=54322,
    dbname="healthsync",
    user="postgres",
    password=values["POSTGRES_PASSWORD"],
) as conn:
    exists = conn.execute("SELECT to_regclass('healthsync.tenants')").fetchone()[0]
    if not exists:
        conn.execute((ROOT / "database/001_schema.sql").read_text())
        conn.execute(
            sql.SQL("ALTER ROLE healthsync_app PASSWORD {}").format(
                sql.Literal(values["APP_DB_PASSWORD"])
            )
        )
        conn.execute((ROOT / "database/002_demo.sql").read_text())
        print("Applied schema and synthetic demo catalog.")
    else:
        print("Existing database preserved; no migrations or password changes applied.")
print("Local database ready. Start the API and web app using README.md.")
