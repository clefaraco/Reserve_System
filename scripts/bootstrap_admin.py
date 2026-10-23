"""Audited, explicit first-admin invitation; never creates a privileged demo user."""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


async def run(tenant):
    from app import db
    from app.auth import decode_token
    from app.team import bootstrap

    # Inputs never appear in CLI history, process arguments or output.
    token = getpass.getpass("Sesión del operador propietario con MFA (oculta): ")
    recipient = getpass.getpass("Correo del primer administrador (oculto): ")
    principal = decode_token(token)
    await db.open_pool()
    try:
        async with db.transaction(tenant, None, principal) as (conn, _):
            result = await bootstrap(conn, tenant, principal, recipient)
        print(
            "Invitación administrativa encolada. No se ha enviado correo. ID:",
            result["id"],
        )
    finally:
        await db.pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", type=UUID, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.tenant))
    except Exception:  # noqa: BLE001 -- redact provider/DB details at this CLI boundary
        # Provider errors could embed URLs or payloads. Operator receives only a safe code.
        raise SystemExit(
            "Bootstrap denegado. Comprueba Auth, MFA, operador propietario y clínica sin personal."
        ) from None
