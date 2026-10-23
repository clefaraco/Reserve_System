import asyncio
import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import psycopg
import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric import rsa
from psycopg.errors import ExclusionViolation, InsufficientPrivilege, RaiseException
from psycopg.rows import dict_row

from app.config import settings
from app.crypto import decrypt, encrypt
from app.db import transaction


def payload(w, *, offset=0, account=False):
    start = (datetime.now(UTC) + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    return {
        "service_id": str(w["service"]),
        "resource_id": str(w["resource"]),
        "starts_at": (start + timedelta(minutes=offset)).isoformat(),
        "patient": {"name": "Paciente Ficticio", "email": "patient@example.com"},
        "consent_document_ids": [str(d["id"]) for d in w["docs"] if d["kind"] != "whatsapp"],
        "create_account": account,
    }


async def book(client, w, data=None, key=None):
    return await client.post(
        w["base"] + "/bookings",
        json=data or payload(w),
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def query(w, statement, params=()):
    with psycopg.connect(**w["owner"], row_factory=dict_row) as conn:
        for key, value in {
            "app.tenant_id": str(w["tenant"]),
            "app.request_id": str(uuid4()),
            "app.actor_type": "worker",
        }.items():
            conn.execute("SELECT set_config(%s,%s,true)", (key, value))
        return conn.execute(statement, params).fetchall()


async def test_booking_encrypts_pii_and_records_consent_ip(client, world):
    response = await book(client, world)
    assert response.status_code == 201, response.text
    patients = query(
        world, "SELECT * FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],)
    )
    patient = patients[0]
    assert b"patient@example.com" not in bytes(patient["pii_ciphertext"])
    assert (
        decrypt(
            bytes(patient["pii_ciphertext"]),
            patient["pii_key_id"],
            f"patient:{world['tenant']}:{patient['id']}",
        )["email"]
        == "patient@example.com"
    )
    consents = query(
        world, "SELECT * FROM healthsync.consents WHERE tenant_id=%s", (world["tenant"],)
    )
    assert len(consents) == 2 and all(c["accepted_at"] for c in consents)
    evidence = query(
        world,
        "SELECT c.* FROM healthsync.audit_events a JOIN healthsync.privacy_contexts c ON (c.tenant_id,c.id)=(a.tenant_id,a.privacy_context_id) WHERE a.tenant_id=%s AND a.entity_type='consents'",
        (world["tenant"],),
    )
    assert len(evidence) == 2
    assert (
        decrypt(
            bytes(evidence[0]["ip_ciphertext"]), evidence[0]["key_id"], f"ip:{world['tenant']}"
        )["ip"]
        == "127.0.0.1"
    )
    assert (
        len(query(world, "SELECT * FROM healthsync.outbox WHERE tenant_id=%s", (world["tenant"],)))
        == 3
    )
    assert response.headers["cache-control"] == "no-store"


async def test_concurrent_bookings_have_one_winner_no_orphans(client, world):
    results = await asyncio.gather(book(client, world), book(client, world))
    assert sorted(r.status_code for r in results) == [201, 409]
    assert (
        len(
            query(
                world, "SELECT id FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],)
            )
        )
        == 1
    )
    assert (
        len(
            query(
                world, "SELECT id FROM healthsync.consents WHERE tenant_id=%s", (world["tenant"],)
            )
        )
        == 2
    )


async def test_database_itself_rejects_concurrent_overlaps(client, world):
    initial = await book(client, world)
    patient = query(
        world, "SELECT patient_id FROM healthsync.appointments WHERE id=%s", (initial.json()["id"],)
    )[0]["patient_id"]
    start = datetime.fromisoformat(payload(world)["starts_at"]) + timedelta(hours=2)

    async def insert(offset):
        try:
            async with transaction(world["tenant"], None, None) as (conn, _):
                await conn.execute(
                    """
                    INSERT INTO healthsync.appointments
                      (tenant_id,patient_id,resource_id,service_id,starts_at,ends_at,occupied_until,duration_minutes,buffer_minutes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,30,15)
                """,
                    (
                        world["tenant"],
                        patient,
                        world["resource"],
                        world["service"],
                        start + timedelta(minutes=offset),
                        start + timedelta(minutes=offset + 30),
                        start + timedelta(minutes=offset + 45),
                    ),
                )
            return "committed"
        except ExclusionViolation:
            return "excluded"

    assert sorted(await asyncio.gather(insert(0), insert(15))) == ["committed", "excluded"]


async def test_buffer_and_adjacent_slots(client, world):
    assert (await book(client, world)).status_code == 201
    assert (await book(client, world, payload(world, offset=30))).status_code == 409
    assert (await book(client, world, payload(world, offset=45))).status_code == 201


async def test_idempotent_retries_and_different_payload(client, world):
    key = uuid4()
    first, second = await asyncio.gather(book(client, world, key=key), book(client, world, key=key))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert (await book(client, world, payload(world, offset=60), key=key)).status_code == 409
    assert (
        len(
            query(
                world, "SELECT id FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],)
            )
        )
        == 1
    )


async def test_rls_fails_closed_and_cross_tenant_writes_fail(client, world):
    from app import db

    await book(client, world)
    async with db.pool.connection() as conn:
        assert await (await conn.execute("SELECT * FROM healthsync.patients")).fetchall() == []
    async with transaction(world["other"], None, None) as (conn, _):
        assert (
            await (
                await conn.execute(
                    "SELECT * FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],)
                )
            ).fetchall()
            == []
        )
    with pytest.raises(InsufficientPrivilege):
        async with transaction(world["other"], None, None) as (conn, _):
            await conn.execute(
                "INSERT INTO healthsync.patients (tenant_id,pii_ciphertext,pii_key_id) VALUES (%s,'x'::bytea,'test')",
                (world["tenant"],),
            )
    assert (await client.get(f"/v1/{world['other']}/catalog")).json()["services"] == []


async def test_confirmed_appointment_can_reschedule_and_stale_update_fails(client, world, login):
    login()
    response = await book(client, world)
    path = world["base"] + "/appointments/" + response.json()["id"]
    confirmed = await client.patch(path, json={"action": "confirm", "expected_version": 1})
    assert confirmed.status_code == 200 and confirmed.json()["version"] == 2
    changed = await client.patch(
        path,
        json={
            "action": "reschedule",
            "expected_version": 2,
            "starts_at": payload(world, offset=60)["starts_at"],
        },
    )
    assert changed.status_code == 200 and changed.json()["status"] == "confirmed"
    assert (
        await client.patch(path, json={"action": "cancel", "expected_version": 2})
    ).status_code == 409
    login()
    assert (
        await client.patch(path, json={"action": "cancel", "expected_version": 3})
    ).status_code == 404


async def test_tenant_cutoff_enforced(client, world, login):
    login()
    query(
        world,
        "UPDATE healthsync.tenants SET cancel_cutoff_minutes=10000,reschedule_cutoff_minutes=10000 WHERE tenant_id=%s RETURNING tenant_id",
        (world["tenant"],),
    )
    response = await book(client, world)
    path = world["base"] + "/appointments/" + response.json()["id"]
    assert (
        await client.patch(path, json={"action": "cancel", "expected_version": 1})
    ).status_code == 409
    assert (
        await client.patch(
            path,
            json={
                "action": "reschedule",
                "expected_version": 1,
                "starts_at": payload(world, offset=60)["starts_at"],
            },
        )
    ).status_code == 409


async def test_old_consent_and_disabled_module_reject_without_patients(client, world):
    data = payload(world)
    data["consent_document_ids"][0] = str(uuid4())
    assert (await book(client, world, data)).status_code == 409
    query(
        world,
        "UPDATE healthsync.tenant_modules SET enabled=false WHERE tenant_id=%s RETURNING code",
        (world["tenant"],),
    )
    assert (await book(client, world)).status_code == 404
    assert (
        query(world, "SELECT id FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],))
        == []
    )


async def test_account_requires_configuration_then_verified_email(
    client, world, login, monkeypatch
):
    from app import main

    monkeypatch.setattr(settings(), "supabase_url", "")
    assert (await book(client, world, payload(world, account=True))).status_code == 503
    monkeypatch.setattr(settings(), "supabase_url", "https://auth.example.com")
    monkeypatch.setattr(settings(), "supabase_publishable_key", "public-test-key")
    result = await book(client, world, payload(world, account=True))
    assert result.status_code == 201 and result.json()["account"] == "queued"
    assert (
        query(
            world,
            "SELECT auth_user_id FROM healthsync.patients WHERE tenant_id=%s",
            (world["tenant"],),
        )[0]["auth_user_id"]
        is None
    )
    user = login()

    async def different_email(principal):
        return "other@example.com"

    monkeypatch.setattr(main, "verified_email", different_email)
    assert (await client.post(world["base"] + "/account/claim")).json()["linked_profiles"] == 0

    async def verified(principal):
        return "patient@example.com"

    monkeypatch.setattr(main, "verified_email", verified)
    assert (await client.post(world["base"] + "/account/claim")).json()["linked_profiles"] == 1
    assert (
        query(
            world,
            "SELECT auth_user_id FROM healthsync.patients WHERE tenant_id=%s",
            (world["tenant"],),
        )[0]["auth_user_id"]
        == user
    )
    assert len((await client.get(world["base"] + "/appointments")).json()) == 1


async def test_export_and_reviewed_anonymization_preserve_audit(client, world, login):
    user = login()
    booking = await book(client, world)
    export = await client.get(world["base"] + "/privacy/export")
    assert export.status_code == 200
    profile = export.json()["profiles"][0]
    assert profile["contact"]["email"] == "patient@example.com" and len(profile["consents"]) == 2
    request = await client.post(
        world["base"] + "/privacy/requests",
        json={"patient_id": profile["patient_id"], "kind": "anonymize"},
    )
    path = world["base"] + "/privacy/requests/" + request.json()["id"] + "/anonymize"
    assert (await client.post(path)).status_code == 403
    query(
        world,
        "INSERT INTO healthsync.memberships VALUES (%s,%s,'privacy',true) RETURNING role",
        (world["tenant"], user),
    )
    assert (await client.post(path)).status_code == 409  # Undecided retention fails closed.
    assert (
        await client.patch(
            world["base"] + "/appointments/" + booking.json()["id"],
            json={"action": "cancel", "expected_version": 1},
        )
    ).status_code == 200
    query(
        world,
        "UPDATE healthsync.patients SET retention_until=clock_timestamp()-interval '1 day' WHERE tenant_id=%s RETURNING id",
        (world["tenant"],),
    )
    before = len(
        query(
            world, "SELECT id FROM healthsync.audit_events WHERE tenant_id=%s", (world["tenant"],)
        )
    )
    assert (await client.post(path)).status_code == 200
    patient = query(
        world, "SELECT * FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],)
    )[0]
    assert patient["pii_ciphertext"] is patient["auth_user_id"] is patient["email_hmac"] is None
    assert patient["deleted_at"] and patient["anonymized_at"]
    assert (
        len(
            query(
                world,
                "SELECT id FROM healthsync.audit_events WHERE tenant_id=%s",
                (world["tenant"],),
            )
        )
        > before
    )
    assert (
        query(
            world,
            "SELECT id FROM healthsync.privacy_contexts WHERE tenant_id=%s AND ip_ciphertext IS NOT NULL",
            (world["tenant"],),
        )
        == []
    )
    assert (await client.get(world["base"] + "/privacy/export")).json()["profiles"] == []


async def test_audit_is_immutable_even_for_owner_without_ddl(client, world):
    await book(client, world)
    with pytest.raises(RaiseException):
        query(
            world,
            "UPDATE healthsync.audit_events SET action='tamper' WHERE tenant_id=%s RETURNING id",
            (world["tenant"],),
        )
    with pytest.raises(InsufficientPrivilege):
        async with transaction(world["tenant"], None, None) as (conn, _):
            await conn.execute("DELETE FROM healthsync.audit_events")


def test_ciphertext_binds_to_patient_and_detects_tampering():
    ciphertext = encrypt({"name": "Ficticio"}, "tenant:patient-1")
    with pytest.raises(InvalidTag):
        decrypt(ciphertext, settings().pii_key_id, "tenant:patient-2")
    with pytest.raises(InvalidTag):
        decrypt(
            ciphertext[:-1] + bytes([ciphertext[-1] ^ 1]), settings().pii_key_id, "tenant:patient-1"
        )


@pytest.mark.parametrize("change", ["signature", "issuer", "audience", "expired"])
def test_jwt_verification_rejects_forged_claims(monkeypatch, change):
    from app import auth

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        auth,
        "jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key())
        ),
    )
    monkeypatch.setattr(settings(), "supabase_url", "https://auth.example.com")
    now = datetime.now(UTC)
    claims = {
        "sub": str(uuid4()),
        "iss": "https://auth.example.com/auth/v1",
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    if change == "issuer":
        claims["iss"] = "https://attacker.example/auth/v1"
    if change == "audience":
        claims["aud"] = "wrong"
    if change == "expired":
        claims["exp"] = now - timedelta(minutes=5)
    signing = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if change == "signature"
        else private
    )
    with pytest.raises(jwt.PyJWTError):
        auth.decode_token(jwt.encode(claims, signing, algorithm="RS256"))


async def test_vault_every_open_is_audited_and_expired_link_denied(
    client, world, login, monkeypatch
):
    import hashlib

    from app import main

    user = login()
    await book(client, world)
    patient = query(
        world, "SELECT id FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],)
    )[0]["id"]
    query(
        world,
        "UPDATE healthsync.tenant_modules SET enabled=true WHERE tenant_id=%s AND code='vault' RETURNING code",
        (world["tenant"],),
    )
    content = b"%PDF-1.7\nsynthetic test content"
    async with transaction(world["tenant"], None, None) as (conn, _):
        row = await (
            await conn.execute(
                """
            INSERT INTO healthsync.exam_results (tenant_id,patient_id,object_key,uploaded_by,content_sha256,byte_size,scan_status)
            VALUES (%s,%s,'opaque/test.pdf',%s,%s,%s,'clean') RETURNING id
        """,
                (world["tenant"], patient, user, hashlib.sha256(content).digest(), len(content)),
            )
        ).fetchone()
    access = await client.post(world["base"] + f"/exam-results/{row['id']}/access")
    assert access.status_code == 200 and access.json()["expires_in"] == 900
    monkeypatch.setattr(main, "read_private_pdf", lambda key, size: content)
    for _ in range(2):
        opened = await client.get(access.json()["path"])
        assert opened.status_code == 200 and opened.content == content
    assert (
        len(
            query(
                world,
                "SELECT id FROM healthsync.audit_events WHERE tenant_id=%s AND action='READ_RESULT'",
                (world["tenant"],),
            )
        )
        == 2
    )
    token = jwt.encode(
        {
            "sub": str(user),
            "tenant": str(world["tenant"]),
            "result": str(row["id"]),
            "purpose": "vault",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        base64.b64decode(settings().vault_signing_key_base64),
        algorithm="HS256",
    )
    assert (await client.get(world["base"] + "/vault/" + token)).status_code == 403
    login()
    assert (await client.get(access.json()["path"])).status_code == 403
    clinician = login()
    query(
        world,
        "INSERT INTO healthsync.memberships VALUES (%s,%s,'clinician',true) RETURNING role",
        (world["tenant"], clinician),
    )
    clinical_path = world["base"] + f"/exam-results/{row['id']}/access"
    assert (await client.post(clinical_path)).status_code == 404
    query(
        world,
        """
        INSERT INTO healthsync.care_relationships
          (tenant_id,patient_id,clinician_id,granted_by,valid_until)
        VALUES (%s,%s,%s,%s,clock_timestamp()+interval '1 day') RETURNING id
    """,
        (world["tenant"], patient, clinician, user),
    )
    assert (await client.post(clinical_path)).status_code == 200
    query(
        world,
        "UPDATE healthsync.care_relationships SET revoked_at=clock_timestamp() WHERE patient_id=%s RETURNING id",
        (patient,),
    )
    assert (await client.post(clinical_path)).status_code == 404


async def test_read_audit_survives_failed_version_validation(client, world, login):
    login()
    response = await book(client, world)
    path = world["base"] + "/appointments/" + response.json()["id"]
    assert (
        await client.patch(path, json={"action": "cancel", "expected_version": 999})
    ).status_code == 409
    assert query(
        world,
        "SELECT id FROM healthsync.audit_events WHERE entity_id=%s AND action='READ'",
        (response.json()["id"],),
    )


async def test_whatsapp_requires_extra_consent_and_phone(client, world):
    data = payload(world)
    data["whatsapp"] = True
    assert (await book(client, world, data)).status_code == 422
    data["patient"]["phone"] = "+56912345678"
    assert (await book(client, world, data)).status_code == 409
    data["consent_document_ids"] = [str(d["id"]) for d in world["docs"]]
    assert (await book(client, world, data)).status_code == 201
    assert (
        len(
            query(
                world,
                "SELECT id FROM healthsync.outbox WHERE tenant_id=%s AND channel='whatsapp'",
                (world["tenant"],),
            )
        )
        == 3
    )


async def test_worker_retries_without_pii_in_error(client, world, monkeypatch):
    from app.worker import dispatch_one

    await book(client, world)
    monkeypatch.setattr(settings(), "notification_webhook_url", "https://notify.example.com")
    monkeypatch.setattr(settings(), "notification_webhook_token", "test-token")
    factory = httpx.AsyncClient

    async def provider(request):
        assert b"Consultation" not in request.content
        return httpx.Response(503, text="do not save provider response with patient PII")

    monkeypatch.setattr(
        "app.worker.httpx.AsyncClient",
        lambda **kwargs: factory(transport=httpx.MockTransport(provider), **kwargs),
    )
    assert await dispatch_one(world["tenant"])
    event = query(
        world,
        "SELECT * FROM healthsync.outbox WHERE tenant_id=%s AND kind='booking_created'",
        (world["tenant"],),
    )[0]
    assert (
        event["attempts"] == 1
        and event["last_error_code"] == "delivery_unavailable"
        and event["delivered_at"] is None
    )


async def test_validation_does_not_echo_sensitive_input(client, world):
    data = payload(world)
    data["patient"]["email"] = "invalid-sensitive@example"
    response = await book(client, world, data)
    assert response.status_code == 422 and "invalid-sensitive" not in response.text
